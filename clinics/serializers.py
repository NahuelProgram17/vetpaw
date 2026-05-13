from rest_framework import serializers
from .models import Clinic, ClinicMembership
from django.db.models import Avg


class ClinicSerializer(serializers.ModelSerializer):
    members_count = serializers.SerializerMethodField()
    rating_avg    = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()
    distance_km   = serializers.SerializerMethodField()
    is_member     = serializers.SerializerMethodField() 

    class Meta:
        model = Clinic
        fields = [
            'id', 'owner', 'name', 'description', 'address',
            'province', 'locality', 'phone', 'email',
            'logo', 'is_active', 'is_24h', 'services',
            'members_count', 'rating_avg', 'reviews_count',
            'distance_km', 'is_member', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'members_count', 'rating_avg', 'reviews_count', 'distance_km']

    def get_members_count(self, obj):
        return obj.members.filter(status='active').count()

    def get_rating_avg(self, obj):
        avg = obj.reviews.aggregate(avg=Avg('rating'))['avg']
        return round(avg, 1) if avg else None

    def get_reviews_count(self, obj):
        return obj.reviews.count()

    def get_distance_km(self, obj):
        return getattr(obj, '_distance_km', None)


class ClinicMembershipSerializer(serializers.ModelSerializer):
    clinic_name     = serializers.CharField(source='clinic.name',     read_only=True)
    clinic_locality = serializers.CharField(source='clinic.locality', read_only=True)

    class Meta:
        model = ClinicMembership
        fields = [
            'id', 'clinic', 'clinic_name', 'clinic_locality',
            'status', 'leave_reason', 'leave_rating',
            'joined_at', 'left_at'
        ]
        read_only_fields = ['id', 'joined_at', 'left_at', 'status']


class LeaveClinicSerializer(serializers.Serializer):
    leave_reason = serializers.CharField(required=True)
    leave_rating = serializers.IntegerField(min_value=1, max_value=5)