from uuid import UUID

from erp.client import ErpClient
from erp.repository import save_snapshot


def sync_erp_snapshot() -> UUID:
    """Download and validate the ERP before publishing its snapshot to Supabase."""
    with ErpClient.from_env() as client:
        snapshot = client.get_snapshot()
    return save_snapshot(snapshot)
