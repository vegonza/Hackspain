import unittest

import httpx2
from openai import PermissionDeniedError

from shared.retries import RetryState, record_failure


class ProviderErrorTests(unittest.TestCase):
    def test_key_limit_has_safe_actionable_error_and_no_automatic_retry(self) -> None:
        error = PermissionDeniedError(
            'Key limit exceeded',
            response=httpx2.Response(403, request=httpx2.Request('POST', 'https://openrouter.ai/api/v1/chat/completions')),
            body={'message': 'Key limit exceeded (total limit). Manage it using https://openrouter.ai/workspaces/default/keys/private-id', 'code': 403},
        )
        state = record_failure(RetryState(attempts=1), error)
        self.assertEqual(state.last_error, 'openrouter_key_limit_exceeded')
        self.assertTrue(state.failed)
        self.assertIsNone(state.next_attempt)
        self.assertNotIn('private-id', state.model_dump_json())

    def test_other_permission_errors_are_not_mislabeled_as_spending_limits(self) -> None:
        error = PermissionDeniedError(
            'Provider denied access',
            response=httpx2.Response(403, request=httpx2.Request('POST', 'https://openrouter.ai/api/v1/chat/completions')),
            body={'message': 'Provider denied access', 'code': 403},
        )
        state = record_failure(RetryState(attempts=1), error)
        self.assertEqual(state.last_error, 'PermissionDeniedError (HTTP 403)')
        self.assertTrue(state.failed)
        self.assertIsNone(state.next_attempt)
