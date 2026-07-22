from secrets import token_urlsafe

from django.contrib.auth.models import Group
from rest_framework.test import APITestCase

from users.models import User

from .models import BusinessProfile, ShelterProfile


class PartnerRegistrationAndProfileTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_partners',
            email='admin-partners@example.com',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
        )
        admin_group, _ = Group.objects.get_or_create(name='vetpaw_admins')
        self.admin.groups.add(admin_group)

    def test_business_registration_creates_pending_profile(self):
        response = self.client.post('/api/users/register-business/', {
            'username': 'mundo_animal',
            'email': 'mundo-animal@example.com',
            'password': 'VetPaw-Business-2026!',
            'password2': 'VetPaw-Business-2026!',
            'business_name': 'Mundo Animal',
            'business_type': 'petshop',
            'responsible_name': 'Ana Responsable',
            'business_whatsapp': '1122334455',
            'business_province': 'Buenos Aires',
            'business_locality': 'Moreno',
            'business_species': ['dog', 'cat'],
            'business_services': ['food', 'accessories'],
        }, format='json')

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username='mundo_animal')
        self.assertEqual(user.role, 'business')
        self.assertFalse(user.is_approved)
        self.assertEqual(user.business_profile.name, 'Mundo Animal')
        self.assertEqual(user.business_profile.species, ['dog', 'cat'])

        hidden = self.client.get(f'/api/businesses/{user.business_profile.slug}/')
        self.assertEqual(hidden.status_code, 404)

        self.client.force_authenticate(self.admin)
        approved = self.client.post(f'/api/users/admin/approve-profile/{user.id}/')
        self.assertEqual(approved.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.is_approved)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(f'/api/businesses/{user.business_profile.slug}/').status_code, 200)

    def test_shelter_registration_requires_contact_and_species(self):
        invalid = self.client.post('/api/users/register-shelter/', {
            'username': 'sin_contacto',
            'email': 'sin-contacto@example.com',
            'password': 'VetPaw-Shelter-2026!',
            'password2': 'VetPaw-Shelter-2026!',
            'shelter_name': 'Refugio Sin Contacto',
            'shelter_type': 'shelter',
            'responsible_name': 'Responsable',
            'shelter_province': 'Buenos Aires',
            'shelter_locality': 'Merlo',
            'shelter_species': [],
        }, format='json')
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(User.objects.filter(username='sin_contacto').exists())

    def test_owner_can_edit_own_profile_and_private_fields_are_hidden_publicly(self):
        owner = User.objects.create_user(
            username='refugio_owner',
            email='refugio-owner@example.com',
            password=token_urlsafe(24),
            role='shelter',
            is_approved=True,
        )
        profile = ShelterProfile.objects.create(
            owner=owner,
            name='Patitas al Rescate',
            shelter_type='rescue',
            responsible_name='Carla Rescate',
            province='Buenos Aires',
            locality='Moreno',
            species=['dog'],
            donation_alias='PATITAS.VETPAW',
            donation_cbu='0000000000000000000000',
            tax_id='30-00000000-0',
            capacity_max=40,
            current_animals=18,
        )

        public = self.client.get(f'/api/shelters/{profile.slug}/')
        self.assertEqual(public.status_code, 200)
        self.assertNotIn('donation_cbu', public.data)
        self.assertNotIn('tax_id', public.data)
        self.assertNotIn('capacity_max', public.data)

        self.client.force_authenticate(owner)
        own = self.client.get('/api/shelters/me/')
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.data['donation_cbu'], '0000000000000000000000')

        updated = self.client.patch('/api/shelters/me/', {
            'activities': '["rescue", "adoption"]',
            'species': '["dog", "cat"]',
            'accepting_animals': True,
        }, format='multipart')
        self.assertEqual(updated.status_code, 200)
        profile.refresh_from_db()
        self.assertEqual(profile.activities, ['rescue', 'adoption'])
        self.assertEqual(profile.species, ['dog', 'cat'])
        self.assertTrue(profile.accepting_animals)

    def test_user_cannot_edit_another_business(self):
        owner = User.objects.create_user(
            username='business_owner', email='business-owner@example.com',
            password=token_urlsafe(24), role='business', is_approved=True,
        )
        other = User.objects.create_user(
            username='other_business', email='other-business@example.com',
            password=token_urlsafe(24), role='business', is_approved=True,
        )
        profile = BusinessProfile.objects.create(
            owner=owner, name='Peluquería Toby', business_type='grooming',
            responsible_name='Toby Responsable', province='Buenos Aires', locality='Moreno',
            species=['dog'], services=['grooming'],
        )
        BusinessProfile.objects.create(
            owner=other, name='Petshop Luna', business_type='petshop',
            responsible_name='Luna Responsable', province='Buenos Aires', locality='Merlo',
            species=['cat'], services=['food'],
        )

        self.client.force_authenticate(other)
        response = self.client.patch(f'/api/businesses/{profile.slug}/', {'name': 'Nombre alterado'}, format='json')
        self.assertEqual(response.status_code, 403)
        profile.refresh_from_db()
        self.assertEqual(profile.name, 'Peluquería Toby')
