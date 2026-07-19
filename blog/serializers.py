from rest_framework import serializers
from .models import Post
from vetpaw.image_validation import validate_uploaded_image


class PostListSerializer(serializers.ModelSerializer):
    cover_url = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ['id', 'title', 'slug', 'excerpt', 'cover_url', 'is_published', 'created_at']

    def get_cover_url(self, obj):
        if obj.cover:
            return obj.cover.url
        return None


class PostSerializer(serializers.ModelSerializer):
    def validate_cover(self, value):
        return validate_uploaded_image(value, max_mb=5, label='La portada del artículo')

    cover_url = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            'id', 'title', 'slug', 'excerpt', 'content', 'cover', 'cover_url',
            'is_published', 'created_at', 'updated_at'
        ]
        extra_kwargs = {'cover': {'write_only': True, 'required': False}}
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']

    def get_cover_url(self, obj):
        if obj.cover:
            return obj.cover.url
        return None
