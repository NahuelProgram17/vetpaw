from django.db import migrations


def create_permission_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('users', 'User')

    admin_group, _ = Group.objects.get_or_create(name='vetpaw_admins')
    moderator_group, _ = Group.objects.get_or_create(name='community_moderators')

    # Conserva el acceso de las cuentas administrativas existentes sin que la
    # aplicación dependa del nombre de usuario en cada request.
    admins = User.objects.filter(is_staff=True) | User.objects.filter(is_superuser=True)
    legacy_admin = User.objects.filter(username='jaime17')

    for user in (admins | legacy_admin).distinct():
        admin_group.user_set.add(user)
        moderator_group.user_set.add(user)


def remove_permission_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=['vetpaw_admins', 'community_moderators']).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0008_remove_email_verification'),
    ]

    operations = [
        migrations.RunPython(create_permission_groups, remove_permission_groups),
    ]
