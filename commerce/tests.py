from datetime import timedelta
from secrets import token_urlsafe

from django.utils import timezone
from rest_framework.test import APITestCase

from community.models import CommunityNotification
from messaging.models import Message
from partners.models import BusinessProfile
from pets.models import Pet
from users.models import User

from .models import BusinessFavorite, BusinessInquiry, BusinessReservation, CatalogItem, Promotion


class CommerceTests(APITestCase):
    def setUp(self):
        password = token_urlsafe(24)
        self.business_user = User.objects.create_user(
            username='business_stage7', email='business-stage7@example.com', password=password,
            role='business', is_approved=True,
        )
        self.business = BusinessProfile.objects.create(
            owner=self.business_user, name='Patitas Store', business_type='grooming',
            responsible_name='Ana', province='Buenos Aires', locality='Moreno',
            species=['dog'], accepts_reservations=True,
            opening_hours={str(i): {'open': '08:00', 'close': '20:00', 'closed': False} for i in range(7)},
        )
        self.owner = User.objects.create_user(
            username='owner_stage7', email='owner-stage7@example.com', password=password,
            role='owner', is_approved=True, phone='1111111111',
        )
        self.pet = Pet.objects.create(owner=self.owner, name='Toby', species='dog', sex='male')

    def test_business_can_create_catalog_and_owner_cannot(self):
        payload = {
            'item_type': 'service', 'category': 'grooming', 'title': 'Baño y corte',
            'description': 'Servicio completo', 'price': '18000', 'species': ['dog'],
            'requires_booking': True, 'duration_minutes': 90,
        }
        self.client.force_authenticate(self.business_user)
        response = self.client.post('/api/commerce/catalog/', payload, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['business_name'], 'Patitas Store')

        self.client.force_authenticate(self.owner)
        denied = self.client.post('/api/commerce/catalog/', payload, format='json')
        self.assertEqual(denied.status_code, 403)

    def test_inquiry_creates_message_and_notification(self):
        item = CatalogItem.objects.create(
            business=self.business, item_type='product', category='food', title='Alimento',
            description='Bolsa 15 kg', price=42000,
        )
        self.client.force_authenticate(self.owner)
        response = self.client.post('/api/commerce/inquiries/', {
            'business': self.business.id, 'catalog_item': item.id, 'content': '¿Hacen envíos?'
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Message.objects.filter(sender=self.owner, recipient=self.business_user).exists())
        self.assertTrue(BusinessInquiry.objects.filter(user=self.owner, catalog_item=item).exists())
        self.assertTrue(CommunityNotification.objects.filter(recipient=self.business_user, notification_type='business_inquiry').exists())

    def test_reservation_flow_and_duplicate_slot(self):
        service = CatalogItem.objects.create(
            business=self.business, item_type='service', category='grooming', title='Baño',
            description='Baño completo', price=10000, requires_booking=True, duration_minutes=60,
        )
        day = timezone.localdate() + timedelta(days=2)
        payload = {
            'business': self.business.id, 'catalog_item': service.id, 'pet': self.pet.id,
            'date': day.isoformat(), 'start_time': '10:00', 'notes': 'Es tranquilo',
        }
        self.client.force_authenticate(self.owner)
        response = self.client.post('/api/commerce/reservations/', payload, format='json')
        self.assertEqual(response.status_code, 201)
        duplicate = self.client.post('/api/commerce/reservations/', payload, format='json')
        self.assertEqual(duplicate.status_code, 400)

        reservation_id = response.data['id']
        self.client.force_authenticate(self.business_user)
        confirmed = self.client.patch(f'/api/commerce/reservations/{reservation_id}/status/', {
            'status': 'confirmed', 'business_note': 'Te esperamos.'
        }, format='json')
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(confirmed.data['status'], 'confirmed')

    def test_favorite_toggle_and_current_promotions(self):
        item = CatalogItem.objects.create(
            business=self.business, item_type='product', category='accessories', title='Correa',
            description='Correa reforzada', price=10000,
        )
        Promotion.objects.create(
            business=self.business, catalog_item=item, title='Oferta correa', description='20% menos',
            previous_price=10000, promotional_price=8000,
            starts_at=timezone.now() - timedelta(hours=1), ends_at=timezone.now() + timedelta(days=2),
        )
        self.client.force_authenticate(self.owner)
        toggled = self.client.post('/api/commerce/favorites/toggle/', {'target_type': 'catalog_item', 'target_id': item.id}, format='json')
        self.assertEqual(toggled.status_code, 200)
        self.assertTrue(toggled.data['favorite'])
        self.assertTrue(BusinessFavorite.objects.filter(user=self.owner, catalog_item=item).exists())
        listed = self.client.get('/api/commerce/promotions/')
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.data), 1)
