from secrets import token_urlsafe
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from clinics.models import Clinic
from rest_framework.test import APITestCase

from pets.models import Pet
from users.models import User

from .models import BlockedUser, Comment, CommunityNotification, PetFollow, PetSocialProfile, Post, PushSubscription, Reaction, Report


class CommunityApiTests(APITestCase):
    def setUp(self):
        # Las contraseñas se generan durante cada ejecución.
        # Así no quedan credenciales fijas escritas en GitHub.
        self.owner_password = token_urlsafe(24)
        self.other_password = token_urlsafe(24)

        self.owner = User.objects.create_user(
            username="owner_test",
            email="owner@example.com",
            password=self.owner_password,
            role="owner",
            is_approved=True,
            locality="Moreno",
            province="Buenos Aires",
        )

        self.other = User.objects.create_user(
            username="other_test",
            email="other@example.com",
            password=self.other_password,
            role="owner",
            is_approved=True,
        )

        self.moderator = User.objects.create_user(
            username="moderator_test",
            email="moderator@example.com",
            password=token_urlsafe(24),
            role="owner",
            is_approved=True,
        )
        moderator_group, _ = Group.objects.get_or_create(name="community_moderators")
        self.moderator.groups.add(moderator_group)

        self.pet = Pet.objects.create(
            owner=self.owner,
            name="Toby",
            species="dog",
            sex="male",
        )

    def test_public_feed_and_owner_can_publish(self):
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            "/api/community/posts/",
            {
                "pet": self.pet.id,
                "text": "Hola comunidad",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)

        self.client.force_authenticate(None)

        feed = self.client.get("/api/community/posts/")

        self.assertEqual(feed.status_code, 200)
        self.assertEqual(feed.data["count"], 1)

    def test_react_comment_follow_and_report(self):
        post = Post.objects.create(
            created_by=self.owner,
            pet=self.pet,
            text="Una foto linda",
        )

        self.client.force_authenticate(self.other)

        reaction_response = self.client.post(
            f"/api/community/posts/{post.id}/react/"
        )
        self.assertEqual(reaction_response.status_code, 200)
        self.assertTrue(
            Reaction.objects.filter(
                post=post,
                user=self.other,
            ).exists()
        )

        comment_response = self.client.post(
            f"/api/community/posts/{post.id}/comments/",
            {"text": "Hermoso"},
        )
        self.assertEqual(comment_response.status_code, 201)
        self.assertTrue(
            Comment.objects.filter(
                post=post,
                author=self.other,
            ).exists()
        )

        follow_response = self.client.post(
            f"/api/community/pets/{self.pet.id}/follow/"
        )
        self.assertEqual(follow_response.status_code, 200)
        self.assertTrue(
            PetFollow.objects.filter(
                pet=self.pet,
                follower=self.other,
            ).exists()
        )

        report_response = self.client.post(
            "/api/community/reports/",
            {
                "post": post.id,
                "reason": "spam",
            },
        )
        self.assertEqual(report_response.status_code, 201)
        self.assertTrue(
            Report.objects.filter(
                post=post,
                reporter=self.other,
            ).exists()
        )

    def test_feed_can_filter_by_hashtag(self):
        Post.objects.create(
            created_by=self.owner,
            pet=self.pet,
            text="Paseo de domingo #MiMascota",
        )

        Post.objects.create(
            created_by=self.owner,
            pet=self.pet,
            text="Otra publicación sin etiqueta",
        )

        response = self.client.get(
            "/api/community/posts/?hashtag=MiMascota"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertIn(
            "#MiMascota",
            response.data["results"][0]["text"],
        )

    def test_discover_and_public_pet_profile(self):
        discover = self.client.get("/api/community/discover/")

        self.assertEqual(discover.status_code, 200)
        self.assertIn(
            "suggested_pets",
            discover.data,
        )

        profile = self.client.get(
            f"/api/community/pets/{self.pet.id}/"
        )

        self.assertEqual(profile.status_code, 200)
        self.assertEqual(
            profile.data["name"],
            "Toby",
        )
    def test_only_owner_or_moderator_can_delete_content(self):
        post = Post.objects.create(created_by=self.owner, pet=self.pet, text="Contenido")
        comment = Comment.objects.create(post=post, author=self.owner, text="Comentario")

        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.delete(f"/api/community/posts/{post.id}/").status_code, 403)
        self.assertEqual(self.client.delete(f"/api/community/comments/{comment.id}/").status_code, 403)

        self.client.force_authenticate(self.moderator)
        self.assertEqual(self.client.delete(f"/api/community/comments/{comment.id}/").status_code, 204)
        self.assertEqual(self.client.delete(f"/api/community/posts/{post.id}/").status_code, 204)

    def test_only_moderator_can_moderate_reports(self):
        post = Post.objects.create(created_by=self.owner, pet=self.pet, text="Reportable")
        report = Report.objects.create(reporter=self.other, post=post, reason=Report.REASON_SPAM)

        self.client.force_authenticate(self.other)
        denied = self.client.post(
            f"/api/community/reports/{report.id}/moderate/",
            {"decision": "hide", "notes": "No debería poder"},
            format="json",
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(self.moderator)
        allowed = self.client.post(
            f"/api/community/reports/{report.id}/moderate/",
            {"decision": "hide", "notes": "Contenido ocultado"},
            format="json",
        )
        self.assertEqual(allowed.status_code, 200)
        post.refresh_from_db()
        report.refresh_from_db()
        self.assertEqual(post.moderation_status, Post.STATUS_HIDDEN)
        self.assertEqual(report.status, Report.STATUS_ACTIONED)
        self.assertEqual(report.reviewed_by, self.moderator)

    def test_private_pet_profile_is_hidden_from_other_users_but_visible_to_moderator(self):
        profile = self.pet.social_profile
        profile.is_public = False
        profile.save(update_fields=["is_public"])

        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f"/api/community/pets/{self.pet.id}/").status_code, 404)

        self.client.force_authenticate(self.moderator)
        self.assertEqual(self.client.get(f"/api/community/pets/{self.pet.id}/").status_code, 200)


    def test_social_notifications_are_created_and_can_be_marked_read(self):
        post = Post.objects.create(created_by=self.owner, pet=self.pet, text='Una foto')

        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(f'/api/community/posts/{post.id}/react/').status_code, 200)
        comment_response = self.client.post(
            f'/api/community/posts/{post.id}/comments/',
            {'text': '¡Qué lindo Toby!'},
            format='json',
        )
        self.assertEqual(comment_response.status_code, 201)
        self.assertEqual(self.client.post(f'/api/community/pets/{self.pet.id}/follow/').status_code, 200)

        self.client.force_authenticate(self.owner)
        unread = self.client.get('/api/community/notifications/unread_count/')
        self.assertEqual(unread.status_code, 200)
        self.assertEqual(unread.data['unread'], 3)

        response = self.client.get('/api/community/notifications/')
        self.assertEqual(response.status_code, 200)
        notifications = response.data['results']
        self.assertEqual(len(notifications), 3)
        self.assertEqual(
            {item['notification_type'] for item in notifications},
            {'reaction', 'comment', 'follow'},
        )
        self.assertTrue(all(item['target_url'] for item in notifications))
        comment_notification = next(
            item for item in notifications
            if item['notification_type'] == CommunityNotification.TYPE_COMMENT
        )
        self.assertEqual(comment_notification['comment_id'], comment_response.data['id'])
        self.assertEqual(
            comment_notification['target_url'],
            f"/comunidad?publicacion={post.id}&comentario={comment_response.data['id']}",
        )

        from .push_utils import notification_target_url
        comment_model = CommunityNotification.objects.get(pk=comment_notification['id'])
        self.assertEqual(
            notification_target_url(comment_model),
            f"/comunidad?publicacion={post.id}&comentario={comment_response.data['id']}",
        )

        first_id = notifications[0]['id']
        marked = self.client.post(f'/api/community/notifications/{first_id}/mark_read/')
        self.assertEqual(marked.status_code, 200)
        self.assertTrue(marked.data['is_read'])

        marked_all = self.client.post('/api/community/notifications/mark_all_read/')
        self.assertEqual(marked_all.status_code, 200)
        self.assertEqual(self.client.get('/api/community/notifications/unread_count/').data['unread'], 0)

    def test_self_actions_do_not_create_notifications(self):
        post = Post.objects.create(created_by=self.owner, pet=self.pet, text='Publicación propia')
        self.client.force_authenticate(self.owner)

        self.assertEqual(self.client.post(f'/api/community/posts/{post.id}/react/').status_code, 200)
        self.assertEqual(
            self.client.post(
                f'/api/community/posts/{post.id}/comments/',
                {'text': 'Comentario propio'},
                format='json',
            ).status_code,
            201,
        )

        self.assertEqual(CommunityNotification.objects.count(), 0)

    def test_removing_reaction_or_follow_removes_the_notification(self):
        post = Post.objects.create(created_by=self.owner, pet=self.pet, text='Una foto')
        self.client.force_authenticate(self.other)

        self.client.post(f'/api/community/posts/{post.id}/react/')
        self.client.post(f'/api/community/pets/{self.pet.id}/follow/')
        self.assertEqual(CommunityNotification.objects.count(), 2)

        self.client.post(f'/api/community/posts/{post.id}/react/')
        self.client.post(f'/api/community/pets/{self.pet.id}/follow/')
        self.assertEqual(CommunityNotification.objects.count(), 0)

    def test_unread_comments_are_grouped_and_blocks_prevent_notifications(self):
        post = Post.objects.create(created_by=self.owner, pet=self.pet, text='Una foto')
        self.client.force_authenticate(self.other)

        self.client.post(
            f'/api/community/posts/{post.id}/comments/',
            {'text': 'Primer comentario'},
            format='json',
        )
        self.client.post(
            f'/api/community/posts/{post.id}/comments/',
            {'text': 'Segundo comentario'},
            format='json',
        )

        grouped = CommunityNotification.objects.get(
            recipient=self.owner,
            actor=self.other,
            notification_type=CommunityNotification.TYPE_COMMENT,
        )
        self.assertEqual(grouped.extra_text, 'Segundo comentario')

        CommunityNotification.objects.all().delete()
        BlockedUser.objects.create(blocker=self.owner, blocked=self.other)
        self.client.post(f'/api/community/posts/{post.id}/react/')
        self.assertEqual(CommunityNotification.objects.count(), 0)


    def test_clinic_receives_social_notifications_and_other_users_cannot_read_them(self):
        clinic_user = User.objects.create_user(
            username='clinic_test',
            email='clinic@example.com',
            password=token_urlsafe(24),
            role='clinic',
            is_approved=True,
        )
        clinic = Clinic.objects.create(
            owner=clinic_user,
            name='Veterinaria VetPaw',
            address='Calle 123',
            province='Buenos Aires',
            locality='Moreno',
        )
        post = Post.objects.create(
            created_by=clinic_user,
            clinic=clinic,
            post_type=Post.TYPE_CLINIC,
            text='Consejo veterinario',
        )

        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(f'/api/community/posts/{post.id}/react/').status_code, 200)
        notification = CommunityNotification.objects.get(recipient=clinic_user)

        self.client.force_authenticate(clinic_user)
        self.assertEqual(self.client.get('/api/community/notifications/unread_count/').data['unread'], 1)

        self.client.force_authenticate(self.owner)
        denied = self.client.post(f'/api/community/notifications/{notification.id}/mark_read/')
        self.assertEqual(denied.status_code, 404)


    def test_push_subscription_can_be_registered_checked_and_disabled(self):
        self.client.force_authenticate(self.owner)
        payload = {
            'endpoint': 'https://push.example.com/subscriptions/owner-device',
            'keys': {'p256dh': 'public-browser-key', 'auth': 'auth-secret'},
            'device_name': 'Chrome en Windows',
            'user_agent': 'VetPaw test browser',
        }

        created = self.client.post('/api/community/push/subscribe/', payload, format='json')
        self.assertEqual(created.status_code, 201)
        subscription = PushSubscription.objects.get(endpoint=payload['endpoint'])
        self.assertEqual(subscription.user, self.owner)
        self.assertTrue(subscription.is_active)
        self.assertEqual(subscription.device_name, 'Chrome en Windows')

        checked = self.client.get(
            '/api/community/push/status/',
            {'endpoint': payload['endpoint']},
        )
        self.assertEqual(checked.status_code, 200)
        self.assertTrue(checked.data['active'])

        disabled = self.client.post(
            '/api/community/push/unsubscribe/',
            {'endpoint': payload['endpoint']},
            format='json',
        )
        self.assertEqual(disabled.status_code, 200)
        subscription.refresh_from_db()
        self.assertFalse(subscription.is_active)

    def test_push_subscription_rejects_missing_browser_keys(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            '/api/community/push/subscribe/',
            {
                'endpoint': 'https://push.example.com/subscriptions/invalid',
                'keys': {'p256dh': '', 'auth': ''},
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(PushSubscription.objects.count(), 0)

    @override_settings(
        VAPID_PUBLIC_KEY='public-vapid-key',
        VAPID_PRIVATE_KEY='private-vapid-key',
        VAPID_SUBJECT='mailto:test@example.com',
    )
    @patch('community.views.send_test_push', return_value={'sent': True})
    def test_push_config_and_test_notification(self, mocked_send):
        self.client.force_authenticate(self.owner)
        subscription = PushSubscription.objects.create(
            user=self.owner,
            endpoint='https://push.example.com/subscriptions/test-device',
            p256dh='public-browser-key',
            auth='auth-secret',
            is_active=True,
        )

        config = self.client.get('/api/community/push/config/')
        self.assertEqual(config.status_code, 200)
        self.assertTrue(config.data['enabled'])
        self.assertEqual(config.data['public_key'], 'public-vapid-key')

        sent = self.client.post(
            '/api/community/push/test/',
            {'endpoint': subscription.endpoint},
            format='json',
        )
        self.assertEqual(sent.status_code, 200)
        self.assertTrue(sent.data['sent'])
        mocked_send.assert_called_once_with(subscription)

    @patch('community.notification_utils.schedule_push_notification')
    def test_social_activity_schedules_a_phone_push(self, mocked_schedule):
        post = Post.objects.create(created_by=self.owner, pet=self.pet, text='Nueva foto')
        self.client.force_authenticate(self.other)

        response = self.client.post(f'/api/community/posts/{post.id}/react/')

        self.assertEqual(response.status_code, 200)
        notification = CommunityNotification.objects.get(
            recipient=self.owner,
            actor=self.other,
            notification_type=CommunityNotification.TYPE_REACTION,
        )
        mocked_schedule.assert_called_once_with(notification)

    @override_settings(
        VAPID_PUBLIC_KEY='public-vapid-key',
        VAPID_PRIVATE_KEY='private-vapid-key',
        VAPID_SUBJECT='mailto:test@example.com',
    )
    @patch('community.push_utils.webpush')
    def test_successful_push_updates_subscription_health(self, mocked_webpush):
        from .push_utils import send_payload_to_subscription

        subscription = PushSubscription.objects.create(
            user=self.owner,
            endpoint='https://push.example.com/subscriptions/healthy-device',
            p256dh='public-browser-key',
            auth='auth-secret',
            failure_count=2,
            is_active=True,
        )

        result = send_payload_to_subscription(
            subscription,
            {'title': 'VetPaw', 'body': 'Prueba', 'url': '/notifications'},
        )

        self.assertTrue(result['sent'])
        subscription.refresh_from_db()
        self.assertEqual(subscription.failure_count, 0)
        self.assertIsNotNone(subscription.last_success_at)
        self.assertTrue(subscription.is_active)
        mocked_webpush.assert_called_once()


    def test_explore_searches_pets_clinics_posts_and_hashtags(self):
        cat = Pet.objects.create(
            owner=self.other,
            name='Luna',
            species='cat',
            breed='Siamesa',
            sex='female',
        )
        PetSocialProfile.objects.get_or_create(pet=cat)
        clinic_user = User.objects.create_user(
            username='clinic_explore',
            email='clinic-explore@example.com',
            password=token_urlsafe(24),
            role='clinic',
            is_approved=True,
        )
        Clinic.objects.create(
            owner=clinic_user,
            name='Veterinaria Luna',
            address='Calle 123',
            locality='Moreno',
            province='Buenos Aires',
            is_24h=True,
            services=['Guardia', 'Vacunación'],
        )
        Post.objects.create(
            created_by=self.other,
            pet=cat,
            text='Luna jugando con una caja #GatosFelices',
            locality='Moreno',
            province='Buenos Aires',
        )

        response = self.client.get('/api/community/explore/', {'q': 'Luna'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['counts']['pets'], 1)
        self.assertEqual(response.data['counts']['clinics'], 1)
        self.assertEqual(response.data['counts']['posts'], 1)
        self.assertEqual(response.data['results']['pets'][0]['name'], 'Luna')
        self.assertTrue(any(item['kind'] == 'pet' for item in response.data['suggestions']))

        smart_query = self.client.get('/api/community/explore/', {'q': 'Guardia Moreno', 'section': 'clinics'})
        self.assertEqual(smart_query.status_code, 200)
        self.assertEqual(smart_query.data['pagination']['total'], 1)
        self.assertEqual(smart_query.data['results']['clinics'][0]['name'], 'Veterinaria Luna')

        hashtags = self.client.get('/api/community/explore/', {'q': 'Gatos', 'section': 'hashtags'})
        self.assertEqual(hashtags.status_code, 200)
        self.assertEqual(hashtags.data['results']['hashtags'][0]['name'], 'gatosfelices')

    def test_explore_supports_species_location_and_24h_filters(self):
        cat = Pet.objects.create(
            owner=self.other,
            name='Mishi',
            species='cat',
            sex='female',
        )
        self.other.locality = 'Merlo'
        self.other.province = 'Buenos Aires'
        self.other.save(update_fields=['locality', 'province'])
        PetSocialProfile.objects.get_or_create(pet=cat)

        clinic_user = User.objects.create_user(
            username='clinic_24h',
            email='clinic-24h@example.com',
            password=token_urlsafe(24),
            role='clinic',
            is_approved=True,
        )
        Clinic.objects.create(
            owner=clinic_user,
            name='Guardia Animal',
            address='Avenida Siempre Viva',
            locality='Merlo',
            province='Buenos Aires',
            is_24h=True,
        )

        pets = self.client.get('/api/community/explore/', {
            'section': 'pets', 'species': 'cat', 'locality': 'Merlo',
        })
        self.assertEqual(pets.status_code, 200)
        self.assertEqual(pets.data['pagination']['total'], 1)
        self.assertEqual(pets.data['results']['pets'][0]['name'], 'Mishi')

        clinics = self.client.get('/api/community/explore/', {
            'section': 'clinics', 'locality': 'Merlo', 'is_24h': 'true',
        })
        self.assertEqual(clinics.status_code, 200)
        self.assertEqual(clinics.data['pagination']['total'], 1)
        self.assertTrue(clinics.data['results']['clinics'][0]['is_24h'])

    def test_explore_hides_private_and_blocked_profiles(self):
        private_pet = Pet.objects.create(
            owner=self.other,
            name='Oculta',
            species='dog',
            sex='female',
        )
        private_profile, _ = PetSocialProfile.objects.get_or_create(pet=private_pet)
        private_profile.is_public = False
        private_profile.save(update_fields=['is_public'])

        visible_pet = Pet.objects.create(
            owner=self.moderator,
            name='Bloqueada',
            species='dog',
            sex='female',
        )
        PetSocialProfile.objects.get_or_create(pet=visible_pet)
        Post.objects.create(created_by=self.moderator, pet=visible_pet, text='Contenido bloqueado')
        BlockedUser.objects.create(blocker=self.owner, blocked=self.moderator)

        self.client.force_authenticate(self.owner)
        private_result = self.client.get('/api/community/explore/', {'q': 'Oculta'})
        blocked_result = self.client.get('/api/community/explore/', {'q': 'Bloqueada'})

        self.assertEqual(private_result.data['counts']['pets'], 0)
        self.assertEqual(blocked_result.data['counts']['pets'], 0)
        self.assertEqual(blocked_result.data['counts']['posts'], 0)

    def test_explore_popular_posts_prioritizes_engagement(self):
        popular = Post.objects.create(created_by=self.owner, pet=self.pet, text='Publicación popular')
        recent = Post.objects.create(created_by=self.owner, pet=self.pet, text='Publicación reciente')
        Reaction.objects.create(post=popular, user=self.other)
        Comment.objects.create(post=popular, author=self.other, text='Hermoso')

        response = self.client.get('/api/community/explore/', {
            'section': 'posts', 'sort': 'popular',
        })

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data['pagination']['total'], 2)
        self.assertEqual(response.data['results']['posts'][0]['id'], popular.id)
