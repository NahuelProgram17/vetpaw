from rest_framework import serializers
from .models import LostPet


class LostPetSerializer(serializers.ModelSerializer):
    days_left = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()
    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    owner_name = serializers.SerializerMethodField()

    class Meta:
        model = LostPet
        fields = [
            'id', 'photo', 'photo_url', 'description',
            'contact_type', 'contact_value', 'report_type',
            'province', 'locality', 'owner', 'owner_name',
            'report_count', 'expires_at', 'days_left', 'created_at'
        ]
        extra_kwargs = {'photo': {'write_only': True}}

    def get_days_left(self, obj):
        from django.utils import timezone
        delta = obj.expires_at - timezone.now()
        return max(0, delta.days)

    def get_photo_url(self, obj):
        if obj.photo:
            return obj.photo.url
        return None

    def get_owner_name(self, obj):
        if obj.owner:
            return obj.owner.first_name or obj.owner.username
        return None