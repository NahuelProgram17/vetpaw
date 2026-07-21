from secrets import token_urlsafe

from rest_framework.test import APITestCase

from users.models import User


class LostPetAdminPermissionTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='lost_owner',
            email='lost-owner@example.com',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
        )
        self.staff = User.objects.create_user(
            username='lost_admin',
            email='lost-admin@example.com',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
            is_staff=True,
        )

    def test_regular_user_cannot_access_lost_pet_admin(self):
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get('/api/lost-pets/admin/').status_code, 403)

    def test_staff_user_can_access_lost_pet_admin(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get('/api/lost-pets/admin/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
