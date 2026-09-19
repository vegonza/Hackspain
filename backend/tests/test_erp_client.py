import unittest
from unittest.mock import patch
from decimal import Decimal

import httpx

from erp.client import ErpClient
from erp.errors import ErpProtocolError, ErpResponseError


ENTRY = '''<?xml version="1.0" encoding="ISO-8859-1"?>
<respuesta><asientos><asiento><id>AS-1</id><proveedor>Peña</proveedor>
<nif>B12345678</nif><pedido>PO-1</pedido><estado>PENDIENTE</estado>
<fecha>12/01/2026</fecha><importe>1.234,56</importe>
</asiento></asientos></respuesta>'''.encode('iso-8859-1')


def session(token: str = 'token-1') -> httpx.Response:
    return httpx.Response(200, text=f'<sesion><token>{token}</token></sesion>')


def error(code: str, status: int) -> httpx.Response:
    return httpx.Response(status, text=f'<error><codigo>{code}</codigo><mensaje>Error</mensaje></error>')


class ErpClientTests(unittest.TestCase):
    def setUp(self) -> None:
        limiter = patch('erp.client.RateLimiter.wait')
        limiter.start()
        self.addCleanup(limiter.stop)

    def client(self, responses: list[httpx.Response | httpx.TransportError]) -> ErpClient:
        self.requests: list[httpx.Request] = []

        def handle(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            result = responses.pop(0)
            if isinstance(result, httpx.TransportError):
                raise result
            return result

        return ErpClient('http://erp:8009', 'user', 'p&ss', transport=httpx.MockTransport(handle))

    def test_login_encoding_token_reuse_and_entry_parsing(self) -> None:
        with self.client([session(), httpx.Response(200, content=ENTRY), httpx.Response(200, content=ENTRY)]) as client:
            entry = client.get_entry('AS-1')
            client.get_entry('AS-1')
        self.assertEqual(entry.amount, Decimal('1234.56'))
        self.assertEqual(entry.supplier_id, 'Peña')
        self.assertEqual(self.requests[0].method, 'POST')
        self.assertEqual(self.requests[0].content, b'usuario=user&clave=p%26ss')
        self.assertNotIn('X-ERP-Token', self.requests[0].headers)
        for request in self.requests[1:]:
            self.assertEqual(request.headers['X-ERP-Token'], 'token-1')
            self.assertEqual(request.url.query, b'')

    def test_expired_session_is_renewed_and_same_request_repeated(self) -> None:
        with self.client([session(), error('SES-401', 401), session('token-2'), httpx.Response(200, content=ENTRY)]) as client:
            client.get_entry('AS-1')
        self.assertEqual(self.requests[1].url, self.requests[3].url)
        self.assertEqual(self.requests[3].headers['X-ERP-Token'], 'token-2')

    def test_repeated_session_rejection_stops(self) -> None:
        with self.client([session(), error('SES-401', 401), session(), error('SES-401', 401)]) as client:
            with self.assertRaises(ErpResponseError):
                client.get_entry('AS-1')
        self.assertEqual(len(self.requests), 4)

    def test_invalid_credentials_are_not_retried(self) -> None:
        with self.client([error('SES-401', 401)]) as client:
            with self.assertRaises(ErpResponseError):
                client.get_entry('AS-1')
        self.assertEqual(len(self.requests), 1)

    def test_erp_errors_retain_code_status_and_retry_after(self) -> None:
        for code, status in (('ERP-404', 404), ('ERP-400', 400)):
            with self.subTest(code=code):
                response = error(code, status)
                response.headers['Retry-After'] = '42'
                with self.client([session(), response]) as client:
                    with self.assertRaises(ErpResponseError) as caught:
                        client.get_entry('AS-1')
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(caught.exception.status, status)
                self.assertEqual(caught.exception.retry_after, '42')
                self.assertEqual(len(self.requests), 2)

    def test_ora_recovers_with_same_session_and_request(self) -> None:
        for failures in (1, 2):
            responses = [session()] + [error('ORA-00600', 500) for _ in range(failures)]
            responses.append(httpx.Response(200, content=ENTRY))
            with self.subTest(failures=failures), self.client(responses) as client:
                with self.assertLogs('app', level='WARNING') as logs:
                    entry = client.get_entry('AS-1')
            self.assertEqual(entry.entry_id, 'AS-1')
            self.assertEqual(len(self.requests), failures + 2)
            for request in self.requests[1:]:
                self.assertEqual(request.method, 'GET')
                self.assertEqual(request.url, self.requests[1].url)
                self.assertEqual(request.headers['X-ERP-Token'], 'token-1')
            self.assertEqual(sum('Retrying' in line for line in logs.output), failures)

    def test_ora_stops_after_three_attempts_and_preserves_last_error(self) -> None:
        responses = [session()] + [error('ORA-00600', 500) for _ in range(3)]
        with self.client(responses) as client:
            with self.assertLogs('app', level='WARNING') as logs:
                with self.assertRaises(ErpResponseError) as caught:
                    client.get_entry('AS-1')
        self.assertEqual(caught.exception.code, 'ORA-00600')
        self.assertEqual(caught.exception.status, 500)
        self.assertEqual(len(self.requests), 4)
        self.assertEqual(sum('Retrying' in line for line in logs.output), 2)

    def test_session_renewal_and_ora_share_three_query_attempts(self) -> None:
        responses = [session(), error('SES-401', 401), session('token-2'),
                     error('ORA-00600', 500), httpx.Response(200, content=ENTRY)]
        with self.client(responses) as client:
            self.assertEqual(client.get_entry('AS-1').entry_id, 'AS-1')
        self.assertEqual(len(self.requests), 5)
        self.assertEqual(self.requests[-1].headers['X-ERP-Token'], 'token-2')
        responses = [session(), error('ORA-00600', 500), error('SES-401', 401),
                     session('token-2'), error('ORA-00600', 500)]
        with self.client(responses) as client:
            with self.assertRaises(ErpResponseError):
                client.get_entry('AS-1')
        self.assertEqual(len(self.requests), 5)

    def test_rate_limit_waits_before_repeating_login_or_query(self) -> None:
        for during_login in (True, False):
            limited = error('ERP-429', 429)
            limited.headers['Retry-After'] = '42'
            responses = [limited, session()] if during_login else [session(), limited]
            responses.append(httpx.Response(200, content=ENTRY))
            with self.subTest(during_login=during_login), self.client(responses) as client:
                def check_wait(seconds: int) -> None:
                    self.assertEqual(seconds, 42)
                    self.assertEqual(len(self.requests), 1 if during_login else 2)
                with patch('erp.client.time.sleep', side_effect=check_wait) as sleep:
                    self.assertEqual(client.get_entry('AS-1').entry_id, 'AS-1')
                sleep.assert_called_once_with(42)
            first, repeated = self.requests[:2] if during_login else self.requests[1:]
            self.assertEqual(first.url, repeated.url)
            self.assertEqual(first.content, repeated.content)
            self.assertEqual(first.headers, repeated.headers)

    def test_rate_limit_stops_without_sleeping_after_last_attempt(self) -> None:
        for during_login in (True, False):
            responses = [] if during_login else [session()]
            for delay in ('1', '2', '3'):
                limited = error('ERP-429', 429)
                limited.headers['Retry-After'] = delay
                responses.append(limited)
            with self.subTest(during_login=during_login), self.client(responses) as client:
                with patch('erp.client.time.sleep') as sleep:
                    with self.assertRaises(ErpResponseError) as caught:
                        client.get_entry('AS-1')
                self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])
            self.assertEqual(caught.exception.code, 'ERP-429')
            self.assertEqual(caught.exception.retry_after, '3')
            self.assertEqual(len(self.requests), 3 if during_login else 4)

    def test_invalid_retry_after_fails_without_guessing_a_delay(self) -> None:
        for header in (None, '', '-1', 'NaN', '1.5'):
            limited = error('ERP-429', 429)
            if header is not None:
                limited.headers['Retry-After'] = header
            with self.subTest(header=header), self.client([session(), limited]) as client:
                with patch('erp.client.time.sleep') as sleep:
                    with self.assertRaises(ErpProtocolError):
                        client.get_entry('AS-1')
                sleep.assert_not_called()
            self.assertEqual(len(self.requests), 2)

    def test_rate_limit_and_ora_share_query_attempt_budget(self) -> None:
        limited = error('ERP-429', 429)
        limited.headers['Retry-After'] = '1'
        with self.client([session(), limited, error('ORA-00600', 500), limited]) as client:
            with patch('erp.client.time.sleep') as sleep:
                with self.assertRaises(ErpResponseError) as caught:
                    client.get_entry('AS-1')
            sleep.assert_called_once_with(1)
        self.assertEqual(caught.exception.code, 'ERP-429')
        self.assertEqual(len(self.requests), 4)

    def test_invalid_login_xml_and_missing_token(self) -> None:
        for body in ('<sesion>', '<sesion/>', '<sesion><token> </token></sesion>', '<other><token>x</token></other>'):
            with self.subTest(body=body), self.client([httpx.Response(200, text=body) for _ in range(3)]) as client:
                with self.assertRaises(ErpProtocolError):
                    client.get_entry('AS-1')

    def test_invalid_entry_response_is_not_silently_accepted(self) -> None:
        for body in (b'<respuesta>', b'<respuesta/>', ENTRY.replace(b'AS-1', b'AS-2'), b'<error/>'):
            with self.subTest(body=body), self.client([session()] + [httpx.Response(200, content=body) for _ in range(3)]) as client:
                with self.assertRaises(ErpProtocolError):
                    client.get_entry('AS-1')

    def test_redirect_is_not_followed(self) -> None:
        redirect = httpx.Response(302, headers={'Location': 'http://elsewhere/'}, text='<redirect/>')
        with self.client([session(), redirect]) as client:
            with self.assertRaises(httpx.HTTPStatusError):
                client.get_entry('AS-1')
        self.assertEqual(len(self.requests), 2)

    def test_network_timeout_is_propagated_and_transport_closed(self) -> None:
        class TimeoutTransport(httpx.BaseTransport):
            closed = False

            def handle_request(self, request: httpx.Request) -> httpx.Response:
                raise httpx.ConnectTimeout('Timed out', request=request)

            def close(self) -> None:
                self.closed = True

        transport = TimeoutTransport()
        with patch('erp.client.time.sleep'), self.assertRaises(httpx.ConnectTimeout):
            with ErpClient('http://erp:8009', 'user', 'password', transport=transport) as client:
                client.get_entry('AS-1')
        self.assertTrue(transport.closed)

    def test_transient_network_errors_recover_with_backoff(self) -> None:
        for during_login in (True, False):
            for failure in (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError,
                            httpx.ReadError, httpx.WriteError, httpx.RemoteProtocolError):
                responses: list[httpx.Response | httpx.TransportError] = [] if during_login else [session()]
                responses.extend([failure('test'), failure('test')])
                if during_login:
                    responses.append(session())
                responses.append(httpx.Response(200, content=ENTRY))
                with self.subTest(login=during_login, failure=failure), self.client(responses) as client:
                    with patch('erp.client.time.sleep') as sleep:
                        self.assertEqual(client.get_entry('AS-1').entry_id, 'AS-1')
                    self.assertEqual([call.args[0] for call in sleep.call_args_list], [0.5, 1.0])
                repeated = self.requests[:3] if during_login else self.requests[1:]
                self.assertEqual(len(repeated), 3)
                for request in repeated:
                    self.assertEqual(request.url, repeated[0].url)
                    self.assertEqual(request.headers, repeated[0].headers)
                    self.assertEqual(request.content, repeated[0].content)

    def test_network_exhaustion_preserves_last_error_without_extra_wait(self) -> None:
        for during_login in (True, False):
            last = httpx.ReadError('last failure')
            responses: list[httpx.Response | httpx.TransportError] = [] if during_login else [session()]
            responses.extend([httpx.ConnectTimeout('test'), httpx.ReadError('test'), last])
            with self.subTest(login=during_login), self.client(responses) as client:
                with patch('erp.client.time.sleep') as sleep:
                    with self.assertRaises(httpx.ReadError) as caught:
                        client.get_entry('AS-1')
                self.assertEqual([call.args[0] for call in sleep.call_args_list], [0.5, 1.0])
            self.assertIs(caught.exception, last)
            self.assertEqual(len(self.requests), 3 if during_login else 4)

    def test_network_and_rate_limit_share_attempt_budget(self) -> None:
        for during_login in (True, False):
            limited = error('ERP-429', 429)
            limited.headers['Retry-After'] = '2'
            responses: list[httpx.Response | httpx.TransportError] = [] if during_login else [session()]
            responses.extend([limited, httpx.ReadError('test'), httpx.ConnectTimeout('last')])
            with self.subTest(login=during_login), self.client(responses) as client:
                with patch('erp.client.time.sleep') as sleep:
                    with self.assertRaises(httpx.ConnectTimeout):
                        client.get_entry('AS-1')
                self.assertEqual([call.args[0] for call in sleep.call_args_list], [2, 1.0])
            self.assertEqual(len(self.requests), 3 if during_login else 4)

    def test_local_protocol_error_is_not_retried(self) -> None:
        with self.client([httpx.LocalProtocolError('invalid request')]) as client:
            with patch('erp.client.time.sleep') as sleep:
                with self.assertRaises(httpx.LocalProtocolError):
                    client.get_entry('AS-1')
            sleep.assert_not_called()
        self.assertEqual(len(self.requests), 1)

    def test_limiter_is_used_for_login_queries_and_retries(self) -> None:
        with self.client([session(), error('ORA-00600', 500), httpx.Response(200, content=ENTRY)]) as client:
            with patch('erp.client.RateLimiter.wait') as wait:
                client.get_entry('AS-1')
            self.assertEqual(wait.call_count, 3)

    def test_page_metadata_and_entries_are_parsed(self) -> None:
        body = ENTRY.replace(b'<respuesta>', b'<respuesta><meta><total>21</total><paginas>2</paginas><pagina>2</pagina><por_pagina>20</por_pagina></meta>')
        with self.client([session(), httpx.Response(200, content=body)]) as client:
            page = client.get_page(2)
        self.assertEqual((page.number, page.total_pages, page.total_entries, page.page_size), (2, 2, 21, 20))
        self.assertEqual(page.entries[0].supplier_id, 'Peña')
        self.assertEqual(page.entries[0].amount, Decimal('1234.56'))
        self.assertEqual(self.requests[-1].url.params['pagina'], '2')

    def test_page_retries_keep_requested_page(self) -> None:
        body = ENTRY.replace(b'<respuesta>', b'<respuesta><meta><total>21</total><paginas>2</paginas><pagina>2</pagina><por_pagina>20</por_pagina></meta>')
        with self.client([session(), error('ORA-00600', 500), httpx.Response(200, content=body)]) as client:
            self.assertEqual(client.get_page(2).number, 2)
        self.assertEqual(self.requests[1].url, self.requests[2].url)

    def test_page_rejects_missing_or_invalid_metadata_and_wrong_page(self) -> None:
        for meta in ('', '<total>1</total>',
                     '<total>x</total><paginas>1</paginas><pagina>1</pagina><por_pagina>20</por_pagina>',
                     '<total>1</total><paginas>0</paginas><pagina>1</pagina><por_pagina>20</por_pagina>',
                     '<total>21</total><paginas>2</paginas><pagina>2</pagina><por_pagina>20</por_pagina>'):
            body = ENTRY.replace(b'<respuesta>', f'<respuesta><meta>{meta}</meta>'.encode())
            with self.subTest(meta=meta), self.client([session()] + [httpx.Response(200, content=body) for _ in range(3)]) as client:
                with self.assertRaises(ErpProtocolError):
                    client.get_page(1)

    def test_empty_page_requires_an_entries_container(self) -> None:
        meta = '<meta><total>0</total><paginas>1</paginas><pagina>1</pagina><por_pagina>20</por_pagina></meta>'
        with self.client([session(), httpx.Response(200, text=f'<respuesta>{meta}<asientos/></respuesta>')]) as client:
            self.assertEqual(client.get_page(1).entries, [])
        with self.client([session()] + [httpx.Response(200, text=f'<respuesta>{meta}</respuesta>') for _ in range(3)]) as client:
            with self.assertRaises(ErpProtocolError):
                client.get_page(1)

    def test_page_keeps_duplicate_entries(self) -> None:
        body = ENTRY.replace(b'<respuesta>', b'<respuesta><meta><total>2</total><paginas>1</paginas><pagina>1</pagina><por_pagina>20</por_pagina></meta>')
        entry = body.split(b'<asientos>')[1].split(b'</asientos>')[0]
        body = body.replace(b'</asientos>', entry + b'</asientos>')
        with self.client([session(), httpx.Response(200, content=body)]) as client:
            page = client.get_page(1)
        self.assertEqual([entry.entry_id for entry in page.entries], ['AS-1', 'AS-1'])

    def test_out_of_range_page_propagates_erp_error(self) -> None:
        with self.client([session(), error('ERP-400', 400)]) as client:
            with self.assertRaises(ErpResponseError) as caught:
                client.get_page(99)
        self.assertEqual(caught.exception.code, 'ERP-400')
        self.assertEqual(len(self.requests), 2)

    def test_malformed_xml_recovers_in_login_and_entry_query(self) -> None:
        responses = [httpx.Response(200, content=b'<sesion>'), session(),
                     httpx.Response(200, content=b'<respuesta>'), httpx.Response(200, content=ENTRY)]
        with self.client(responses) as client, patch('erp.client.time.sleep') as sleep:
            self.assertEqual(client.get_entry('AS-1').entry_id, 'AS-1')
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [0.5, 0.5])
        self.assertEqual(len(self.requests), 4)

    def test_xml_and_network_errors_share_query_attempt_budget(self) -> None:
        responses = [session(), httpx.ReadError('interrupted'),
                     httpx.Response(200, content=b'<respuesta>'), httpx.Response(200, content=b'<respuesta>')]
        with self.client(responses) as client, patch('erp.client.time.sleep') as sleep:
            with self.assertRaises(ErpProtocolError):
                client.get_entry('AS-1')
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [0.5, 1.0])
        self.assertEqual(len(self.requests), 4)

    def test_status_is_anonymous_and_retries_malformed_xml(self) -> None:
        body = '<estado><version>2.3.1</version><activo_segundos>120</activo_segundos><asientos>516</asientos><actualizacion_cargada>NO</actualizacion_cargada></estado>'
        with self.client([httpx.Response(200, text='<estado/>'), httpx.Response(200, text=body)]) as client:
            with patch('erp.client.time.sleep') as sleep:
                status = client.get_status()
            sleep.assert_called_once_with(0.5)
        self.assertEqual(status.entry_count, 516)
        self.assertEqual(status.uptime_seconds, 120)
        self.assertFalse(status.update_loaded)
        for request in self.requests:
            self.assertEqual(request.url.path, '/erp/estado')
            self.assertNotIn('X-ERP-Token', request.headers)
