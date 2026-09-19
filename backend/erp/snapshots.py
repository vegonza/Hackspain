from datetime import datetime, timezone
from typing import TYPE_CHECKING

from erp.errors import ErpProtocolError
from erp.models import ErpPage, ErpSnapshot
from shared.logger import get_logger

if TYPE_CHECKING:
    from erp.client import ErpClient

logger = get_logger()


def check_page(page: ErpPage, first: ErpPage) -> None:
    if (page.total_entries, page.total_pages, page.page_size) != (first.total_entries, first.total_pages, first.page_size):
        raise ErpProtocolError('ERP pagination metadata changed during the download')
    expected = min(page.page_size, max(0, page.total_entries - (page.number - 1) * page.page_size))
    if len(page.entries) != expected:
        raise ErpProtocolError(f'ERP page {page.number} contains {len(page.entries)} entries; expected {expected}')


def download_snapshot(client: 'ErpClient') -> ErpSnapshot:
    """Return a complete download; preserve duplicate entries and data warnings."""
    logger.info('[ERP] Downloading snapshot')
    before = client.get_status()
    first = client.get_page(1)
    if first.total_entries != before.entry_count or first.total_entries == 0:
        raise ErpProtocolError('ERP page total does not match a nonempty source state')
    if first.total_pages != (first.total_entries + first.page_size - 1) // first.page_size:
        raise ErpProtocolError('ERP total pages does not match its entry count and page size')
    check_page(first, first)
    entries = list(first.entries)
    for number in range(2, first.total_pages + 1):
        page = client.get_page(number)
        check_page(page, first)
        entries.extend(page.entries)
    after = client.get_status()
    if (
        (before.version, before.entry_count, before.update_loaded) !=
        (after.version, after.entry_count, after.update_loaded)
        or after.uptime_seconds < before.uptime_seconds
    ):
        raise ErpProtocolError('ERP state changed during the snapshot download')
    if len(entries) != first.total_entries:
        raise ErpProtocolError('ERP snapshot is incomplete')
    snapshot = ErpSnapshot(
        fetched_at=datetime.now(timezone.utc), status_before=before,
        status_after=after, entries=entries,
    )
    logger.info('[ERP] Downloaded snapshot: %s entries, version %s', len(entries), after.version)
    return snapshot
