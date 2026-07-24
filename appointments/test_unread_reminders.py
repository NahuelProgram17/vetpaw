from datetime import timedelta
from io import StringIO
from secrets import token_urlsafe

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from messaging.models import Message
from users.models import User


class UnreadMessageReminderTests(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            username='reminder-sender',
            email='sender@example.com',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
        )
        self.recipient = User.objects.create_user(
            username='reminder-recipient',
            email='recipient@example.com',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
        )
        self.message = Message.objects.create(
            sender=self.sender,
            recipient=self.recipient,
            content='Mensaje pendiente de lectura',
        )
        Message.objects.filter(pk=self.message.pk).update(
            created_at=timezone.now() - timedelta(hours=13),
        )

    def test_unread_reminder_is_marked_after_successful_email(self):
        call_command('send_reminders', stdout=StringIO())

        self.message.refresh_from_db()
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(self.message.unread_reminder_sent)

    def test_unread_reminder_is_not_sent_twice(self):
        call_command('send_reminders', stdout=StringIO())
        call_command('send_reminders', stdout=StringIO())

        self.assertEqual(len(mail.outbox), 1)
