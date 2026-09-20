from fastapi import APIRouter, Response

from gestoria import repository, service
from gestoria.models import Overview, SendInput, SendResult, SettingsInput

router = APIRouter(prefix='/api/gestoria', tags=['gestoria'])


@router.get('')
def overview(period: str) -> Overview:
    return repository.overview(period)


@router.put('', status_code=204)
def save_settings(value: SettingsInput) -> Response:
    repository.save_settings(value)
    return Response(status_code=204)


@router.post('/send')
def send(value: SendInput) -> SendResult:
    return service.send(value)
