from datetime import timedelta
from secrets import token_urlsafe

from django.utils import timezone
from rest_framework.test import APITestCase

from appointments.models import Appointment
from community.models import Post
from pets.models import Pet
from users.models import User

from .models import Clinic, ClinicCampaign, ClinicSchedule


class ClinicCommunityStage81Tests(APITestCase):
    def setUp(self):
        self.clinic_user = User.objects.create_user(
            username='stage81-clinic',
            email='stage81-clinic@vetpaw.test',
            password=token_urlsafe(24),
            role='clinic',
            is_approved=True,
        )
        self.owner = User.objects.create_user(
            username='stage81-owner',
            email='stage81-owner@vetpaw.test',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
        )
        self.clinic = Clinic.objects.create(
            owner=self.clinic_user,
            name='Veterinaria Comunidad',
            address='Calle VetPaw 123',
            province='Buenos Aires',
            locality='Moreno',
            latitude=-34.6500,
            longitude=-58.7900,
            is_active=True,
            plan_status=Clinic.PLAN_ACTIVE,
        )
        ClinicSchedule.objects.create(
            clinic=self.clinic,
            working_days=[0, 1, 2, 3, 4, 5, 6],
            day_hours={str(day): {'open': '08:00', 'close': '20:00'} for day in range(7)},
        )
        self.pet = Pet.objects.create(
            owner=self.owner,
            name='Toby Stage 8.1',
            species='dog',
            sex='male',
        )
        self.starts_at = timezone.now() + timedelta(days=7)

    def _campaign_payload(self):
        return {
            'campaign_type': ClinicCampaign.TYPE_VACCINATION,
            'title': 'Vacunación antirrábica',
            'description': 'Jornada comunitaria informativa.',
            'starts_at': self.starts_at.isoformat(),
            'ends_at': (self.starts_at + timedelta(hours=4)).isoformat(),
            'location': 'Veterinaria Comunidad',
            'capacity': 10,
            'species': ['dog', 'cat'],
            'price': '0.00',
            'is_free': True,
            # Aunque un cliente viejo lo envíe, el backend lo ignora.
            'allow_booking': True,
            'is_active': True,
        }

    def test_clinic_can_create_and_publish_informative_campaign(self):
        self.client.force_authenticate(self.clinic_user)
        create_response = self.client.post(
            '/api/clinic-campaigns/',
            self._campaign_payload(),
            format='json',
        )
        self.assertEqual(create_response.status_code, 201, create_response.data)
        campaign = ClinicCampaign.objects.get(pk=create_response.data['id'])
        self.assertFalse(campaign.allow_booking)

        publish_response = self.client.post(
            f'/api/clinic-campaigns/{campaign.id}/publish/',
            {'text': 'Sumate a nuestra campaña de vacunación.'},
            format='json',
        )
        self.assertEqual(publish_response.status_code, 201, publish_response.data)
        post = Post.objects.get(related_clinic_campaign=campaign)
        self.assertEqual(post.clinic_content_type, Post.CLINIC_CONTENT_CAMPAIGN)
        self.assertFalse(publish_response.data['clinic_content']['can_request_appointment'])

    def test_owner_cannot_create_clinic_campaign(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post('/api/clinic-campaigns/', self._campaign_payload(), format='json')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ClinicCampaign.objects.exists())

    def test_community_post_cannot_generate_appointment(self):
        post = Post.objects.create(
            created_by=self.clinic_user,
            clinic=self.clinic,
            post_type=Post.TYPE_CLINIC,
            clinic_content_type=Post.CLINIC_CONTENT_NOTICE,
            text='Aviso importante de la veterinaria.',
            province=self.clinic.province,
            locality=self.clinic.locality,
        )
        self.client.force_authenticate(self.owner)
        response = self.client.post('/api/appointments/', {
            'pet': self.pet.id,
            'clinic': self.clinic.id,
            'source_post': post.id,
            'requested_date': (timezone.now() + timedelta(days=2)).isoformat(),
            'reason': 'Intento desde Comunidad',
            'appointment_type': 'control',
        }, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('Turnos', str(response.data))
        self.assertFalse(Appointment.objects.exists())

    def test_only_four_professional_post_categories_remain(self):
        self.assertEqual(
            {value for value, _ in Post.CLINIC_CONTENT_CHOICES},
            {'health_tip', 'campaign', 'notice', 'service'},
        )


class ClinicPlanAccessTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='plan-owner',
            email='plan-owner@vetpaw.test',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
        )
        self.clinic_user = User.objects.create_user(
            username='plan-clinic',
            email='plan-clinic@vetpaw.test',
            password=token_urlsafe(24),
            role='clinic',
            is_approved=True,
        )
        self.clinic = Clinic.objects.create(
            owner=self.clinic_user,
            name='Veterinaria Plan',
            address='Calle Plan 10',
            province='Buenos Aires',
            locality='Moreno',
            plan_status=Clinic.PLAN_INACTIVE,
        )
        ClinicSchedule.objects.create(
            clinic=self.clinic,
            working_days=[0, 1, 2, 3, 4, 5, 6],
            day_hours={str(day): {'open': '08:00', 'close': '20:00'} for day in range(7)},
        )
        self.pet = Pet.objects.create(owner=self.owner, name='Milo Plan', species='dog', sex='male')

    def _appointment_payload(self):
        return {
            'pet': self.pet.id,
            'clinic': self.clinic.id,
            'requested_date': (timezone.now() + timedelta(days=2)).replace(hour=10, minute=0).isoformat(),
            'reason': 'Control',
            'appointment_type': 'control',
        }

    def test_inactive_plan_blocks_new_appointments_and_slots(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post('/api/appointments/', self._appointment_payload(), format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Appointment.objects.exists())

        date_value = (timezone.localdate() + timedelta(days=2)).isoformat()
        slots = self.client.get(f'/api/clinics/{self.clinic.id}/slots/?date={date_value}&type=control')
        self.assertEqual(slots.status_code, 403)

    def test_free_trial_enables_paid_appointment_tools(self):
        self.clinic.start_free_trial()
        self.client.force_authenticate(self.owner)
        response = self.client.post('/api/appointments/', self._appointment_payload(), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        appointment = Appointment.objects.get()
        self.assertIsNone(appointment.source_post_id)
        self.assertIsNone(appointment.source_campaign_id)
        self.assertEqual(appointment.status, 'confirmed')

    def test_free_trial_can_only_be_used_once(self):
        self.clinic.start_free_trial()
        with self.assertRaises(Exception):
            self.clinic.start_free_trial()

    def test_paid_plan_prevents_late_trial(self):
        self.clinic.activate_paid_plan(days=30)
        self.assertTrue(self.clinic.trial_used)
        with self.assertRaises(Exception):
            self.clinic.start_free_trial()
