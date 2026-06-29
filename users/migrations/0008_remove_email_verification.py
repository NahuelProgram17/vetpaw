from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0007_alter_user_email'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='email_verified',
        ),
        migrations.RemoveField(
            model_name='user',
            name='email_verification_token',
        ),
    ]
