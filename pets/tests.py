from secrets import token_urlsafe

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
            password=token_urlsafe(24),
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


class PetPhotoUploadTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner-photo',
            email='owner-photo@example.com',
            password=token_urlsafe(24),
            role='owner',
        )

    def test_owner_can_create_pet_with_valid_photo(self):
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        image_bytes = BytesIO()
        Image.new('RGB', (160, 120), color=(70, 170, 90)).save(image_bytes, format='JPEG')
        image_bytes.seek(0)
        photo = SimpleUploadedFile('toby.jpg', image_bytes.read(), content_type='image/jpeg')

        client = APIClient()
        client.force_authenticate(self.owner)
        response = client.post('/api/pets/', {
            'name': 'Toby',
            'species': 'dog',
            'sex': 'male',
            'photo': photo,
        }, format='multipart')

        self.assertEqual(response.status_code, 201)
        pet = Pet.objects.get(name='Toby')
        self.assertTrue(bool(pet.photo))
        self.assertTrue(response.data['photo'])
