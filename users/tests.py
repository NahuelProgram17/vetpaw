import importlib
from datetime import datetime, timezone as dt_timezone

from django.test import SimpleTestCase

from .admin_panel_views import format_local_datetime


class AdminPanelTimezoneTests(SimpleTestCase):
    def test_formats_utc_time_as_argentina_time(self):
        value = datetime(2026, 7, 19, 14, 54, tzinfo=dt_timezone.utc)
        self.assertEqual(format_local_datetime(value), '19/07/2026 11:54')

from secrets import token_urlsafe

from django.apps import apps as django_apps
from django.contrib.auth.models import Group
from rest_framework.test import APITestCase

from .models import User


class AdministrativePermissionTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='regular_owner',
            email='regular@example.com',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
        )
        self.staff = User.objects.create_user(
            username='staff_admin',
            email='staff@example.com',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
            is_staff=True,
        )
        self.group_admin = User.objects.create_user(
            username='group_admin',
            email='groupadmin@example.com',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
        )
        admin_group, _ = Group.objects.get_or_create(name='vetpaw_admins')
        self.group_admin.groups.add(admin_group)
        self.pending_clinic = User.objects.create_user(
            username='pending_clinic',
            email='clinic@example.com',
            password=token_urlsafe(24),
            role='clinic',
            is_approved=False,
        )

    def test_profile_exposes_permission_flags(self):
        self.client.force_authenticate(self.group_admin)
        response = self.client.get('/api/users/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['can_access_admin'])
        self.assertTrue(response.data['can_moderate_community'])

        self.client.force_authenticate(self.owner)
        response = self.client.get('/api/users/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['can_access_admin'])
        self.assertFalse(response.data['can_moderate_community'])

    def test_regular_user_cannot_open_admin_panel_or_approve_clinic(self):
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get('/api/users/admin-panel/').status_code, 403)
        self.assertEqual(
            self.client.post(f'/api/users/admin/approve-clinic/{self.pending_clinic.id}/').status_code,
            403,
        )

    def test_staff_or_admin_group_can_approve_clinic(self):
        self.client.force_authenticate(self.group_admin)
        response = self.client.post(f'/api/users/admin/approve-clinic/{self.pending_clinic.id}/')
        self.assertEqual(response.status_code, 200)
        self.pending_clinic.refresh_from_db()
        self.assertTrue(self.pending_clinic.is_approved)
    def test_permission_group_migration_preserves_legacy_admin_access(self):
        legacy = User.objects.create_user(
            username='jaime17',
            email='legacy-admin@example.com',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
        )
        migration = importlib.import_module('users.migrations.0009_create_vetpaw_permission_groups')
        migration.create_permission_groups(django_apps, None)
        legacy.refresh_from_db()
        self.assertTrue(legacy.groups.filter(name='vetpaw_admins').exists())
        self.assertTrue(legacy.groups.filter(name='community_moderators').exists())
