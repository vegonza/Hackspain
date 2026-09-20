"""Export the challenge's two JSONL batches from the application's saved decisions."""

import argparse
import json
import os
import sys
from http.cookiejar import CookieJar
from hashlib import sha256
from pathlib import Path
from typing import Literal, TypedDict, cast
from urllib.error import URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener


Result = Literal['PAGAR', 'NO_PAGAR', 'ESCALAR']


class PaymentDecision(TypedDict):
    classification: Result


class Invoice(TypedDict):
    sha256: str
    status: str
    payment_decision: PaymentDecision | None


class Outcome(TypedDict):
    file_id: str
    result: Result


def batch_outcomes(directory: Path, expected_count: int, invoices: list[Invoice]) -> list[Outcome]:
    """Match original filenames by content, rejecting incomplete or ambiguous results."""
    files = sorted(directory.glob('*.pdf'))
    if len(files) != expected_count:
        raise ValueError(f'{directory}: se esperaban {expected_count} PDFs, hay {len(files)}.')
    by_hash: dict[str, list[Invoice]] = {}
    for invoice in invoices:
        by_hash.setdefault(invoice['sha256'], []).append(invoice)
    outcomes: list[Outcome] = []
    errors: list[str] = []
    for path in files:
        matches = by_hash.get(sha256(path.read_bytes()).hexdigest(), [])
        if len(matches) != 1:
            errors.append(f'{path.name}: {len(matches)} facturas subidas coinciden con el hash; se necesita una.')
            continue
        invoice = matches[0]
        decision = invoice['payment_decision']
        if invoice['status'] != 'ready':
            errors.append(f'{path.name}: estado {invoice["status"]}; debe terminar de procesarse.')
        elif decision is None or decision['classification'] not in ('PAGAR', 'NO_PAGAR', 'ESCALAR'):
            errors.append(f'{path.name}: falta una decisión válida.')
        else:
            outcomes.append({'file_id': path.name, 'result': decision['classification']})
    if errors:
        raise ValueError('\n'.join(errors))
    return outcomes


def read_invoices(api_url: str, password: str) -> list[Invoice]:
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    login = Request(
        f'{api_url.rstrip("/")}/auth/login',
        data=json.dumps({'password': password}).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with opener.open(login, timeout=60):
        pass
    with opener.open(f'{api_url.rstrip("/")}/invoices', timeout=60) as response:
        return cast(list[Invoice], json.load(response))


def export(api_url: str, challenge_dir: Path, output_dir: Path, password: str) -> dict[str, int]:
    """Validate both batches before writing UTF-8 JSONL; never change invoice decisions."""
    invoices = read_invoices(api_url, password)
    batches = {
        'outcomes.jsonl': batch_outcomes(challenge_dir / 'facturas', 500, invoices),
        'outcomes_lote2.jsonl': batch_outcomes(challenge_dir / 'facturas_primin', 40, invoices),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, outcomes in batches.items():
        content = ''.join(json.dumps(outcome, ensure_ascii=False) + '\n' for outcome in outcomes)
        (output_dir / name).write_text(content, encoding='utf-8')
    return {name: len(outcomes) for name, outcomes in batches.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description='Exporta los dos JSONL de entrega desde las decisiones guardadas.')
    parser.add_argument('--output-dir', type=Path, required=True, help='Carpeta de destino de los JSONL (se sobrescriben).')
    parser.add_argument('--api-url', default='http://localhost:5173/api', help='URL base de la API.')
    parser.add_argument('--challenge-dir', type=Path,
                        default=Path(__file__).resolve().parents[1] / '500-sombras-de-alberto',
                        help='Carpeta del reto con facturas/ y facturas_primin/.')
    args = parser.parse_args()
    try:
        counts = export(args.api_url, args.challenge_dir, args.output_dir, os.environ['APP_PASSWORD'])
    except (OSError, URLError, ValueError) as error:
        print(f'No se ha podido exportar: {error}', file=sys.stderr)
        return 1
    for name, count in counts.items():
        print(f'{args.output_dir / name}: {count} resultados')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
