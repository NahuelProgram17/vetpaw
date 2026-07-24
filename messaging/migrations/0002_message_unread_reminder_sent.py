from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('messaging', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='unread_reminder_sent',
            field=models.BooleanField(default=False),
        ),
        migrations.AddIndex(
            model_name='message',
            index=models.Index(
                fields=['read', 'unread_reminder_sent', 'created_at'],
                name='msg_unread_reminder_idx',
            ),
        ),
    ]
