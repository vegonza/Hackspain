import json
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel

from extractor.categories import CategorizedInvoiceExtraction, MODEL, categorize_invoice
from extractor.extraction import InvoiceExtraction
from shared.logger import setup_logger
from shared.retries import MAX_ATTEMPTS, retry_delay, retryable
from shared.storage import download_file, get_client, upload_file
from shared.usage import track_usage

PAGE_SIZE = 1000
WORKERS = 10
logger = setup_logger()


class StoredInvoice(BaseModel):
    id: UUID
    name: str
    result_path: str
    line_items: list[dict[str, object]] | None


class Result(StrEnum):
    CATEGORIZED = "categorized"
    SYNCED = "synced"
    UNCHANGED = "unchanged"


def read_invoices() -> list[StoredInvoice]:
    invoices: list[StoredInvoice] = []
    while True:
        rows = (
            get_client()
            .table("documents")
            .select("id,name,result_path,line_items")
            .is_("deleted_at", "null")
            .not_.is_("result_path", "null")
            .order("created_at")
            .range(len(invoices), len(invoices) + PAGE_SIZE - 1)
            .execute()
            .data
        )
        invoices.extend(StoredInvoice.model_validate(row) for row in rows)
        if len(rows) < PAGE_SIZE:
            return invoices


def call_jev(invoice: StoredInvoice, extraction: InvoiceExtraction) -> CategorizedInvoiceExtraction:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with track_usage("typesafe", MODEL, "categorization", str(invoice.id), invoice.name) as usage:
                return categorize_invoice(extraction, usage)
        except Exception as error:
            if attempt == MAX_ATTEMPTS or not retryable(error):
                raise
            delay = retry_delay(error, attempt)
            logger.warning("[CATEGORIES] Retrying %s in %.1fs after %s (%s/%s)",
                           invoice.name, delay, type(error).__name__, attempt + 1, MAX_ATTEMPTS)
            time.sleep(delay)
    raise RuntimeError("Category retry loop ended without a result")


def categorize(invoice: StoredInvoice) -> Result:
    payload = json.loads(download_file(invoice.result_path))
    items = payload["line_items"]
    has_categories = all("category" in item for item in items)
    if has_categories:
        extraction = CategorizedInvoiceExtraction.model_validate(payload)
    else:
        extraction = call_jev(invoice, InvoiceExtraction.model_validate(payload))
        upload_file(invoice.result_path, extraction.model_dump_json().encode("utf-8"), "application/json")

    stored_items = [item.model_dump(mode="json") for item in extraction.line_items]
    if invoice.line_items != stored_items:
        (
            get_client()
            .table("documents")
            .update({"line_items": stored_items})
            .eq("id", str(invoice.id))
            .is_("deleted_at", "null")
            .execute()
        )
        logger.info("[CATEGORIES] Saved categories for %s", invoice.name)
    if not has_categories:
        return Result.CATEGORIZED
    if invoice.line_items != stored_items:
        return Result.SYNCED
    return Result.UNCHANGED


def main() -> None:
    invoices = read_invoices()
    totals = {result: 0 for result in Result}
    failures: list[tuple[StoredInvoice, Exception]] = []
    futures: dict[Future[Result], StoredInvoice] = {}
    with ThreadPoolExecutor(max_workers=WORKERS, thread_name_prefix="categories") as pool:
        for invoice in invoices:
            futures[pool.submit(categorize, invoice)] = invoice
        for completed, future in enumerate(as_completed(futures), start=1):
            invoice = futures[future]
            try:
                totals[future.result()] += 1
            except Exception as error:
                failures.append((invoice, error))
                logger.exception("[CATEGORIES] Failed %s (%s)", invoice.name, invoice.id)
            if completed % 25 == 0 or completed == len(invoices):
                logger.info("[CATEGORIES] Progress %s/%s", completed, len(invoices))

    logger.info("[CATEGORIES] Finished: %s categorized, %s synchronized, %s unchanged, %s failed",
                totals[Result.CATEGORIZED], totals[Result.SYNCED], totals[Result.UNCHANGED], len(failures))
    if failures:
        raise RuntimeError(f"Could not categorize {len(failures)} invoices")


if __name__ == "__main__":
    main()
