from datetime import timedelta
from secrets import token_urlsafe

from django.utils import timezone
from rest_framework.test import APITestCase

from clinics.models import Clinic, ClinicPetAccess
from pets.models import Pet
from users.models import User

from .models import Appointment, Visit


class VisitApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='visit-owner',
            email='visit-owner@example.com',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
        )
        self.clinic_user = User.objects.create_user(
            username='visit-clinic',
            email='visit-clinic@example.com',
            password=token_urlsafe(24),
            role='clinic',
            is_approved=True,
        )
        self.clinic = Clinic.objects.create(
            owner=self.clinic_user,
            name='Clínica de pruebas',
            address='Calle 123',
            province='Buenos Aires',
            locality='Moreno',
        )
        self.pet = Pet.objects.create(
            owner=self.owner,
            name='Toby',
            species='dog',
            sex='male',
        )
        ClinicPetAccess.objects.create(
            clinic=self.clinic,
            pet=self.pet,
            last_appointment=timezone.now(),
        )
        self.client.force_authenticate(self.clinic_user)

    def visit_payload(self, **overrides):
        payload = {
            'pet': self.pet.id,
            'date': timezone.now().isoformat(),
            'reason': 'Control general',
            'diagnosis': 'Paciente en buen estado',
            'treatment': '',
            'observations': '',
            'next_visit': None,
            'vet_first_name': 'Ana',
            'vet_last_name': 'Pérez',
            'vet_license': 'MP 1234',
            'vet_clinic_name': self.clinic.name,
        }
        payload.update(overrides)
        return payload

    def test_direct_visit_from_patient_file_does_not_complete_future_appointments(self):
        future_appointment = Appointment.objects.create(
            owner=self.owner,
            pet=self.pet,
            clinic=self.clinic,
            requested_date=timezone.now() + timedelta(days=7),
            reason='Control futuro',
            status='confirmed',
        )

        response = self.client.post('/api/visits/', self.visit_payload(), format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Visit.objects.count(), 1)
        future_appointment.refresh_from_db()
        self.assertEqual(future_appointment.status, 'confirmed')

    def test_visit_opened_from_appointment_completes_only_that_appointment(self):
        selected = Appointment.objects.create(
            owner=self.owner,
            pet=self.pet,
            clinic=self.clinic,
            requested_date=timezone.now(),
            reason='Consulta actual',
            status='confirmed',
        )
        another = Appointment.objects.create(
            owner=self.owner,
            pet=self.pet,
            clinic=self.clinic,
            requested_date=timezone.now() + timedelta(days=14),
            reason='Control siguiente',
            status='confirmed',
        )

        response = self.client.post(
            '/api/visits/',
            self.visit_payload(appointment_id=selected.id),
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        selected.refresh_from_db()
        another.refresh_from_db()
        self.assertEqual(selected.status, 'completed')
        self.assertEqual(another.status, 'confirmed')

    def test_clinic_cannot_create_visit_for_unrelated_pet(self):
        unrelated_pet = Pet.objects.create(
            owner=self.owner,
            name='Luna',
            species='cat',
            sex='female',
        )

        response = self.client.post(
            '/api/visits/',
            self.visit_payload(pet=unrelated_pet.id),
            format='json',
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Visit.objects.filter(pet=unrelated_pet).exists())


class AppointmentPrivacyTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='appointment-privacy-owner',
            email='appointment-privacy-owner@example.com',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
        )
        self.clinic_user = User.objects.create_user(
            username='appointment-privacy-clinic',
            email='appointment-privacy-clinic@example.com',
            password=token_urlsafe(24),
            role='clinic',
            is_approved=True,
        )
        self.clinic = Clinic.objects.create(
            owner=self.clinic_user,
            name='Clínica privada',
            address='Calle 10',
            province='Buenos Aires',
            locality='Moreno',
        )
        self.pet = Pet.objects.create(
            owner=self.owner,
            name='Milo',
            species='dog',
            sex='male',
        )
        self.client.force_authenticate(self.owner)

    def test_clinic_can_disable_community_appointment_requests(self):
        from community.models import CommunityPrivacySettings
        CommunityPrivacySettings.objects.create(
            user=self.clinic_user,
            allow_appointment_requests=False,
        )
        response = self.client.post('/api/appointments/', {
            'pet': self.pet.id,
            'clinic': self.clinic.id,
            'requested_date': (timezone.now() + timedelta(days=2)).isoformat(),
            'reason': 'Control',
            'appointment_type': 'control',
        }, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Appointment.objects.filter(owner=self.owner, clinic=self.clinic).exists())
