from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('community', '0003_pushsubscription'),
        ('partners', '0001_initial'),
    ]
    operations = [
        migrations.AddField(
            model_name='post',
            name='business',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='community_posts', to='partners.businessprofile'),
        ),
        migrations.AddField(
            model_name='post',
            name='shelter',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='community_posts', to='partners.shelterprofile'),
        ),
        migrations.AlterField(
            model_name='post',
            name='post_type',
            field=models.CharField(choices=[('normal', 'Publicación'), ('birthday', 'Cumpleaños'), ('lost', 'Mascota perdida/encontrada'), ('clinic', 'Veterinaria'), ('business', 'Negocio de mascotas'), ('shelter', 'Refugio o rescatista'), ('adoption', 'Adopción')], default='normal', max_length=20),
        ),
        migrations.AddIndex(model_name='post', index=models.Index(fields=['business', '-created_at'], name='community_p_busines_3c2719_idx')),
        migrations.AddIndex(model_name='post', index=models.Index(fields=['shelter', '-created_at'], name='community_p_shelter_ca21b8_idx')),
    ]
