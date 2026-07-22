from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APITestCase

from partners.models import ShelterProfile


class AdoptionTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()

        self.shelter_user = user_model.objects.create_user(
            username="shelter_test",
            email="shelter_test@vetpaw.test",
            password="safe-test-password",
            role="shelter",
            is_approved=True,
        )
        self.owner_user = user_model.objects.create_user(
            username="owner_test",
            email="owner_test@vetpaw.test",
            password="safe-test-password",
            role="owner",
            is_approved=True,
        )
        self.shelter_profile = ShelterProfile.objects.create(
            owner=self.shelter_user,
            name="Refugio Test",
            responsible_name="Ana",
            shelter_type="shelter",
            province="Buenos Aires",
            locality="Moreno",
        )

    @staticmethod
    def image():
        """Genera una imagen PNG válida para las reglas reales de VetPaw."""
        buffer = BytesIO()
        Image.new("RGB", (64, 64), (90, 170, 110)).save(buffer, format="PNG")
        buffer.seek(0)
        return SimpleUploadedFile(
            "pet.png",
            buffer.read(),
            content_type="image/png",
        )

    def test_shelter_can_create_and_public_can_list(self):
        self.client.force_authenticate(self.shelter_user)
        response = self.client.post(
            "/api/adoptions/",
            {
                "name": "Luna",
                "species": "dog",
                "story": "Busca familia responsable",
                "province": "Buenos Aires",
                "locality": "Moreno",
                "cover": self.image(),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)

        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/adoptions/").status_code, 200)

    def test_owner_cannot_create(self):
        self.client.force_authenticate(self.owner_user)
        response = self.client.post(
            "/api/adoptions/",
            {
                "name": "No",
                "species": "dog",
                "story": "x",
                "province": "BA",
                "locality": "Moreno",
                "cover": self.image(),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 403, response.data)
