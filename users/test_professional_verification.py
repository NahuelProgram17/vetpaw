from secrets import token_urlsafe

from rest_framework.test import APITestCase

from clinics.models import Clinic
from community.social_profiles import identity_for_target
from partners.models import BusinessProfile, ShelterProfile
from users.models import ProfessionalVerificationDecision, User
from users.serializers import UserSerializer


class ProfessionalVerificationAdministrationTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='verification-admin',
            email='verification-admin@vetpaw.test',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
            is_staff=True,
        )
        self.regular = User.objects.create_user(
            username='verification-owner',
            email='verification-owner@vetpaw.test',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
        )
        self.business_user = User.objects.create_user(
            username='verification-business',
            email='verification-business@vetpaw.test',
            password=token_urlsafe(24),
            role='business',
            is_approved=True,
            professional_verification_status=User.VERIFICATION_PENDING,
        )
        self.business = BusinessProfile.objects.create(
            owner=self.business_user,
            name='Patitas Shop',
            responsible_name='Ana Responsable',
            business_type=BusinessProfile.TYPE_PETSHOP,
            phone='1111111111',
            province='Buenos Aires',
            locality='Moreno',
            species=['dog', 'cat'],
        )
        self.pending_clinic_user = User.objects.create_user(
            username='verification-clinic',
            email='verification-clinic@vetpaw.test',
            password=token_urlsafe(24),
            role='clinic',
            is_approved=False,
            professional_verification_status=User.VERIFICATION_PENDING,
        )
        self.clinic = Clinic.objects.create(
            owner=self.pending_clinic_user,
            name='Clínica Confianza',
            address='Calle 123',
            province='Buenos Aires',
            locality='Moreno',
            latitude=-34.65,
            longitude=-58.79,
        )


    def test_new_professional_accounts_start_pending_even_outside_registration_view(self):
        user = User.objects.create_user(
            username='automatic-pending-shelter',
            email='automatic-pending-shelter@vetpaw.test',
            password=token_urlsafe(24),
            role='shelter',
            is_approved=False,
        )
        self.assertEqual(
            user.professional_verification_status,
            User.VERIFICATION_PENDING,
        )

    def test_regular_user_cannot_access_verification_panel(self):
        self.client.force_authenticate(self.regular)
        self.assertEqual(self.client.get('/api/users/admin/verifications/').status_code, 403)
        self.assertEqual(
            self.client.post(
                f'/api/users/admin/verifications/{self.business_user.id}/',
                {'action': 'verify'},
                format='json',
            ).status_code,
            403,
        )

    def test_admin_list_contains_only_professional_accounts(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get('/api/users/admin/verifications/')
        self.assertEqual(response.status_code, 200)
        returned_ids = {row['user_id'] for row in response.data['results']}
        self.assertIn(self.business_user.id, returned_ids)
        self.assertIn(self.pending_clinic_user.id, returned_ids)
        self.assertNotIn(self.regular.id, returned_ids)
        self.assertIn('pending', response.data['summary'])

    def test_unapproved_account_cannot_be_verified(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            f'/api/users/admin/verifications/{self.pending_clinic_user.id}/',
            {'action': 'verify'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('aprobar', response.data['error'].lower())
        self.pending_clinic_user.refresh_from_db()
        self.assertEqual(
            self.pending_clinic_user.professional_verification_status,
            User.VERIFICATION_PENDING,
        )

    def test_review_corrections_and_verification_create_history(self):
        self.client.force_authenticate(self.admin)

        review = self.client.post(
            f'/api/users/admin/verifications/{self.business_user.id}/',
            {
                'action': 'review',
                'internal_note': 'Revisar documentación comercial.',
            },
            format='json',
        )
        self.assertEqual(review.status_code, 200)
        self.assertEqual(review.data['verification']['status'], User.VERIFICATION_IN_REVIEW)

        corrections = self.client.post(
            f'/api/users/admin/verifications/{self.business_user.id}/',
            {
                'action': 'request_corrections',
                'public_note': 'Completá el domicilio y el teléfono.',
                'internal_note': 'Faltan datos públicos.',
            },
            format='json',
        )
        self.assertEqual(corrections.status_code, 200)
        self.assertEqual(corrections.data['verification']['status'], User.VERIFICATION_CORRECTIONS)

        verified = self.client.post(
            f'/api/users/admin/verifications/{self.business_user.id}/',
            {
                'action': 'verify',
                'public_note': 'Identidad y actividad revisadas por VetPaw.',
            },
            format='json',
        )
        self.assertEqual(verified.status_code, 200)
        self.assertTrue(verified.data['verification']['is_verified'])
        self.assertEqual(
            ProfessionalVerificationDecision.objects.filter(user=self.business_user).count(),
            3,
        )
        self.business_user.refresh_from_db()
        self.business.refresh_from_db()
        self.assertTrue(self.business_user.is_professionally_verified)
        self.assertTrue(self.business.is_verified)

    def test_corrections_rejection_and_withdrawal_require_visible_reason(self):
        self.client.force_authenticate(self.admin)
        for action in ('request_corrections', 'reject', 'withdraw'):
            response = self.client.post(
                f'/api/users/admin/verifications/{self.business_user.id}/',
                {'action': action},
                format='json',
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn('motivo', response.data['error'].lower())

    def test_withdraw_removes_public_badge_without_unapproving_account(self):
        self.business_user.professional_verification_status = User.VERIFICATION_VERIFIED
        self.business_user.save(update_fields=['professional_verification_status'])
        self.business.is_verified = True
        self.business.save(update_fields=['is_verified'])

        self.client.force_authenticate(self.admin)
        response = self.client.post(
            f'/api/users/admin/verifications/{self.business_user.id}/',
            {
                'action': 'withdraw',
                'public_note': 'La documentación dejó de estar vigente.',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.business_user.refresh_from_db()
        self.business.refresh_from_db()
        self.assertTrue(self.business_user.is_approved)
        self.assertFalse(self.business_user.is_professionally_verified)
        self.assertFalse(self.business.is_verified)
        self.assertFalse(identity_for_target('business', self.business)['verified'])

    def test_clinic_badge_is_independent_from_account_approval(self):
        self.pending_clinic_user.is_approved = True
        self.pending_clinic_user.save(update_fields=['is_approved'])
        self.assertFalse(identity_for_target('clinic', self.clinic)['verified'])

        self.client.force_authenticate(self.admin)
        response = self.client.post(
            f'/api/users/admin/verifications/{self.pending_clinic_user.id}/',
            {'action': 'verify'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.pending_clinic_user.refresh_from_db()
        self.assertTrue(identity_for_target('clinic', self.clinic)['verified'])

    def test_history_exposes_admin_notes_only_in_admin_endpoint(self):
        self.client.force_authenticate(self.admin)
        self.client.post(
            f'/api/users/admin/verifications/{self.business_user.id}/',
            {
                'action': 'review',
                'public_note': 'Estamos revisando tu perfil.',
                'internal_note': 'Documento observado por el administrador.',
            },
            format='json',
        )
        history = self.client.get(
            f'/api/users/admin/verifications/history/?user_id={self.business_user.id}'
        )
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.data['count'], 1)
        self.assertEqual(
            history.data['results'][0]['internal_note'],
            'Documento observado por el administrador.',
        )

        serialized = UserSerializer(self.business_user).data
        self.assertIn('professional_verification', serialized)
        self.assertNotIn(
            'internal_note',
            serialized['professional_verification'],
        )
        self.assertNotIn(
            'latest_internal_note',
            serialized['professional_verification'],
        )

    def test_owner_profile_has_no_professional_verification(self):
        data = UserSerializer(self.regular).data
        self.assertIsNone(data['professional_verification'])

    def test_business_and_shelter_legacy_flags_stay_synchronized(self):
        shelter_user = User.objects.create_user(
            username='verification-shelter',
            email='verification-shelter@vetpaw.test',
            password=token_urlsafe(24),
            role='shelter',
            is_approved=True,
            professional_verification_status=User.VERIFICATION_PENDING,
        )
        shelter = ShelterProfile.objects.create(
            owner=shelter_user,
            name='Refugio Huellitas',
            responsible_name='Luis Responsable',
            shelter_type=ShelterProfile.TYPE_SHELTER,
            phone='2222222222',
            province='Buenos Aires',
            locality='Moreno',
            species=['dog'],
        )
        self.client.force_authenticate(self.admin)
        verified = self.client.post(
            f'/api/users/admin/verifications/{shelter_user.id}/',
            {'action': 'verify'},
            format='json',
        )
        self.assertEqual(verified.status_code, 200)
        shelter.refresh_from_db()
        self.assertTrue(shelter.is_verified)

        rejected = self.client.post(
            f'/api/users/admin/verifications/{shelter_user.id}/',
            {
                'action': 'reject',
                'public_note': 'No se pudo validar la documentación.',
            },
            format='json',
        )
        self.assertEqual(rejected.status_code, 200)
        shelter.refresh_from_db()
        self.assertFalse(shelter.is_verified)

    def test_nonprofessional_account_cannot_receive_verification_action(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            f'/api/users/admin/verifications/{self.regular.id}/',
            {'action': 'verify'},
            format='json',
        )
        self.assertEqual(response.status_code, 404)
