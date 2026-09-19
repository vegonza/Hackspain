import json
import os
import time
import unittest
from concurrent.futures import Future
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import httpx
from mistralai.client.errors import SDKError
from mistralai.client.models import OCRResponse
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from fastapi import HTTPException

from documents import queue, worker
from pipeline import ocr_2 as ocr_phase
from documents import router as document_router
from documents.repository import Document
from shared.retries import RetryState, read_retry, record_failure, retry_delay, retryable
from shared.usage import UsageEntry, UsageRecord
from usage import worker as usage_worker

class RetryTests(unittest.TestCase):
    """Use isolated Redis keys and mocked providers/Storage/Supabase."""

    def setUp(self) -> None:
        self.redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
        self.prefix = f"test:retries:{uuid4()}:"

    def tearDown(self) -> None:
        keys = list(self.redis.scan_iter(match=f"{self.prefix}*"))
        if keys:
            self.redis.delete(*keys)
        self.redis.close()

    def test_policy_and_retry_after(self) -> None:
        for status in (408, 429, 500, 502, 503, 504):
            self.assertTrue(retryable(SDKError('test', httpx.Response(status))))
        for status in (400, 401, 403, 404, 422):
            self.assertFalse(retryable(SDKError('test', httpx.Response(status))))
        self.assertFalse(retryable(ValueError('invalid PDF')))
        self.assertTrue(retryable(httpx.ConnectTimeout('timeout')))
        self.assertTrue(retryable(RedisConnectionError('unavailable')))
        error = SDKError('limited', httpx.Response(429, headers={'Retry-After': '30'}))
        self.assertGreaterEqual(retry_delay(error, 1), 30)
        date_error = SDKError('limited', httpx.Response(429, headers={'Retry-After': 'Tue, 01 Jan 2030 00:00:00 GMT'}))
        self.assertGreater(retry_delay(date_error, 1), 30)
        with patch('shared.retries.random.uniform', return_value=1):
            self.assertEqual([retry_delay(ConnectionError(), attempt) for attempt in range(1, 5)], [2, 4, 8, 16])
        self.assertTrue(record_failure(RetryState(attempts=5), ConnectionError()).failed)
        self.assertTrue(record_failure(RetryState(attempts=1), ValueError()).failed)

    def test_manual_document_retry_preserves_identity_and_prevents_double_enqueue(self) -> None:
        identifier = uuid4()
        retries, scheduled, ready = [self.prefix + name for name in ('state', 'scheduled', 'queue')]
        document = Document(id=identifier, name='test.pdf', sha256='a' * 64, created_at=datetime.now(timezone.utc), status='error')
        self.redis.hset(retries, str(identifier), RetryState(attempts=5, failed=True).model_dump_json())
        with patch.multiple(document_router, RETRIES=retries, SCHEDULED=scheduled, QUEUE=ready), patch.object(document_router, 'get_redis', return_value=self.redis), patch.object(document_router, 'read_document', return_value=document), patch.object(document_router, 'write_document'):
            result = document_router.retry_document(identifier)
            self.assertEqual(result.id, identifier)
            self.assertEqual(result.status, 'queued')
            self.assertEqual(self.redis.lrange(ready, 0, -1), [str(identifier)])
            self.assertFalse(self.redis.hexists(retries, str(identifier)))
            with self.assertRaises(HTTPException) as error:
                document_router.retry_document(identifier)
            self.assertEqual(error.exception.status_code, 409)
            self.assertEqual(self.redis.llen(ready), 1)

    def test_document_failure_is_scheduled_and_promoted_once(self) -> None:
        retries, scheduled, processing, ready = [self.prefix + name for name in ('state', 'scheduled', 'processing', 'queue')]
        identifier = 'doc'
        self.redis.hset(retries, identifier, RetryState(attempts=1).model_dump_json())
        self.redis.lpush(processing, identifier)
        future: Future[None] = Future()
        future.set_exception(httpx.ConnectTimeout('test'))
        active = {future: identifier}
        with patch.multiple(worker, RETRIES=retries, SCHEDULED=scheduled, PROCESSING=processing):
            worker.finish_jobs(self.redis, active, {future})
        self.assertEqual(active, {})
        self.assertEqual(self.redis.llen(processing), 0)
        self.assertGreater(self.redis.zscore(scheduled, identifier), time.time())
        with patch.multiple(queue, SCHEDULED=scheduled, QUEUE=ready), patch.object(queue, 'get_redis', return_value=self.redis):
            queue.promote_retries()
            self.assertEqual(self.redis.llen(ready), 0)
            self.redis.zadd(scheduled, {identifier: 0})
            queue.promote_retries()
            queue.promote_retries()
            self.assertEqual(self.redis.lrange(ready, 0, -1), [identifier])

    def test_usage_backoff_limit_and_manual_reset(self) -> None:
        outbox, retries = self.prefix + 'outbox', self.prefix + 'state'
        record = UsageRecord(provider='mistral', model='ocr', operation='ocr', document_id=str(uuid4()), document_name='test.pdf', usage=[UsageEntry(provider='mistral', model='ocr', cost=Decimal('0.004'), details={})])
        payload = record.model_dump_json()
        self.redis.hset(outbox, record.id, payload)
        with patch.multiple(usage_worker, RETRIES=retries, USAGE_OUTBOX=outbox), patch.object(usage_worker, 'save_usage', side_effect=httpx.ConnectTimeout('test')) as save:
            for attempt in range(1, 6):
                usage_worker.persist_pending(self.redis, record.id, payload)
                state = read_retry(self.redis, retries, record.id)
                self.assertEqual(state.attempts, attempt)
                usage_worker.persist_pending(self.redis, record.id, payload)
                self.assertEqual(save.call_count, attempt)
                if attempt < 5:
                    state.next_attempt = 0
                    self.redis.hset(retries, record.id, state.model_dump_json())
            self.assertTrue(state.failed)
            self.assertTrue(self.redis.hexists(outbox, record.id))
        self.redis.hdel(retries, record.id)
        with patch.multiple(usage_worker, RETRIES=retries, USAGE_OUTBOX=outbox), patch.object(usage_worker, 'save_usage') as save:
            usage_worker.persist_pending(self.redis, record.id, payload)
            save.assert_called_once()
            self.assertFalse(self.redis.hexists(outbox, record.id))
            self.assertFalse(self.redis.hexists(retries, record.id))

    def test_checkpoint_reuses_ocr_and_usage_id_after_storage_failure(self) -> None:
        response = OCRResponse.model_validate({'model': 'mistral-ocr-latest', 'pages': [{'index': 0, 'markdown': '![image](img)', 'images': [{'id': 'img', 'top_left_x': 0, 'top_left_y': 0, 'bottom_right_x': 10, 'bottom_right_y': 10, 'image_base64': 'aGVsbG8='}], 'dimensions': {'dpi': 200, 'height': 100, 'width': 100}}], 'usage_info': {'pages_processed': 1, 'doc_size_bytes': 20}})
        checkpoint = self.prefix + 'checkpoint'
        outbox = self.prefix + 'outbox'
        client = MagicMock()
        client.__enter__.return_value = client
        client.ocr.process.return_value = response
        with patch.object(ocr_phase, 'Mistral', return_value=client), patch.object(ocr_phase, 'get_redis', return_value=self.redis), patch('shared.usage.get_redis', return_value=self.redis), patch('shared.usage.USAGE_OUTBOX', outbox):
            ocr_phase.request_ocr(b'%PDF-test', 'test', 'test.pdf', checkpoint)
        saved = json.loads(self.redis.get(checkpoint))
        identifier = saved['usage']['id']
        cache = MagicMock()
        cache.__enter__.return_value = cache
        cache.get.return_value = json.dumps(saved)
        with patch.object(ocr_phase, 'get_redis', return_value=cache), patch.object(ocr_phase, 'request_ocr') as ocr, patch.object(ocr_phase, 'upload_file', side_effect=[httpx.ConnectTimeout('storage'), None, None, None]):
            with self.assertRaises(httpx.ConnectTimeout):
                ocr_phase.extract_markdown(b'%PDF-test', 'test', 'test.pdf')
            markdown, pages = ocr_phase.extract_markdown(b'%PDF-test', 'test', 'test.pdf')
            ocr.assert_not_called()
            self.assertEqual(pages, 1)
            self.assertIn('/api/documents/test/images/', markdown)
            self.assertTrue(all(call.args[1] == identifier for call in cache.hset.call_args_list))
        client.ocr.process.assert_called_once()
        self.assertIsNone(client.ocr.process.call_args.kwargs['retries'])


if __name__ == '__main__':
    unittest.main()
