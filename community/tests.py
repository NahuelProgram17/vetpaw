from secrets import token_urlsafe

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from clinics.models import Clinic
from rest_framework.test import APITestCase

from pets.models import Pet
from users.models import User

from .models import BlockedUser, Comment, CommunityNotification, PetFollow, Post, Reaction, Report


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
        self.assertEqual(
            self.client.post(
                f'/api/community/posts/{post.id}/comments/',
                {'text': '¡Qué lindo Toby!'},
                format='json',
            ).status_code,
            201,
        )
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
