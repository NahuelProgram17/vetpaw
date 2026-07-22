# Generated for VetPaw Etapa 6
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('partners', '0001_initial'),
        ('community', '0007_privacy_and_control_stage5'),
    ]
    operations = [
        migrations.CreateModel(
            name='AdoptionAnimal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)), ('slug', models.SlugField(blank=True, max_length=160)),
                ('species', models.CharField(choices=[('dog','Perro'),('cat','Gato'),('rabbit','Conejo'),('bird','Ave'),('horse','Caballo'),('farm','Animal de granja'),('other','Otro')], max_length=20)),
                ('breed', models.CharField(blank=True,max_length=120)), ('sex', models.CharField(choices=[('female','Hembra'),('male','Macho'),('unknown','Sin determinar')],default='unknown',max_length=15)),
                ('size', models.CharField(blank=True,choices=[('small','Pequeño'),('medium','Mediano'),('large','Grande'),('giant','Muy grande')],max_length=15)),
                ('age_group', models.CharField(blank=True,choices=[('baby','Cachorro'),('young','Joven'),('adult','Adulto'),('senior','Adulto mayor')],max_length=15)), ('approximate_age',models.CharField(blank=True,max_length=80)),
                ('story',models.TextField(max_length=4000)), ('temperament',models.TextField(blank=True,max_length=1200)), ('health_notes',models.TextField(blank=True,max_length=1500)),
                ('good_with_dogs',models.BooleanField(blank=True,null=True)), ('good_with_cats',models.BooleanField(blank=True,null=True)), ('good_with_children',models.BooleanField(blank=True,null=True)),
                ('vaccinated',models.BooleanField(default=False)), ('neutered',models.BooleanField(default=False)), ('dewormed',models.BooleanField(default=False)),
                ('province',models.CharField(max_length=100)), ('locality',models.CharField(max_length=100)), ('adoption_area',models.CharField(blank=True,max_length=255)), ('requirements',models.TextField(blank=True,max_length=2500)), ('urgent_needs',models.TextField(blank=True,max_length=1500)),
                ('status',models.CharField(choices=[('available','Disponible para adopción'),('recovery','En recuperación'),('foster','Necesita tránsito'),('urgent','Caso urgente'),('reserved','Reservado'),('adopted','Adoptado')],default='available',max_length=20)),
                ('cover',models.ImageField(upload_to='adoptions/covers/')), ('is_published',models.BooleanField(default=True)), ('created_at',models.DateTimeField(auto_now_add=True)), ('updated_at',models.DateTimeField(auto_now=True)),
                ('community_post',models.OneToOneField(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='adoption_animal',to='community.post')),
                ('shelter',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='adoption_animals',to='partners.shelterprofile')),
            ], options={'ordering':['-created_at']},
        ),
        migrations.CreateModel(name='AdoptionPhoto',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('image',models.ImageField(upload_to='adoptions/gallery/')),('caption',models.CharField(blank=True,max_length=180)),('created_at',models.DateTimeField(auto_now_add=True)),('animal',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='photos',to='adoptions.adoptionanimal'))]),
        migrations.CreateModel(name='AdoptionApplication',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('phone',models.CharField(max_length=30)),('locality',models.CharField(max_length=100)),('housing_type',models.CharField(max_length=120)),('has_other_animals',models.BooleanField(default=False)),('other_animals',models.TextField(blank=True,max_length=800)),('experience',models.TextField(blank=True,max_length=1200)),('motivation',models.TextField(max_length=1800)),('follow_up_available',models.BooleanField(default=True)),('accepts_requirements',models.BooleanField(default=False)),('status',models.CharField(choices=[('new','Nueva'),('review','En revisión'),('approved','Aprobada'),('rejected','Rechazada'),('completed','Adopción concretada')],default='new',max_length=20)),('shelter_notes',models.TextField(blank=True,max_length=1500)),('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),('animal',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='applications',to='adoptions.adoptionanimal')),('applicant',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='adoption_applications',to=settings.AUTH_USER_MODEL))],options={'ordering':['-created_at']}),
        migrations.CreateModel(name='AdoptionStatusHistory',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('old_status',models.CharField(blank=True,max_length=20)),('new_status',models.CharField(max_length=20)),('created_at',models.DateTimeField(auto_now_add=True)),('animal',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='status_history',to='adoptions.adoptionanimal')),('changed_by',models.ForeignKey(null=True,on_delete=django.db.models.deletion.SET_NULL,to=settings.AUTH_USER_MODEL))]),
        migrations.CreateModel(name='HelpOffer',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('help_type',models.CharField(choices=[('foster','Hogar de tránsito'),('food','Alimento'),('medicine','Medicamentos'),('transport','Traslado'),('vet','Ayuda veterinaria'),('volunteer','Voluntariado'),('sharing','Difusión')],max_length=20)),('message',models.TextField(blank=True,max_length=1200)),('phone',models.CharField(blank=True,max_length=30)),('created_at',models.DateTimeField(auto_now_add=True)),('animal',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='help_offers',to='adoptions.adoptionanimal')),('user',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='adoption_help_offers',to=settings.AUTH_USER_MODEL))],options={'ordering':['-created_at']}),
        migrations.AddIndex(model_name='adoptionanimal',index=models.Index(fields=['status','is_published','-created_at'],name='adoptions_a_status_00d0ad_idx')),
        migrations.AddIndex(model_name='adoptionanimal',index=models.Index(fields=['species','province','locality'],name='adoptions_a_species_008bc6_idx')),
        migrations.AddConstraint(model_name='adoptionanimal',constraint=models.UniqueConstraint(fields=('shelter','slug'),name='unique_adoption_slug_per_shelter')),
        migrations.AddConstraint(model_name='adoptionapplication',constraint=models.UniqueConstraint(fields=('animal','applicant'),name='unique_application_per_animal')),
        migrations.AddConstraint(model_name='helpoffer',constraint=models.UniqueConstraint(fields=('animal','user','help_type'),name='unique_help_offer_type')),
    ]
