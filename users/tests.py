from datetime import datetime, timezone as dt_timezone

from django.test import SimpleTestCase

from .admin_panel_views import format_local_datetime


class AdminPanelTimezoneTests(SimpleTestCase):
    def test_formats_utc_time_as_argentina_time(self):
        value = datetime(2026, 7, 19, 14, 54, tzinfo=dt_timezone.utc)
        self.assertEqual(format_local_datetime(value), '19/07/2026 11:54')
