from io import BytesIO
from unittest.mock import patch

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


class AdoptionNotificationTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.shelter_user = user_model.objects.create_user(
            username='notification_shelter',
            email='notification_shelter@vetpaw.test',
            password='safe-test-password',
            role='shelter',
            is_approved=True,
        )
        self.owner_user = user_model.objects.create_user(
            username='notification_owner',
            email='notification_owner@vetpaw.test',
            password='safe-test-password',
            role='owner',
            is_approved=True,
        )
        self.shelter_profile = ShelterProfile.objects.create(
            owner=self.shelter_user,
            name='Refugio Notificaciones',
            responsible_name='Ana',
            shelter_type='shelter',
            province='Buenos Aires',
            locality='Moreno',
        )

        from adoptions.models import AdoptionAnimal

        self.animal = AdoptionAnimal.objects.create(
            shelter=self.shelter_profile,
            name='Luna',
            species='dog',
            story='Busca una familia responsable.',
            province='Buenos Aires',
            locality='Moreno',
            cover=self.image(),
        )

    @staticmethod
    def image():
        buffer = BytesIO()
        Image.new('RGB', (64, 64), (90, 170, 110)).save(buffer, format='PNG')
        buffer.seek(0)
        return SimpleUploadedFile(
            'notification-pet.png',
            buffer.read(),
            content_type='image/png',
        )

    def application_payload(self):
        return {
            'phone': '11 5555 5555',
            'locality': 'Moreno',
            'housing_type': 'Casa con patio cerrado',
            'has_other_animals': False,
            'other_animals': '',
            'experience': 'Tuve perros anteriormente.',
            'motivation': 'Quiero darle una familia definitiva.',
            'follow_up_available': True,
            'accepts_requirements': True,
        }

    def create_application(self):
        self.client.force_authenticate(self.owner_user)
        response = self.client.post(
            f'/api/adoptions/{self.animal.id}/apply/',
            self.application_payload(),
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        from adoptions.models import AdoptionApplication
        return AdoptionApplication.objects.get(animal=self.animal, applicant=self.owner_user)

    def get_notification_payload(self, user):
        self.client.force_authenticate(user)
        response = self.client.get('/api/community/notifications/?page_size=50')
        self.assertEqual(response.status_code, 200, response.data)
        rows = response.data.get('results', response.data)
        self.assertTrue(rows)
        return rows[0]


    @patch('adoptions.notifications.schedule_push_notification')
    def test_new_application_uses_existing_push_pipeline(self, schedule_push):
        application = self.create_application()
        schedule_push.assert_called_once()
        self.assertEqual(
            schedule_push.call_args.args[0].adoption_application_id,
            application.id,
        )

    def test_application_notifies_shelter_with_direct_link(self):
        application = self.create_application()

        from community.models import CommunityNotification

        notification = CommunityNotification.objects.get(
            recipient=self.shelter_user,
            notification_type=CommunityNotification.TYPE_ADOPTION_APPLICATION,
        )
        self.assertEqual(notification.actor, self.owner_user)
        self.assertEqual(notification.adoption_animal, self.animal)
        self.assertEqual(notification.adoption_application, application)

        payload = self.get_notification_payload(self.shelter_user)
        self.assertEqual(payload['target_type'], 'adoption')
        self.assertEqual(
            payload['target_url'],
            f'/refugio/adopciones?tab=apps&solicitud={application.id}',
        )
        self.assertIn('quiere adoptar a Luna', payload['message'])

    def test_help_offer_notifies_shelter_with_direct_link(self):
        self.client.force_authenticate(self.owner_user)
        response = self.client.post(
            f'/api/adoptions/{self.animal.id}/help/',
            {
                'help_type': 'foster',
                'message': 'Puedo ofrecer tránsito por dos semanas.',
                'phone': '11 4444 4444',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)

        from adoptions.models import HelpOffer
        from community.models import CommunityNotification

        offer = HelpOffer.objects.get(animal=self.animal, user=self.owner_user)
        notification = CommunityNotification.objects.get(
            recipient=self.shelter_user,
            notification_type=CommunityNotification.TYPE_ADOPTION_HELP_OFFER,
        )
        self.assertEqual(notification.help_offer, offer)

        payload = self.get_notification_payload(self.shelter_user)
        self.assertEqual(
            payload['target_url'],
            f'/refugio/adopciones?tab=offers&ayuda={offer.id}',
        )
        self.assertIn('ofreció ayuda para Luna', payload['message'])
        self.assertIn('Hogar de tránsito', payload['message'])

    def test_status_update_notifies_applicant(self):
        application = self.create_application()
        self.client.force_authenticate(self.shelter_user)
        response = self.client.patch(
            f'/api/adoptions/applications/{application.id}/status/',
            {'status': 'review'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)

        from community.models import CommunityNotification

        notification = CommunityNotification.objects.get(
            recipient=self.owner_user,
            notification_type=CommunityNotification.TYPE_ADOPTION_APPLICATION_UPDATE,
        )
        self.assertEqual(notification.actor, self.shelter_user)
        self.assertIn('En revisión', notification.extra_text)

        payload = self.get_notification_payload(self.owner_user)
        self.assertEqual(
            payload['target_url'],
            f'/adopciones/{self.animal.id}?solicitud={application.id}',
        )
        self.assertIn('actualizó tu solicitud para adoptar a Luna', payload['message'])

    def test_note_update_notifies_applicant_without_requiring_status(self):
        application = self.create_application()
        self.client.force_authenticate(self.shelter_user)
        response = self.client.patch(
            f'/api/adoptions/applications/{application.id}/status/',
            {'shelter_notes': 'Nos comunicaremos durante la semana.'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)

        from community.models import CommunityNotification

        notification = CommunityNotification.objects.get(
            recipient=self.owner_user,
            notification_type=CommunityNotification.TYPE_ADOPTION_APPLICATION_UPDATE,
        )
        self.assertIn('agregó una observación', notification.extra_text)

    def test_identical_update_does_not_duplicate_notification(self):
        application = self.create_application()
        self.client.force_authenticate(self.shelter_user)
        endpoint = f'/api/adoptions/applications/{application.id}/status/'
        payload = {
            'status': 'review',
            'shelter_notes': 'Coordinaremos una entrevista.',
        }
        first = self.client.patch(endpoint, payload, format='json')
        second = self.client.patch(endpoint, payload, format='json')
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(second.status_code, 200, second.data)

        from community.models import CommunityNotification

        count = CommunityNotification.objects.filter(
            recipient=self.owner_user,
            notification_type=CommunityNotification.TYPE_ADOPTION_APPLICATION_UPDATE,
        ).count()
        self.assertEqual(count, 1)
