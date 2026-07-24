from django.db import models
from users.models import User
from appointments.models import Appointment


class Message(models.Model):
    sender      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    appointment = models.ForeignKey(Appointment, on_delete=models.SET_NULL, null=True, blank=True, related_name='messages')
    content     = models.TextField()
    read        = models.BooleanField(default=False)
    unread_reminder_sent = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(
                fields=['read', 'unread_reminder_sent', 'created_at'],
                name='msg_unread_reminder_idx',
            ),
        ]

    def __str__(self):
        return f"{self.sender.username} → {self.recipient.username}: {self.content[:40]}"