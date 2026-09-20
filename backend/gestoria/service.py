from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from redis import Redis
from redis.lock import Lock

from gestoria import repository
from gestoria.mailer import RejectedEmail, batches, configuration, make_email, send_email
from gestoria.models import PendingSend, SendInput, SendResult
from shared.logger import get_logger
from shared.redis import get_redis

PENDING_KEY = 'gestoria:pending-send'


def finish_send(pending: PendingSend, redis: Redis, lock: Lock, api_key: str, *, fresh: bool = False) -> int:
    lock.extend(180, replace_ttl=True)
    if not pending.accepted:
        if datetime.now(timezone.utc) - pending.created_at >= timedelta(hours=23):
            raise HTTPException(409, 'gestoria_send_expired')
        try:
            send_email(pending.email, api_key, f'gestoria/{pending.id}')
        except RejectedEmail as error:
            if fresh:
                redis.delete(PENDING_KEY)
            raise HTTPException(409, 'gestoria_send_failed' if fresh else 'gestoria_send_uncertain') from error
        pending.accepted = True
        redis.set(PENDING_KEY, pending.model_dump_json())
    repository.mark_sent(pending.received_ids, pending.issued_ids)
    redis.delete(PENDING_KEY)
    count = len(pending.received_ids) + len(pending.issued_ids)
    get_logger().info('[GESTORIA] Marked %s invoices sent to %s', count, pending.email.to[0])
    return count


def send(value: SendInput) -> SendResult:
    api_key, sender = configuration()
    with get_redis() as redis:
        lock = redis.lock('gestoria:send-lock', timeout=180, blocking=False)
        if not lock.acquire():
            raise HTTPException(409, 'gestoria_busy')
        try:
            sent = 0
            received_ids, issued_ids = set(value.received_ids), set(value.issued_ids)
            invoices = [invoice for invoice in repository.eligible_invoices(value.period)
                        if invoice.id in (received_ids if invoice.kind == 'received' else issued_ids)]
            selected_received = {invoice.id for invoice in invoices if invoice.kind == 'received'}
            selected_issued = {invoice.id for invoice in invoices if invoice.kind == 'issued'}
            saved = redis.get(PENDING_KEY)
            if saved is not None:
                pending = PendingSend.model_validate_json(saved)
                if not pending.accepted and (pending.email.to != [value.email]
                        or not set(pending.received_ids).issubset(selected_received)
                        or not set(pending.issued_ids).issubset(selected_issued)):
                    raise HTTPException(409, 'gestoria_pending_send')
                finish_send(pending, redis, lock, api_key)
                if pending.email.to == [value.email]:
                    sent += len(selected_received.intersection(pending.received_ids)) + len(selected_issued.intersection(pending.issued_ids))
                completed = set(pending.received_ids + pending.issued_ids)
                invoices = [invoice for invoice in invoices if invoice.id not in completed]
            for selected, attachments in batches(invoices, lambda: lock.extend(180, replace_ttl=True)):
                pending = PendingSend(id=uuid4(), created_at=datetime.now(timezone.utc),
                                      received_ids=[invoice.id for invoice in selected if invoice.kind == 'received'],
                                      issued_ids=[invoice.id for invoice in selected if invoice.kind == 'issued'],
                                      email=make_email(sender, value.email, selected, attachments))
                redis.set(PENDING_KEY, pending.model_dump_json())
                get_logger().info('[GESTORIA] Sending %s invoices to %s: %s', len(selected), value.email,
                                  ', '.join(invoice.name for invoice in selected))
                sent += finish_send(pending, redis, lock, api_key, fresh=True)
            return SendResult(sent=sent)
        finally:
            lock.release()
