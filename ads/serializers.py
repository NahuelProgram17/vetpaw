from rest_framework import serializers
from .models import Advertiser


class AdvertiserSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Advertiser
        fields = [
            'id', 'name', 'image', 'image_url', 'link',
            'is_active', 'order', 'start_date', 'end_date',
            'is_live', 'created_at'
        ]
        extra_kwargs = {'image': {'write_only': True, 'required': False}}
        read_only_fields = ['id', 'created_at']

    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None
