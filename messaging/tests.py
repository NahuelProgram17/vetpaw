from secrets import token_urlsafe

from rest_framework.test import APITestCase

from community.models import BlockedUser, CommunityPrivacySettings
from users.models import User

from .models import Message


class MessagePrivacyTests(APITestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            username='message-sender', email='message-sender@example.com',
            password=token_urlsafe(24), role='owner', is_approved=True,
        )
        self.recipient = User.objects.create_user(
            username='message-recipient', email='message-recipient@example.com',
            password=token_urlsafe(24), role='business', is_approved=True,
        )
        self.client.force_authenticate(self.sender)

    def test_recipient_can_disable_internal_messages(self):
        CommunityPrivacySettings.objects.create(
            user=self.recipient,
            allow_internal_messages=False,
        )
        response = self.client.post('/api/messages/', {
            'recipient': self.recipient.id,
            'content': 'Hola desde VetPaw',
        }, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Message.objects.count(), 0)

    def test_blocks_prevent_messages(self):
        BlockedUser.objects.create(blocker=self.recipient, blocked=self.sender)
        response = self.client.post('/api/messages/', {
            'recipient': self.recipient.id,
            'content': 'No debería enviarse',
        }, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Message.objects.count(), 0)
