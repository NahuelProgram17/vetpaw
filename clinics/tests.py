from datetime import timedelta
from secrets import token_urlsafe

from django.utils import timezone
from rest_framework.test import APITestCase

from appointments.models import Appointment
from community.models import CommunityNotification, Post
from pets.models import Pet
from users.models import User

from .models import Clinic, ClinicCampaign


class ClinicCommunityStage8Tests(APITestCase):
    def setUp(self):
        self.clinic_user = User.objects.create_user(
            username='stage8-clinic',
            email='stage8-clinic@vetpaw.test',
            password=token_urlsafe(24),
            role='clinic',
            is_approved=True,
        )
        self.owner = User.objects.create_user(
            username='stage8-owner',
            email='stage8-owner@vetpaw.test',
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
        )
        self.pet = Pet.objects.create(
            owner=self.owner,
            name='Toby Stage 8',
            species='dog',
            sex='male',
        )
        self.starts_at = timezone.now() + timedelta(days=7)

    def _campaign_payload(self):
        return {
            'campaign_type': ClinicCampaign.TYPE_VACCINATION,
            'title': 'Vacunación antirrábica',
            'description': 'Jornada comunitaria con cupos limitados.',
            'starts_at': self.starts_at.isoformat(),
            'ends_at': (self.starts_at + timedelta(hours=4)).isoformat(),
            'location': 'Veterinaria Comunidad',
            'capacity': 10,
            'species': ['dog', 'cat'],
            'price': '0.00',
            'is_free': True,
            'allow_booking': True,
            'is_active': True,
        }

    def test_clinic_can_create_and_publish_campaign(self):
        self.client.force_authenticate(self.clinic_user)

        create_response = self.client.post(
            '/api/clinic-campaigns/',
            self._campaign_payload(),
            format='json',
        )

        self.assertEqual(create_response.status_code, 201, create_response.data)
        campaign = ClinicCampaign.objects.get(pk=create_response.data['id'])
        self.assertEqual(campaign.clinic, self.clinic)

        publish_response = self.client.post(
            f'/api/clinic-campaigns/{campaign.id}/publish/',
            {'text': 'Sumate a nuestra campaña de vacunación.'},
            format='json',
        )

        self.assertEqual(publish_response.status_code, 201, publish_response.data)
        post = Post.objects.get(related_clinic_campaign=campaign)
        self.assertEqual(post.clinic, self.clinic)
        self.assertEqual(post.clinic_content_type, Post.CLINIC_CONTENT_CAMPAIGN)
        self.assertTrue(post.is_public)

    def test_owner_cannot_create_clinic_campaign(self):
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            '/api/clinic-campaigns/',
            self._campaign_payload(),
            format='json',
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(ClinicCampaign.objects.exists())

    def test_campaign_appointment_creates_notifications_for_both_sides(self):
        campaign = ClinicCampaign.objects.create(
            clinic=self.clinic,
            campaign_type=ClinicCampaign.TYPE_VACCINATION,
            title='Vacunación con turno',
            description='Reservá desde la Comunidad.',
            starts_at=self.starts_at,
            ends_at=self.starts_at + timedelta(hours=4),
            capacity=5,
            species=['dog'],
            is_free=True,
            allow_booking=True,
            is_active=True,
        )
        post = Post.objects.create(
            created_by=self.clinic_user,
            clinic=self.clinic,
            post_type=Post.TYPE_CLINIC,
            clinic_content_type=Post.CLINIC_CONTENT_CAMPAIGN,
            related_clinic_campaign=campaign,
            text='Turnos para vacunación.',
            province=self.clinic.province,
            locality=self.clinic.locality,
            is_public=True,
            moderation_status=Post.STATUS_PUBLISHED,
        )
        self.client.force_authenticate(self.owner)

        response = self.client.post('/api/appointments/', {
            'pet': self.pet.id,
            'clinic': self.clinic.id,
            'source_post': post.id,
            'requested_date': (timezone.now() + timedelta(days=2)).isoformat(),
            'reason': 'Quiero participar',
            'appointment_type': 'control',
        }, format='json')

        self.assertEqual(response.status_code, 201, response.data)
        appointment = Appointment.objects.get(pk=response.data['id'])
        self.assertEqual(appointment.status, 'pending')
        self.assertEqual(appointment.source_campaign, campaign)
        self.assertEqual(appointment.requested_date, campaign.starts_at)
        self.assertEqual(appointment.appointment_type, 'vaccine')
        self.assertTrue(CommunityNotification.objects.filter(
            recipient=self.clinic_user,
            actor=self.owner,
            appointment=appointment,
            notification_type=CommunityNotification.TYPE_CLINIC_APPOINTMENT,
        ).exists())

        self.client.force_authenticate(self.clinic_user)
        confirm_response = self.client.patch(
            f'/api/appointments/{appointment.id}/confirm/',
            {},
            format='json',
        )

        self.assertEqual(confirm_response.status_code, 200, confirm_response.data)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, 'confirmed')
        self.assertTrue(CommunityNotification.objects.filter(
            recipient=self.owner,
            actor=self.clinic_user,
            appointment=appointment,
            notification_type=CommunityNotification.TYPE_CLINIC_APPOINTMENT_UPDATE,
        ).exists())

        self.client.force_authenticate(self.owner)
        cancel_response = self.client.patch(
            f'/api/appointments/{appointment.id}/cancel/',
            {},
            format='json',
        )

        self.assertEqual(cancel_response.status_code, 200, cancel_response.data)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, 'cancelled')
        self.assertTrue(CommunityNotification.objects.filter(
            recipient=self.clinic_user,
            actor=self.owner,
            appointment=appointment,
            notification_type=CommunityNotification.TYPE_CLINIC_APPOINTMENT_UPDATE,
        ).exists())
