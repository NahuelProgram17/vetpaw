from django.conf import settings
from django.db import models
from django.utils.text import slugify

class AdoptionAnimal(models.Model):
    STATUS_AVAILABLE='available'; STATUS_RECOVERY='recovery'; STATUS_FOSTER='foster'; STATUS_URGENT='urgent'; STATUS_RESERVED='reserved'; STATUS_ADOPTED='adopted'
    STATUS_CHOICES=[(STATUS_AVAILABLE,'Disponible para adopción'),(STATUS_RECOVERY,'En recuperación'),(STATUS_FOSTER,'Necesita tránsito'),(STATUS_URGENT,'Caso urgente'),(STATUS_RESERVED,'Reservado'),(STATUS_ADOPTED,'Adoptado')]
    SPECIES_CHOICES=[('dog','Perro'),('cat','Gato'),('rabbit','Conejo'),('bird','Ave'),('horse','Caballo'),('farm','Animal de granja'),('other','Otro')]
    SEX_CHOICES=[('female','Hembra'),('male','Macho'),('unknown','Sin determinar')]
    SIZE_CHOICES=[('small','Pequeño'),('medium','Mediano'),('large','Grande'),('giant','Muy grande')]
    AGE_CHOICES=[('baby','Cachorro'),('young','Joven'),('adult','Adulto'),('senior','Adulto mayor')]
    shelter=models.ForeignKey('partners.ShelterProfile',on_delete=models.CASCADE,related_name='adoption_animals')
    name=models.CharField(max_length=120); slug=models.SlugField(max_length=160,blank=True)
    species=models.CharField(max_length=20,choices=SPECIES_CHOICES); breed=models.CharField(max_length=120,blank=True)
    sex=models.CharField(max_length=15,choices=SEX_CHOICES,default='unknown'); size=models.CharField(max_length=15,choices=SIZE_CHOICES,blank=True)
    age_group=models.CharField(max_length=15,choices=AGE_CHOICES,blank=True); approximate_age=models.CharField(max_length=80,blank=True)
    story=models.TextField(max_length=4000); temperament=models.TextField(blank=True,max_length=1200); health_notes=models.TextField(blank=True,max_length=1500)
    good_with_dogs=models.BooleanField(null=True,blank=True); good_with_cats=models.BooleanField(null=True,blank=True); good_with_children=models.BooleanField(null=True,blank=True)
    vaccinated=models.BooleanField(default=False); neutered=models.BooleanField(default=False); dewormed=models.BooleanField(default=False)
    province=models.CharField(max_length=100); locality=models.CharField(max_length=100); adoption_area=models.CharField(max_length=255,blank=True); requirements=models.TextField(blank=True,max_length=2500)
    urgent_needs=models.TextField(blank=True,max_length=1500); status=models.CharField(max_length=20,choices=STATUS_CHOICES,default=STATUS_AVAILABLE)
    cover=models.ImageField(upload_to='adoptions/covers/'); is_published=models.BooleanField(default=True); community_post=models.OneToOneField('community.Post',on_delete=models.SET_NULL,null=True,blank=True,related_name='adoption_animal')
    created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        ordering=['-created_at']; indexes=[models.Index(fields=['status','is_published','-created_at']),models.Index(fields=['species','province','locality'])]; constraints=[models.UniqueConstraint(fields=['shelter','slug'],name='unique_adoption_slug_per_shelter')]
    def save(self,*args,**kwargs):
        if not self.slug:
            base=slugify(self.name) or 'animal'; candidate=base; i=2
            while AdoptionAnimal.objects.filter(shelter=self.shelter,slug=candidate).exclude(pk=self.pk).exists(): candidate=f'{base}-{i}'; i+=1
            self.slug=candidate
        super().save(*args,**kwargs)
    def __str__(self): return f'{self.name} — {self.shelter.name}'

class AdoptionPhoto(models.Model):
    animal=models.ForeignKey(AdoptionAnimal,on_delete=models.CASCADE,related_name='photos'); image=models.ImageField(upload_to='adoptions/gallery/'); caption=models.CharField(max_length=180,blank=True); created_at=models.DateTimeField(auto_now_add=True)

class AdoptionApplication(models.Model):
    STATUS_NEW='new'; STATUS_REVIEW='review'; STATUS_APPROVED='approved'; STATUS_REJECTED='rejected'; STATUS_COMPLETED='completed'
    STATUS_CHOICES=[(STATUS_NEW,'Nueva'),(STATUS_REVIEW,'En revisión'),(STATUS_APPROVED,'Aprobada'),(STATUS_REJECTED,'Rechazada'),(STATUS_COMPLETED,'Adopción concretada')]
    animal=models.ForeignKey(AdoptionAnimal,on_delete=models.CASCADE,related_name='applications'); applicant=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='adoption_applications')
    phone=models.CharField(max_length=30); locality=models.CharField(max_length=100); housing_type=models.CharField(max_length=120); has_other_animals=models.BooleanField(default=False); other_animals=models.TextField(blank=True,max_length=800)
    experience=models.TextField(blank=True,max_length=1200); motivation=models.TextField(max_length=1800); follow_up_available=models.BooleanField(default=True); accepts_requirements=models.BooleanField(default=False)
    status=models.CharField(max_length=20,choices=STATUS_CHOICES,default=STATUS_NEW); shelter_notes=models.TextField(blank=True,max_length=1500); created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        ordering=['-created_at']; constraints=[models.UniqueConstraint(fields=['animal','applicant'],name='unique_application_per_animal')]

class AdoptionStatusHistory(models.Model):
    animal=models.ForeignKey(AdoptionAnimal,on_delete=models.CASCADE,related_name='status_history'); old_status=models.CharField(max_length=20,blank=True); new_status=models.CharField(max_length=20); changed_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True); created_at=models.DateTimeField(auto_now_add=True)

class HelpOffer(models.Model):
    HELP_CHOICES=[('foster','Hogar de tránsito'),('food','Alimento'),('medicine','Medicamentos'),('transport','Traslado'),('vet','Ayuda veterinaria'),('volunteer','Voluntariado'),('sharing','Difusión')]
    animal=models.ForeignKey(AdoptionAnimal,on_delete=models.CASCADE,related_name='help_offers'); user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='adoption_help_offers'); help_type=models.CharField(max_length=20,choices=HELP_CHOICES); message=models.TextField(blank=True,max_length=1200); phone=models.CharField(max_length=30,blank=True); created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['-created_at']; constraints=[models.UniqueConstraint(fields=['animal','user','help_type'],name='unique_help_offer_type')]
