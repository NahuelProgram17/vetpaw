from unittest.mock import patch

from django.db import DatabaseError
from django.test import override_settings
from rest_framework.test import APIRequestFactory, APITestCase

from vetpaw.exceptions import api_exception_handler


class ServiceResilienceTests(APITestCase):
    def test_health_endpoint_is_public_and_reports_database(self):
        response = self.client.get('/api/health/')

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['status'], 'ok')
        self.assertEqual(response.data['service'], 'vetpaw-api')
        self.assertEqual(response.data['database'], 'ok')
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response.data['request_id'], response['X-Request-ID'])
        self.assertEqual(len(response['X-Request-ID']), 32)

    @patch('vetpaw.health.connection.cursor', side_effect=DatabaseError('database unavailable'))
    def test_health_endpoint_reports_temporary_database_failure(self, _cursor):
        response = self.client.get('/api/health/')

        self.assertEqual(response.status_code, 503, response.data)
        self.assertEqual(response.data['status'], 'degraded')
        self.assertEqual(response.data['database'], 'unavailable')
        self.assertEqual(response['Retry-After'], '30')
        self.assertNotIn('database unavailable', str(response.data))

    def test_each_response_receives_a_different_request_id(self):
        first = self.client.get('/api/health/')
        second = self.client.get('/api/health/')

        self.assertNotEqual(first['X-Request-ID'], second['X-Request-ID'])

    @override_settings(DEBUG=False)
    def test_unknown_api_route_returns_a_safe_json_error(self):
        response = self.client.get('/api/route-that-does-not-exist/')

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(response.json()['code'], 'not_found')
        self.assertEqual(response.json()['request_id'], response['X-Request-ID'])

    def test_unexpected_api_error_does_not_expose_internal_details(self):
        request = APIRequestFactory().get('/api/test-error/')
        request.request_id = '0123456789abcdef0123456789abcdef'
        exception = RuntimeError('SECRET DATABASE INTERNAL DETAIL')

        response = api_exception_handler(exception, {'request': request})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data['code'], 'server_error')
        self.assertEqual(response.data['request_id'], request.request_id)
        self.assertNotIn('SECRET DATABASE INTERNAL DETAIL', str(response.data))
        self.assertEqual(response['Cache-Control'], 'no-store')
