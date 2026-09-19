import unittest
from unittest.mock import patch

from erp.rate_limit import RateLimiter


class RateLimiterTests(unittest.TestCase):
    def test_requests_are_spaced_by_one_ninth_of_a_second(self) -> None:
        with patch('erp.rate_limit.monotonic', side_effect=[10, 10, 10, 10 + 1 / 9, 10 + 1 / 9, 10 + 2 / 9]):
            with patch('erp.rate_limit.sleep') as sleep:
                limiter = RateLimiter()
                limiter.wait()
                sleep.assert_not_called()
                limiter.wait()
                limiter.wait()
        self.assertEqual(sleep.call_count, 2)
        for call in sleep.call_args_list:
            self.assertAlmostEqual(call.args[0], 1 / 9)

    def test_elapsed_time_does_not_create_burst_credit(self) -> None:
        with patch('erp.rate_limit.monotonic', side_effect=[10, 10, 20, 20, 20, 20 + 1 / 9]):
            with patch('erp.rate_limit.sleep') as sleep:
                limiter = RateLimiter()
                limiter.wait()
                limiter.wait()
                sleep.assert_not_called()
                limiter.wait()
        self.assertEqual(sleep.call_count, 1)
        self.assertAlmostEqual(sleep.call_args.args[0], 1 / 9)
