from rest_framework import serializers
from .models import Message


class MessageSerializer(serializers.ModelSerializer):
    sender_name    = serializers.CharField(source='sender.username',  read_only=True)
    recipient_name = serializers.CharField(source='recipient.username', read_only=True)
    appointment_reason = serializers.CharField(source='appointment.reason', read_only=True)
    pet_name       = serializers.CharField(source='appointment.pet.name', read_only=True)

    class Meta:
        model  = Message
        fields = [
            'id', 'sender', 'sender_name', 'recipient', 'recipient_name',
            'appointment', 'appointment_reason', 'pet_name',
            'content', 'read', 'created_at',
        ]
        read_only_fields = ['id', 'sender', 'read', 'created_at']