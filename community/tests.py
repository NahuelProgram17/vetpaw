from secrets import token_urlsafe

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APITestCase

from pets.models import Pet
from users.models import User

from .models import Comment, PetFollow, Post, Reaction, Report


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