from uuid import UUID

from erp.models import ErpSnapshot
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
