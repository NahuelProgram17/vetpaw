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
from django.utils import timezone
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


class ClinicPlanAdministrationTests(APITestCase):
    def setUp(self):
        from clinics.models import Clinic

        self.admin = User.objects.create_user(
            username='plan-admin',
            email='plan-admin@vetpaw.test',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
            is_staff=True,
        )
        self.clinic_user = User.objects.create_user(
            username='plan-managed-clinic',
            email='plan-managed-clinic@vetpaw.test',
            password=token_urlsafe(24),
            role='clinic',
            is_approved=True,
        )
        self.clinic = Clinic.objects.create(
            owner=self.clinic_user,
            name='Veterinaria Administrada',
            address='Calle Admin 123',
            province='Buenos Aires',
            locality='Moreno',
            plan_status=Clinic.PLAN_INACTIVE,
        )
        self.client.force_authenticate(self.admin)

    def test_admin_can_approve_clinic_with_first_free_month_atomically(self):
        from clinics.models import Clinic

        self.clinic_user.is_approved = False
        self.clinic_user.save(update_fields=['is_approved'])
        response = self.client.post(
            f'/api/users/admin/clinic-plan/{self.clinic.id}/',
            {'action': 'approve_and_start_trial'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.clinic_user.refresh_from_db()
        self.clinic.refresh_from_db()
        self.assertTrue(self.clinic_user.is_approved)
        self.assertEqual(self.clinic.plan_status, Clinic.PLAN_TRIAL)
        self.assertTrue(self.clinic.trial_used)

    def test_admin_can_start_first_free_month(self):
        from clinics.models import Clinic

        response = self.client.post(
            f'/api/users/admin/clinic-plan/{self.clinic.id}/',
            {'action': 'start_trial'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.clinic.refresh_from_db()
        self.assertEqual(self.clinic.plan_status, Clinic.PLAN_TRIAL)
        self.assertTrue(self.clinic.trial_used)
        self.assertTrue(self.clinic.has_active_plan)
        self.assertIsNotNone(self.clinic.plan_ends_at)

    def test_admin_cannot_grant_trial_twice(self):
        self.clinic.start_free_trial()
        response = self.client.post(
            f'/api/users/admin/clinic-plan/{self.clinic.id}/',
            {'action': 'start_trial'},
            format='json',
        )
        self.assertEqual(response.status_code, 400, response.data)

    def test_admin_panel_lists_clinic_plan(self):
        response = self.client.get('/api/users/admin-panel/')
        self.assertEqual(response.status_code, 200, response.data)
        row = next(item for item in response.data['clinic_plans'] if item['clinic_id'] == self.clinic.id)
        self.assertEqual(row['plan_status'], 'inactive')
        self.assertFalse(row['trial_used'])


class AdminInteractionStatisticsTests(APITestCase):
    def setUp(self):
        from pets.models import Pet
        from community.models import Comment, PetFollow, Post, Reaction
        from messaging.models import Message
        from partners.models import BusinessProfile, ShelterProfile
        from adoptions.models import AdoptionAnimal, AdoptionApplication, HelpOffer
        from commerce.models import (
            BusinessInquiry,
            BusinessProfileView,
            BusinessReservation,
            CatalogItem,
        )

        self.admin = User.objects.create_user(
            username='stats-admin',
            email='stats-admin@vetpaw.test',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
            is_staff=True,
        )
        self.owner = User.objects.create_user(
            username='stats-owner',
            email='stats-owner@vetpaw.test',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
        )
        self.other_owner = User.objects.create_user(
            username='stats-follower',
            email='stats-follower@vetpaw.test',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
        )
        self.pet = Pet.objects.create(
            owner=self.owner,
            name='Luna Stats',
            species='dog',
            sex='female',
        )
        self.post = Post.objects.create(
            created_by=self.owner,
            pet=self.pet,
            text='Publicación para medir interacción.',
        )
        Reaction.objects.create(post=self.post, user=self.other_owner)
        Comment.objects.create(post=self.post, author=self.other_owner, text='Hermosa mascota')
        PetFollow.objects.create(follower=self.other_owner, pet=self.pet)
        Message.objects.create(sender=self.owner, recipient=self.other_owner, content='Hola desde VetPaw')

        shelter_user = User.objects.create_user(
            username='stats-shelter',
            email='stats-shelter@vetpaw.test',
            password=token_urlsafe(24),
            role='shelter',
            is_approved=True,
        )
        shelter = ShelterProfile.objects.create(
            owner=shelter_user,
            name='Refugio Stats',
            responsible_name='Responsable Stats',
            shelter_type='shelter',
            province='Buenos Aires',
            locality='Moreno',
        )
        animal = AdoptionAnimal.objects.create(
            shelter=shelter,
            name='Toby Stats',
            species='dog',
            story='Busca una familia responsable.',
            province='Buenos Aires',
            locality='Moreno',
        )
        AdoptionApplication.objects.create(
            animal=animal,
            applicant=self.owner,
            phone='1111111111',
            locality='Moreno',
            housing_type='Casa',
            motivation='Quiero brindarle un hogar.',
            accepts_requirements=True,
        )
        HelpOffer.objects.create(
            animal=animal,
            user=self.other_owner,
            help_type='food',
            message='Puedo colaborar con alimento.',
        )

        business_user = User.objects.create_user(
            username='stats-business',
            email='stats-business@vetpaw.test',
            password=token_urlsafe(24),
            role='business',
            is_approved=True,
        )
        business = BusinessProfile.objects.create(
            owner=business_user,
            name='Petshop Stats',
            responsible_name='Comerciante Stats',
            business_type='petshop',
            province='Buenos Aires',
            locality='Moreno',
        )
        service = CatalogItem.objects.create(
            business=business,
            item_type=CatalogItem.TYPE_SERVICE,
            title='Baño Stats',
            description='Servicio para mascotas.',
            price=1000,
            requires_booking=True,
            duration_minutes=30,
        )
        BusinessInquiry.objects.create(
            business=business,
            user=self.owner,
            catalog_item=service,
            content='Quisiera consultar disponibilidad.',
        )
        BusinessReservation.objects.create(
            business=business,
            user=self.owner,
            pet=self.pet,
            catalog_item=service,
            date=timezone.localdate(),
            start_time='10:00',
        )
        BusinessProfileView.objects.create(business=business, user=self.owner)

        self.client.force_authenticate(self.admin)

    def test_admin_panel_exposes_complete_interaction_statistics(self):
        response = self.client.get('/api/users/admin-panel/')
        self.assertEqual(response.status_code, 200, response.data)

        stats = response.data['interaction_stats']
        self.assertEqual(stats['community']['posts_total'], 1)
        self.assertEqual(stats['community']['paws_total'], 1)
        self.assertEqual(stats['community']['comments_total'], 1)
        self.assertEqual(stats['community']['follows_total'], 1)
        self.assertEqual(stats['community']['messages_total'], 1)
        self.assertGreaterEqual(stats['community']['active_users_week'], 2)

        self.assertEqual(stats['adoptions']['animals_total'], 1)
        self.assertEqual(stats['adoptions']['applications_total'], 1)
        self.assertEqual(stats['adoptions']['help_offers_total'], 1)

        self.assertEqual(stats['businesses']['inquiries_total'], 1)
        self.assertEqual(stats['businesses']['reservations_total'], 1)
        self.assertEqual(stats['businesses']['profile_views_total'], 1)

        self.assertEqual(len(stats['engagement_by_day']), 14)
        self.assertEqual(stats['top_community_posts'][0]['id'], self.post.id)
        self.assertTrue(any(row['profile_type'] == 'pet' for row in stats['top_profiles']))
        self.assertEqual(stats['top_businesses'][0]['name'], 'Petshop Stats')
        self.assertEqual(stats['top_shelters'][0]['name'], 'Refugio Stats')
