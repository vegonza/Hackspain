import os
from base64 import b64decode
from datetime import datetime, timedelta, timezone
from typing import Literal
from unittest import TestCase
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from auth import COOKIE_NAME, PasswordMiddleware, session_token
from gestoria import mailer, repository, service
from gestoria.models import Attachment, Invoice, Overview, PendingSend, SendInput
from gestoria.router import router


def invoice(kind: Literal['received', 'issued'] = 'received') -> Invoice:
    identifier = uuid4()
    return Invoice(id=identifier, kind=kind, name='Factura.pdf', path=f'{identifier}/original.pdf')


class GestoriaRepositoryTests(TestCase):
    def test_only_approved_unsent_active_received_and_paid_issued_query(self) -> None:
        with patch('gestoria.repository.get_client') as client:
            received = MagicMock()
            issued = MagicMock()
            client.return_value.table.side_effect = lambda table: received if table == 'documents' else issued
            for query in [received, issued]:
                for method in ['select', 'is_', 'eq', 'order', 'range']:
                    getattr(query, method).return_value = query
                query.execute.return_value.data = []
            self.assertEqual(repository.eligible_invoices('2026-09'), [])
        received.is_.assert_any_call('deleted_at', 'null')
        received.is_.assert_any_call('gestoria_sent_at', 'null')
        received.eq.assert_any_call('status', 'ready')
        received.eq.assert_any_call('payment_decision->>classification', 'PAGAR')
        issued.eq.assert_called_once_with('status', 'paid')
        issued.is_.assert_called_once_with('gestoria_sent_at', 'null')

    def test_reads_beyond_database_page_limit(self) -> None:
        query = MagicMock()
        for method in ['select', 'is_', 'eq', 'order', 'range']:
            getattr(query, method).return_value = query
        query.execute.side_effect = [MagicMock(data=[{'id': str(uuid4())} for _ in range(500)]), MagicMock(data=[{'id': str(uuid4())}])]
        with patch('gestoria.repository.get_client') as client:
            client.return_value.table.return_value = query
            self.assertEqual(len(repository.sendable_rows('received')), 501)
        self.assertEqual([call.args for call in query.range.call_args_list], [(0, 499), (500, 999)])

    def test_period_uses_received_invoice_date_and_issued_issue_date(self) -> None:
        received = [{'id': str(uuid4()), 'name': value or 'undated', 'invoice_date': value}
                    for value in ['2026-08-31', '2026-09-01', '2025-08-01', None, '2026-08-99']]
        issued = [{'id': str(uuid4()), 'invoice_number': value, 'issue_date': value, 'pdf_path': 'issued/invoice.pdf'}
                  for value in ['2026-08-01', '2026-09-30']]
        with patch('gestoria.repository.sendable_rows', side_effect=lambda kind: received if kind == 'received' else issued):
            august = repository.eligible_invoices('2026-08')
            september = repository.eligible_invoices('2026-09')
            self.assertEqual({item.name for item in august}, {'2026-08-31', '2026-08-01.pdf'})
            self.assertEqual({item.name for item in september}, {'2026-09-01', '2026-09-30.pdf'})
            self.assertEqual(len(repository.eligible_invoices('all')), 7)
            self.assertEqual({item.name for item in repository.eligible_invoices('undated')}, {'undated', '2026-08-99'})

    def test_overview_status_counts_match_only_invoices_eligible_for_sending(self) -> None:
        eligible = [invoice(), invoice(), invoice('issued')]
        with patch('gestoria.repository.read_settings', return_value='gestoria@example.com'), patch('gestoria.repository.eligible_invoices', return_value=eligible) as candidates:
            overview = repository.overview('2026-08')
        self.assertEqual(overview.invoices, eligible)
        self.assertEqual({(item.kind, item.status): item.count for item in overview.statuses}, {
            ('received', 'PAGAR'): 2, ('issued', 'paid'): 1,
        })
        self.assertEqual(sum(item.count for item in overview.statuses), len(overview.invoices))
        candidates.assert_called_once_with('2026-08')

    def test_marks_both_invoice_types_in_one_transaction(self) -> None:
        received, issued = uuid4(), uuid4()
        with patch('gestoria.repository.get_client') as client:
            repository.mark_sent([received], [issued])
        client.return_value.rpc.assert_called_once_with('mark_gestoria_sent', {'p_received_ids': [str(received)], 'p_issued_ids': [str(issued)]})

    def test_overview_has_no_private_storage_paths_and_put_returns_no_content(self) -> None:
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client, patch('gestoria.router.repository.overview', return_value=Overview(email='gestoria@example.com', invoices=[invoice()], statuses=[])), patch('gestoria.router.repository.save_settings') as save:
            result = client.get('/api/gestoria?period=2026-09').json()
            self.assertNotIn('path', result['invoices'][0])
            self.assertEqual(client.put('/api/gestoria', json={'email': 'new@example.com'}).status_code, 204)
            self.assertEqual(save.call_args.args[0].email, 'new@example.com')


class GestoriaSendTests(TestCase):
    def setUp(self) -> None:
        self.received = invoice()
        self.issued = invoice('issued')
        self.available = [self.received, self.issued]
        self.cache: dict[str, str] = {}
        self.redis = MagicMock()
        self.redis.get.side_effect = self.cache.get
        self.redis.set.side_effect = lambda key, value: self.cache.__setitem__(key, value)
        self.redis.delete.side_effect = lambda key: self.cache.pop(key, None)
        self.lock = self.redis.lock.return_value
        self.lock.acquire.return_value = True
        for target, kwargs in [
            ('gestoria.service.configuration', {'return_value': ('test-key', 'Invoices <sender@example.com>')}),
            ('gestoria.service.get_redis', {}),
            ('gestoria.service.repository.eligible_invoices', {'side_effect': lambda period: list(self.available)}),
            ('gestoria.service.repository.mark_sent', {'side_effect': self.mark}),
            ('gestoria.mailer.download_file', {'return_value': b'%PDF-test'}),
            ('gestoria.service.send_email', {}),
        ]:
            patcher = patch(target, **kwargs)
            mock = patcher.start()
            self.addCleanup(patcher.stop)
            if target.endswith('get_redis'):
                mock.return_value.__enter__.return_value = self.redis
            if target.endswith('send_email'):
                self.send_email = mock
            if target.endswith('mark_sent'):
                self.mark_sent = mock
        self.body = SendInput(email='gestoria@example.com', period='2026-09', received_ids=[self.received.id], issued_ids=[self.issued.id])

    def mark(self, received_ids: list[UUID], issued_ids: list[UUID]) -> None:
        ids = set(received_ids + issued_ids)
        self.available = [item for item in self.available if item.id not in ids]

    def test_send_attaches_both_types_marks_only_after_acceptance_and_does_not_repeat(self) -> None:
        self.send_email.side_effect = lambda *args: self.mark_sent.assert_not_called()
        self.assertEqual(service.send(self.body).sent, 2)
        payload = self.send_email.call_args.args[0]
        self.assertEqual(len(payload.attachments), 2)
        self.assertEqual(payload.to, ['gestoria@example.com'])
        self.assertEqual(service.send(self.body).sent, 0)
        self.send_email.assert_called_once()
        self.assertNotIn(service.PENDING_KEY, self.cache)

    def test_authenticated_send_route_attaches_pdfs_through_resend_and_records_success(self) -> None:
        app = FastAPI()
        app.add_middleware(PasswordMiddleware)
        app.include_router(router)
        self.send_email.side_effect = mailer.send_email
        with TestClient(app) as client, patch('gestoria.mailer.httpx.post', return_value=httpx.Response(200, json={'id': 'resend-test'})) as post:
            payload = self.body.model_dump(mode='json')
            self.assertEqual(client.post('/api/gestoria/send', json=payload).status_code, 401)
            post.assert_not_called()
            client.cookies.set(COOKIE_NAME, session_token())
            response = client.post('/api/gestoria/send', json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'sent': 2})
            email = post.call_args.kwargs['json']
            self.assertEqual(email['to'], [self.body.email])
            self.assertEqual(email['from'], 'Invoices <sender@example.com>')
            self.assertEqual(len(email['attachments']), 2)
            for attachment in email['attachments']:
                self.assertEqual(b64decode(attachment['content']), b'%PDF-test')
            self.mark_sent.assert_called_once_with([self.received.id], [self.issued.id])
            self.assertEqual(client.post('/api/gestoria/send', json=payload).json(), {'sent': 0})
            post.assert_called_once()

    def test_server_filters_unpaid_and_nonselected_invoices(self) -> None:
        extra = invoice()
        self.available = [self.received, extra]
        self.assertEqual(service.send(self.body).sent, 1)
        self.mark_sent.assert_called_once_with([self.received.id], [])

    def test_send_rechecks_period_even_if_request_contains_other_month_ids(self) -> None:
        self.body.period = '2026-08'
        with patch('gestoria.service.repository.eligible_invoices', return_value=[self.received]) as eligible:
            self.assertEqual(service.send(self.body).sent, 1)
        eligible.assert_called_once_with('2026-08')
        self.mark_sent.assert_called_once_with([self.received.id], [])

    def test_switching_month_cannot_retry_another_months_pending_email(self) -> None:
        self.send_email.side_effect = HTTPException(409, 'gestoria_send_uncertain')
        with self.assertRaises(HTTPException):
            service.send(self.body)
        self.body.period = '2026-08'
        with patch('gestoria.service.repository.eligible_invoices', return_value=[]), self.assertRaises(HTTPException) as error:
            service.send(self.body)
        self.assertEqual(error.exception.detail, 'gestoria_pending_send')
        self.send_email.assert_called_once()
        self.mark_sent.assert_not_called()

    def test_concurrent_send_cannot_start(self) -> None:
        self.lock.acquire.return_value = False
        with self.assertRaises(HTTPException) as error:
            service.send(self.body)
        self.assertEqual(error.exception.detail, 'gestoria_busy')
        self.send_email.assert_not_called()

    def test_rejection_does_not_mark_and_releases_pending_send(self) -> None:
        self.send_email.side_effect = mailer.RejectedEmail()
        with self.assertRaises(HTTPException):
            service.send(self.body)
        self.mark_sent.assert_not_called()
        self.assertNotIn(service.PENDING_KEY, self.cache)
        self.lock.release.assert_called_once()

    def test_timeout_retries_exact_payload_and_key(self) -> None:
        self.send_email.side_effect = HTTPException(409, 'gestoria_send_uncertain')
        with self.assertRaises(HTTPException):
            service.send(self.body)
        original = self.send_email.call_args
        self.mark_sent.assert_not_called()
        self.send_email.side_effect = None
        self.assertEqual(service.send(self.body).sent, 2)
        self.assertEqual(self.send_email.call_args, original)

    def test_rejection_after_timeout_does_not_discard_original_idempotency_key(self) -> None:
        self.send_email.side_effect = HTTPException(409, 'gestoria_send_uncertain')
        with self.assertRaises(HTTPException):
            service.send(self.body)
        original = self.cache[service.PENDING_KEY]
        self.send_email.side_effect = mailer.RejectedEmail()
        with self.assertRaises(HTTPException) as error:
            service.send(self.body)
        self.assertEqual(error.exception.detail, 'gestoria_send_uncertain')
        self.assertEqual(self.cache[service.PENDING_KEY], original)
        self.mark_sent.assert_not_called()

    def test_accepted_email_database_failure_retries_only_database(self) -> None:
        self.mark_sent.side_effect = RuntimeError('database unavailable')
        with self.assertRaises(RuntimeError):
            service.send(self.body)
        self.assertTrue(PendingSend.model_validate_json(self.cache[service.PENDING_KEY]).accepted)
        self.mark_sent.side_effect = self.mark
        self.assertEqual(service.send(self.body).sent, 2)
        self.send_email.assert_called_once()

    def test_pending_unconfirmed_send_cannot_change_recipient(self) -> None:
        self.send_email.side_effect = HTTPException(409, 'gestoria_send_uncertain')
        with self.assertRaises(HTTPException):
            service.send(self.body)
        self.body.email = 'different@example.com'
        with self.assertRaises(HTTPException) as error:
            service.send(self.body)
        self.assertEqual(error.exception.detail, 'gestoria_pending_send')
        self.send_email.assert_called_once()

    def test_expired_idempotency_window_requires_reconciliation(self) -> None:
        email = mailer.make_email('sender@example.com', self.body.email, [self.received], [])
        pending = PendingSend(id=uuid4(), created_at=datetime.now(timezone.utc) - timedelta(days=1), received_ids=[self.received.id], issued_ids=[], email=email)
        self.cache[service.PENDING_KEY] = pending.model_dump_json()
        with self.assertRaises(HTTPException) as error:
            service.send(self.body)
        self.assertEqual(error.exception.detail, 'gestoria_send_expired')
        self.send_email.assert_not_called()

    def test_large_selections_split_and_each_batch_marks_only_its_own_invoices(self) -> None:
        with patch('gestoria.mailer.MAX_ATTACHMENTS_SIZE', 15):
            self.assertEqual(service.send(self.body).sent, 2)
        self.assertEqual(self.send_email.call_count, 2)
        self.assertEqual([call.args for call in self.mark_sent.call_args_list], [([self.received.id], []), ([], [self.issued.id])])

    def test_partial_failure_retry_does_not_resend_finished_batches(self) -> None:
        self.send_email.side_effect = [None, HTTPException(409, 'gestoria_send_uncertain'), None]
        with patch('gestoria.mailer.MAX_ATTACHMENTS_SIZE', 15):
            with self.assertRaises(HTTPException):
                service.send(self.body)
            self.assertEqual(service.send(self.body).sent, 1)
        self.assertEqual(self.send_email.call_args_list[1], self.send_email.call_args_list[2])
        self.assertEqual(len(self.available), 0)


class GestoriaMailerTests(TestCase):
    def test_resend_request_contains_pdf_attachments_and_idempotency_key(self) -> None:
        payload = mailer.make_email('sender@example.com', 'gestoria@example.com', [invoice()], [Attachment(filename='invoice.pdf', content='JVBERg==')])
        with patch('gestoria.mailer.httpx.post', return_value=httpx.Response(200, json={'id': 'resend-id'})) as post:
            mailer.send_email(payload, 'test-secret', 'send-id')
        self.assertEqual(post.call_args.args[0], 'https://api.resend.com/emails')
        options = post.call_args.kwargs
        self.assertEqual(options['headers'], {'Authorization': 'Bearer test-secret', 'Idempotency-Key': 'send-id'})
        self.assertEqual(options['json']['from'], 'sender@example.com')
        self.assertEqual(options['json']['attachments'][0]['content'], 'JVBERg==')

    def test_missing_configuration_fails_only_when_sending(self) -> None:
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(HTTPException) as error:
            mailer.configuration()
        self.assertEqual(error.exception.detail, 'gestoria_not_configured')

    def test_oversized_single_pdf_is_not_sent(self) -> None:
        with patch('gestoria.mailer.MAX_ATTACHMENTS_SIZE', 1), patch('gestoria.mailer.download_file', return_value=b'%PDF'), self.assertRaises(HTTPException) as error:
            list(mailer.batches([invoice()], lambda: None))
        self.assertEqual(error.exception.detail, 'gestoria_file_too_large')
