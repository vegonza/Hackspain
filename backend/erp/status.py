from xml.etree import ElementTree

from erp.errors import ErpProtocolError
from erp.models import ErpStatus


def parse_status(root: ElementTree.Element) -> ErpStatus:
    version = root.findtext('version')
    uptime = root.findtext('activo_segundos')
    count = root.findtext('asientos')
    update = root.findtext('actualizacion_cargada')
    if root.tag != 'estado' or version is None or uptime is None or count is None or update not in ('SI', 'NO'):
        raise ErpProtocolError('ERP status has missing or invalid fields')
    try:
        return ErpStatus(version=version, uptime_seconds=int(uptime), entry_count=int(count), update_loaded=update == 'SI')
    except ValueError as exc:
        raise ErpProtocolError('ERP status has invalid values') from exc
