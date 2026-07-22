from rest_framework import serializers
from vetpaw.image_validation import validate_uploaded_image
from .models import AdoptionAnimal, AdoptionPhoto, AdoptionApplication, HelpOffer, AdoptionStatusHistory

def file_url(request, field):
    if not field: return None
    try: url=field.url
    except (ValueError,AttributeError): return None
    return request.build_absolute_uri(url) if request and url.startswith('/') else url

class AdoptionPhotoSerializer(serializers.ModelSerializer):
    image_url=serializers.SerializerMethodField()
    class Meta: model=AdoptionPhoto; fields=['id','image_url','caption']
    def get_image_url(self,obj): return file_url(self.context.get('request'),obj.image)

class AdoptionAnimalSerializer(serializers.ModelSerializer):
    cover_url=serializers.SerializerMethodField(); photos=AdoptionPhotoSerializer(many=True,read_only=True); shelter_name=serializers.CharField(source='shelter.name',read_only=True); shelter_slug=serializers.CharField(source='shelter.slug',read_only=True); shelter_logo=serializers.SerializerMethodField(); status_display=serializers.CharField(source='get_status_display',read_only=True); species_display=serializers.CharField(source='get_species_display',read_only=True); can_manage=serializers.SerializerMethodField(); applications_count=serializers.SerializerMethodField(); help_offers_count=serializers.SerializerMethodField()
    class Meta:
        model=AdoptionAnimal; fields=['id','slug','name','species','species_display','breed','sex','size','age_group','approximate_age','story','temperament','health_notes','good_with_dogs','good_with_cats','good_with_children','vaccinated','neutered','dewormed','province','locality','adoption_area','requirements','urgent_needs','status','status_display','cover','cover_url','photos','shelter_name','shelter_slug','shelter_logo','is_published','can_manage','applications_count','help_offers_count','created_at','updated_at']; read_only_fields=['slug','shelter_name','shelter_slug','created_at','updated_at']
    def validate_cover(self,v): return validate_uploaded_image(v,max_mb=6,label='La foto principal')
    def get_cover_url(self,obj): return file_url(self.context.get('request'),obj.cover)
    def get_shelter_logo(self,obj): return file_url(self.context.get('request'),obj.shelter.logo)
    def get_can_manage(self,obj):
        r=self.context.get('request'); return bool(r and r.user.is_authenticated and (r.user.id==obj.shelter.owner_id or r.user.is_staff or r.user.is_superuser))
    def get_applications_count(self,obj): return obj.applications.count() if self.get_can_manage(obj) else None
    def get_help_offers_count(self,obj): return obj.help_offers.count() if self.get_can_manage(obj) else None

class AdoptionApplicationSerializer(serializers.ModelSerializer):
    applicant_name=serializers.SerializerMethodField(); animal_name=serializers.CharField(source='animal.name',read_only=True)
    class Meta: model=AdoptionApplication; fields=['id','animal','animal_name','applicant_name','phone','locality','housing_type','has_other_animals','other_animals','experience','motivation','follow_up_available','accepts_requirements','status','shelter_notes','created_at','updated_at']; read_only_fields=['applicant_name','status','shelter_notes','created_at','updated_at']
    def get_applicant_name(self,obj): return obj.applicant.get_full_name().strip() or obj.applicant.username
    def validate_accepts_requirements(self,v):
        if not v: raise serializers.ValidationError('Tenés que aceptar los requisitos del refugio.')
        return v

class HelpOfferSerializer(serializers.ModelSerializer):
    user_name=serializers.SerializerMethodField(); help_type_display=serializers.CharField(source='get_help_type_display',read_only=True)
    class Meta: model=HelpOffer; fields=['id','animal','user_name','help_type','help_type_display','message','phone','created_at']; read_only_fields=['user_name','created_at']
    def get_user_name(self,obj): return obj.user.get_full_name().strip() or obj.user.username

class AdoptionStatusHistorySerializer(serializers.ModelSerializer):
    class Meta: model=AdoptionStatusHistory; fields=['old_status','new_status','created_at']
