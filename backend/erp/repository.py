from uuid import UUID

from erp.models import ErpSnapshot, SavedErpSnapshot
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
    """Read the newest saved download together with all of its entries."""
    snapshots = get_client().table('erp_snapshots').select('*').order('fetched_at', desc=True).order('id', desc=True).limit(1).execute().data
    if not snapshots:
        return None
    entries = get_client().table('erp_entries').select('*').eq('snapshot_id', snapshots[0]['id']).order('entry_id').execute().data
    documents = get_client().table('documents').select('id,name,erp_entry_id').eq('erp_snapshot_id', snapshots[0]['id']).is_('deleted_at', 'null').order('name').execute().data
    linked: dict[str, list[dict[str, str]]] = {}
    for document in documents:
        if document['erp_entry_id'] is not None:
            linked.setdefault(document['erp_entry_id'], []).append({'id': document['id'], 'name': document['name']})
    return SavedErpSnapshot.model_validate({**snapshots[0], 'entries': [{**entry, 'documents': linked.get(entry['id'], [])} for entry in entries]})
