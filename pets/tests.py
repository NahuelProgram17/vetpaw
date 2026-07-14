from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .birthdays import sync_birthday_celebrations
from .models import BirthdayCelebration, Pet


User = get_user_model()


class BirthdayCelebrationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner-birthday',
            email='owner-birthday@example.com',
            password='test-pass-123',
            role='owner',
        )
        today = timezone.localdate()
        self.pet = Pet.objects.create(
            owner=self.owner,
            name='Luna',
            species='dog',
            sex='female',
            birth_date=date(today.year - 5, today.month, today.day),
        )

    def test_sync_creates_only_one_annual_celebration(self):
        sync_birthday_celebrations(self.owner)
        sync_birthday_celebrations(self.owner)
        celebration = BirthdayCelebration.objects.get(pet=self.pet)
        self.assertEqual(celebration.age, 5)
        self.assertEqual(BirthdayCelebration.objects.count(), 1)

    def test_current_endpoint_and_open_gift(self):
        client = APIClient()
        client.force_authenticate(self.owner)
        response = client.get('/api/birthday-celebrations/current/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        celebration_id = response.data[0]['id']

        response = client.post(f'/api/birthday-celebrations/{celebration_id}/open-gift/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_opened'])
        self.assertTrue(response.data['is_read'])

        response = client.get('/api/birthday-celebrations/current/')
        self.assertEqual(response.data, [])
