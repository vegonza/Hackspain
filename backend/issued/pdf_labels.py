import json
from pathlib import Path

LABELS: dict[str, str] = json.loads((Path(__file__).with_name('locales') / 'es.json').read_text())
