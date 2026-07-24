import json
from datetime import timedelta
from secrets import token_urlsafe
from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APITestCase

from clinics.models import Clinic
from community.models import Post
from messaging.models import Message
from pets.models import Pet
from users.abuse import record_abuse_signal
from users.models import AccountSanction, AbuseSignal, User
from users.sanctions import sanction_error_payload
from users.verification import apply_verification_status


class FinalRegressionCoverageTests(APITestCase):
    """Protege los flujos más sensibles antes del cierre de VetPaw."""

    password = 'VetPaw-Pruebas-2026!'

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user(
            username='final-admin',
            email='final-admin@vetpaw.test',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
            is_staff=True,
        )
        self.owner = User.objects.create_user(
            username='final-owner',
            email='final-owner@vetpaw.test',
            password=self.password,
            role='owner',
            is_approved=True,
        )

    def tearDown(self):
        cache.clear()

    def _clinic_user(self, *, username='final-clinic', approved=True):
        user = User.objects.create_user(
            username=username,
            email=f'{username}@vetpaw.test',
            password=self.password,
            role='clinic',
            is_approved=approved,
        )
        clinic = Clinic.objects.create(
            owner=user,
            name=f'Veterinaria {username}',
            address='Calle VetPaw 123',
            province='Buenos Aires',
            locality='Moreno',
            latitude=-34.63,
            longitude=-58.79,
            plan_status=Clinic.PLAN_INACTIVE,
        )
        return user, clinic

    def test_owner_registration_forces_owner_role_and_auto_approves(self):
        response = self.client.post(
            '/api/users/register/',
            {
                'username': 'new-owner-final',
                'email': 'new-owner-final@vetpaw.test',
                'password': self.password,
                'password2': self.password,
                'role': 'clinic',
                'first_name': 'Nueva',
                'last_name': 'Dueña',
            },
            format='json',
            REMOTE_ADDR='198.51.100.10',
        )
        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(username='new-owner-final')
        self.assertEqual(user.role, 'owner')
        self.assertTrue(user.is_approved)
        self.assertEqual(
            user.professional_verification_status,
            User.VERIFICATION_NOT_APPLICABLE,
        )

        login = self.client.post(
            '/api/users/login/',
            {'username': user.username, 'password': self.password},
            format='json',
        )
        self.assertEqual(login.status_code, 200, login.data)
        self.assertIn('access', login.data)

    @patch('clinics.geocoding.get_coordinates', return_value=(None, None))
    def test_clinic_registration_creates_pending_inactive_profile_and_blocks_login(self, _geocode):
        response = self.client.post(
            '/api/users/register-clinic/',
            {
                'username': 'registered-clinic-final',
                'email': 'registered-clinic-final@vetpaw.test',
                'password': self.password,
                'password2': self.password,
                'clinic_name': 'Veterinaria Registro Final',
                'clinic_address': 'Calle Registro 456',
                'clinic_province': 'Buenos Aires',
                'clinic_locality': 'Moreno',
                'clinic_phone': '1111111111',
                'clinic_services': ['Consulta general'],
            },
            format='json',
            REMOTE_ADDR='198.51.100.11',
        )
        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(username='registered-clinic-final')
        clinic = Clinic.objects.get(owner=user)
        self.assertEqual(user.role, 'clinic')
        self.assertFalse(user.is_approved)
        self.assertEqual(user.professional_verification_status, User.VERIFICATION_PENDING)
        self.assertEqual(clinic.plan_status, Clinic.PLAN_INACTIVE)
        self.assertFalse(clinic.can_use_clinical_tools)

        login = self.client.post(
            '/api/users/login/',
            {'username': user.username, 'password': self.password},
            format='json',
        )
        self.assertEqual(login.status_code, 400, login.data)
        self.assertIn('pendiente', str(login.data).lower())

    def test_profile_update_cannot_change_role_or_administrative_flags(self):
        self.client.force_authenticate(self.owner)
        response = self.client.patch(
            '/api/users/profile/',
            {
                'role': 'clinic',
                'is_approved': False,
                'is_staff': True,
                'is_superuser': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.role, 'owner')
        self.assertTrue(self.owner.is_approved)
        self.assertFalse(self.owner.is_staff)
        self.assertFalse(self.owner.is_superuser)
        self.assertEqual(response.data['role'], 'owner')

    def test_approval_allows_login_but_does_not_activate_plan_or_verification(self):
        user, clinic = self._clinic_user(username='approved-no-plan', approved=False)
        user.is_approved = True
        user.save(update_fields=['is_approved'])

        login = self.client.post(
            '/api/users/login/',
            {'username': user.username, 'password': self.password},
            format='json',
        )
        self.assertEqual(login.status_code, 200, login.data)
        user.refresh_from_db()
        clinic.refresh_from_db()
        self.assertEqual(user.professional_verification_status, User.VERIFICATION_PENDING)
        self.assertEqual(clinic.plan_status, Clinic.PLAN_INACTIVE)
        self.assertFalse(clinic.can_use_clinical_tools)

    def test_verification_does_not_activate_clinic_plan_or_appointments(self):
        user, clinic = self._clinic_user(username='verified-no-plan')
        apply_verification_status(
            user=user,
            target_status=User.VERIFICATION_VERIFIED,
            public_note='Identidad profesional comprobada.',
            internal_note='Documentación revisada.',
            decided_by=self.admin,
        )
        user.refresh_from_db()
        clinic.refresh_from_db()
        self.assertTrue(user.is_professionally_verified)
        self.assertEqual(clinic.plan_status, Clinic.PLAN_INACTIVE)
        self.assertFalse(clinic.has_active_plan)
        self.assertFalse(clinic.can_receive_appointments)

    def test_professional_profile_never_exposes_internal_verification_note(self):
        user, _clinic = self._clinic_user(username='private-verification-note')
        secret_note = 'NOTA INTERNA CONFIDENCIAL 8842'
        apply_verification_status(
            user=user,
            target_status=User.VERIFICATION_VERIFIED,
            public_note='Perfil verificado por VetPaw.',
            internal_note=secret_note,
            decided_by=self.admin,
        )
        self.client.force_authenticate(user)
        response = self.client.get('/api/users/profile/')
        self.assertEqual(response.status_code, 200, response.data)
        verification = response.data['professional_verification']
        self.assertTrue(verification['is_verified'])
        self.assertNotIn('latest_internal_note', verification)
        self.assertNotIn(secret_note, json.dumps(response.data, default=str))

    def test_sanction_payload_hides_internal_note_and_preserves_user_data(self):
        pet = Pet.objects.create(
            owner=self.owner,
            name='Luna Conservada',
            species='dog',
            sex='female',
        )
        post = Post.objects.create(
            created_by=self.owner,
            pet=pet,
            text='Esta publicación debe conservarse.',
        )
        message = Message.objects.create(
            sender=self.owner,
            recipient=self.admin,
            content='Este mensaje también debe conservarse.',
        )
        sanction = AccountSanction.objects.create(
            user=self.owner,
            kind=AccountSanction.KIND_SUSPENSION,
            reason='Motivo visible para la persona.',
            internal_note='Nota privada del administrador.',
            starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(days=3),
            applied_by=self.admin,
        )
        payload = sanction_error_payload(sanction)
        self.assertNotIn('internal_note', payload['account_sanction'])
        self.assertEqual(payload['account_sanction']['reason'], sanction.reason)
        self.assertTrue(Pet.objects.filter(pk=pet.pk).exists())
        self.assertTrue(Post.objects.filter(pk=post.pk).exists())
        self.assertTrue(Message.objects.filter(pk=message.pk).exists())

    def test_password_reset_request_does_not_reveal_registered_emails(self):
        mail.outbox.clear()
        existing = self.client.post(
            '/api/users/password-reset/',
            {'email': self.owner.email},
            format='json',
        )
        missing = self.client.post(
            '/api/users/password-reset/',
            {'email': 'missing-user@vetpaw.test'},
            format='json',
        )
        self.assertEqual(existing.status_code, 200, existing.data)
        self.assertEqual(missing.status_code, 200, missing.data)
        self.assertEqual(existing.data, missing.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.owner.email])

    def test_valid_password_reset_changes_credentials_and_invalidates_old_password(self):
        uid = urlsafe_base64_encode(force_bytes(self.owner.pk))
        token = default_token_generator.make_token(self.owner)
        new_password = 'VetPaw-Nueva-2026!'
        response = self.client.post(
            f'/api/users/password-reset-confirm/{uid}/{token}/',
            {'password': new_password, 'password2': new_password},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)

        old_login = self.client.post(
            '/api/users/login/',
            {'username': self.owner.username, 'password': self.password},
            format='json',
        )
        new_login = self.client.post(
            '/api/users/login/',
            {'username': self.owner.username, 'password': new_password},
            format='json',
        )
        self.assertEqual(old_login.status_code, 401, old_login.data)
        self.assertEqual(new_login.status_code, 200, new_login.data)

    def test_admin_statistics_count_messages_without_exposing_private_content(self):
        secret_message = 'MENSAJE PRIVADO QUE NO DEBE APARECER 1947'
        Message.objects.create(
            sender=self.owner,
            recipient=self.admin,
            content=secret_message,
        )
        self.client.force_authenticate(self.admin)
        response = self.client.get('/api/users/admin-panel/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['interaction_stats']['community']['messages_total'], 1)
        self.assertNotIn(secret_message, json.dumps(response.data, default=str))

    def test_abuse_signals_aggregate_without_automatic_sanction(self):
        for occurrence in range(3):
            signal = record_abuse_signal(
                user=self.owner,
                category=AbuseSignal.CATEGORY_DUPLICATE_CONTENT,
                action_key='post',
                severity=AbuseSignal.SEVERITY_HIGH,
                fingerprint='final-regression-fingerprint',
                content='Contenido repetido de prueba.',
                details={'occurrence': occurrence + 1},
            )
        signal.refresh_from_db()
        self.assertEqual(AbuseSignal.objects.filter(user=self.owner).count(), 1)
        self.assertEqual(signal.occurrences, 3)
        self.assertEqual(signal.status, AbuseSignal.STATUS_PENDING)
        self.assertFalse(AccountSanction.objects.filter(user=self.owner).exists())
