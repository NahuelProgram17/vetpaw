from rest_framework import serializers
from .models import Advertiser
from vetpaw.image_validation import validate_uploaded_image


class AdvertiserSerializer(serializers.ModelSerializer):
    def validate_image(self, value):
        return validate_uploaded_image(value, max_mb=5, label='La imagen del anuncio')

    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Advertiser
        fields = [
            'id', 'name', 'image', 'image_url', 'link',
            'is_active', 'order', 'start_date', 'end_date',
            'clicks', 'is_live', 'created_at'
        ]
        extra_kwargs = {'image': {'write_only': True, 'required': False}}
        read_only_fields = ['id', 'clicks', 'created_at']

    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None
