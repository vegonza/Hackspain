from uuid import UUID

from erp.models import ErpEntryDetail, ErpSnapshot, SavedErpSnapshot
from shared.logger import get_logger
from shared.storage import get_client

logger = get_logger()


def save_snapshot(snapshot: ErpSnapshot) -> UUID:
    """Persist a validated download and all its entries in one transaction."""
    result = get_client().rpc('save_erp_snapshot', {
        'p_fetched_at': snapshot.fetched_at.isoformat(),
        'p_erp_version': snapshot.status_after.version,
        'p_update_loaded': snapshot.status_after.update_loaded,
        'p_entries': [entry.model_dump(mode='json') for entry in snapshot.entries],
    }).execute()
    snapshot_id = UUID(result.data)
    logger.info('[ERP] Saved snapshot %s: %s entries, version %s',
                snapshot_id, len(snapshot.entries), snapshot.status_after.version)
    return snapshot_id


def read_latest_snapshot() -> SavedErpSnapshot | None:
    """Read the complete latest snapshot in one database request."""
    data = get_client().rpc('get_erp_snapshot', {}).execute().data
    return None if data is None else SavedErpSnapshot.model_validate(data)


def read_entry(entry_id: UUID) -> ErpEntryDetail | None:
    """Resolve a saved entry independently of newer snapshots."""
    data = get_client().rpc('get_erp_entry', {'p_entry_id': str(entry_id)}).execute().data
    return None if data is None else ErpEntryDetail.model_validate(data)
