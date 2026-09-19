from uuid import UUID

from documents.repository import DocumentDetails
from erp import sync_erp_snapshot
from shared.logger import get_logger
from shared.redis import get_redis
from shared.storage import get_client

logger = get_logger()


def latest_snapshot_id() -> UUID | None:
    rows = get_client().table("erp_snapshots").select("id").order("fetched_at", desc=True).order("id", desc=True).limit(1).execute().data
    return UUID(rows[0]["id"]) if rows else None


def bind_snapshot(document: DocumentDetails) -> None:
    """Pin one saved snapshot for the document and reuse it across retries."""
    if document.erp_snapshot_id is not None:
        return
    snapshot_id = latest_snapshot_id()
    if snapshot_id is None:
        with get_redis() as redis, redis.lock("erp:snapshot-initialization", timeout=600):
            snapshot_id = latest_snapshot_id()
            if snapshot_id is None:
                snapshot_id = sync_erp_snapshot()
    get_client().table("documents").update({"erp_snapshot_id": str(snapshot_id)}).eq("id", str(document.id)).execute()
    document.erp_snapshot_id = snapshot_id
    logger.info("[PIPELINE] Linked ERP snapshot %s to %s", snapshot_id, document.name)


def match_entry(document: DocumentDetails, purchase_order: str) -> None:
    """Link only an unambiguous order match within the document's pinned snapshot."""
    assert document.erp_snapshot_id is not None
    entries = get_client().table("erp_entries").select("id").eq("snapshot_id", str(document.erp_snapshot_id)).eq("order_id", purchase_order).limit(2).execute().data if purchase_order else []
    entry_id = entries[0]["id"] if len(entries) == 1 else None
    get_client().table("documents").update({"erp_entry_id": entry_id}).eq("id", str(document.id)).execute()
    logger.info("[PIPELINE] ERP order match for %s: %s", document.name, "unique" if entry_id is not None else "missing or ambiguous")
