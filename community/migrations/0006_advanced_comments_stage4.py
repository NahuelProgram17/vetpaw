from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('community', '0005_social_profiles_stage3'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='shares_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='comment',
            name='parent',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='replies',
                to='community.comment',
            ),
        ),
        migrations.AddIndex(
            model_name='comment',
            index=models.Index(
                fields=['parent', 'moderation_status', 'created_at'],
                name='comm_comment_parent_idx',
            ),
        ),
        migrations.CreateModel(
            name='CommentReaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('comment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reactions', to='community.comment')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='community_comment_reactions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'indexes': [models.Index(fields=['comment', 'created_at'], name='comm_creact_comment_idx')],
                'constraints': [models.UniqueConstraint(fields=('comment', 'user'), name='unique_community_comment_reaction')],
            },
        ),
        migrations.AlterField(
            model_name='communitynotification',
            name='notification_type',
            field=models.CharField(
                choices=[
                    ('reaction', 'Patita en publicación'),
                    ('comment', 'Comentario en publicación'),
                    ('follow', 'Nuevo seguidor'),
                    ('comment_reaction', 'Patita en comentario'),
                    ('reply', 'Respuesta a comentario'),
                    ('mention', 'Mención'),
                ],
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name='communitynotification',
            constraint=models.UniqueConstraint(
                condition=models.Q(('comment__isnull', False), ('notification_type', 'comment_reaction')),
                fields=('recipient', 'actor', 'comment', 'notification_type'),
                name='unique_comment_reaction_notification',
            ),
        ),
        migrations.AddConstraint(
            model_name='communitynotification',
            constraint=models.UniqueConstraint(
                condition=models.Q(('comment__isnull', False), ('notification_type', 'reply')),
                fields=('recipient', 'actor', 'comment', 'notification_type'),
                name='unique_reply_notification',
            ),
        ),
        migrations.AddConstraint(
            model_name='communitynotification',
            constraint=models.UniqueConstraint(
                condition=models.Q(('comment__isnull', True), ('notification_type', 'mention'), ('post__isnull', False)),
                fields=('recipient', 'actor', 'post', 'notification_type'),
                name='unique_post_mention_notification',
            ),
        ),
        migrations.AddConstraint(
            model_name='communitynotification',
            constraint=models.UniqueConstraint(
                condition=models.Q(('comment__isnull', False), ('notification_type', 'mention')),
                fields=('recipient', 'actor', 'comment', 'notification_type'),
                name='unique_comment_mention_notification',
            ),
        ),
    ]
