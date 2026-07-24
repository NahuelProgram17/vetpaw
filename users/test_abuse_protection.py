from secrets import token_urlsafe

from django.contrib.auth.models import Group
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APITestCase

from community.models import PetFollow, Post, Report
from messaging.models import Message
from pets.models import Pet
from users.models import AbuseAction, AbuseSignal, AccountSanction, User


class AbuseProtectionApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user(
            username='abuse-owner',
            email='abuse-owner@vetpaw.test',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
        )
        self.other = User.objects.create_user(
            username='abuse-other',
            email='abuse-other@vetpaw.test',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
        )
        self.admin = User.objects.create_user(
            username='abuse-admin',
            email='abuse-admin@vetpaw.test',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
            is_staff=True,
        )
        self.pet = Pet.objects.create(
            owner=self.owner,
            name='Toby Abuse',
            species='dog',
            sex='male',
        )
        self.other_pet = Pet.objects.create(
            owner=self.other,
            name='Luna Abuse',
            species='dog',
            sex='female',
        )

    def test_duplicate_post_is_blocked_and_signal_is_created(self):
        self.client.force_authenticate(self.owner)
        payload = {'pet': self.pet.id, 'text': 'Este contenido largo no debe publicarse dos veces seguidas.'}
        first = self.client.post('/api/community/posts/', payload, format='multipart')
        second = self.client.post('/api/community/posts/', payload, format='multipart')
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(second.status_code, 429, second.data)
        self.assertEqual(Post.objects.filter(created_by=self.owner).count(), 1)
        self.assertTrue(AbuseSignal.objects.filter(
            user=self.owner,
            category=AbuseSignal.CATEGORY_DUPLICATE_CONTENT,
        ).exists())

    def test_repeated_link_is_blocked_on_fourth_post(self):
        self.client.force_authenticate(self.owner)
        link = 'https://example.com/promocion'
        texts = [
            f'Encontré una promoción interesante para alimentos balanceados {link}',
            f'Comparto una página con información sobre paseos responsables {link}',
            f'Esta dirección tiene una guía distinta para cuidar animales mayores {link}',
        ]
        for text in texts:
            response = self.client.post('/api/community/posts/', {
                'pet': self.pet.id,
                'text': text,
            }, format='multipart')
            self.assertEqual(response.status_code, 201, response.data)
        blocked = self.client.post('/api/community/posts/', {
            'pet': self.pet.id,
            'text': f'Una cuarta publicación vuelve a colocar exactamente el mismo enlace {link}',
        }, format='multipart')
        self.assertEqual(blocked.status_code, 429, blocked.data)
        self.assertTrue(AbuseSignal.objects.filter(
            user=self.owner,
            category=AbuseSignal.CATEGORY_REPEATED_LINK,
        ).exists())

    def test_duplicate_comment_is_blocked(self):
        post = Post.objects.create(created_by=self.other, pet=self.other_pet, text='Publicación para comentar')
        self.client.force_authenticate(self.owner)
        payload = {'text': 'Este comentario suficientemente largo está repetido.'}
        first = self.client.post(f'/api/community/posts/{post.id}/comments/', payload, format='json')
        second = self.client.post(f'/api/community/posts/{post.id}/comments/', payload, format='json')
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(second.status_code, 429, second.data)

    def test_duplicate_message_is_blocked(self):
        self.client.force_authenticate(self.owner)
        payload = {
            'recipient': self.other.id,
            'content': 'Este mensaje suficientemente largo no debe repetirse enseguida.',
        }
        first = self.client.post('/api/messages/', payload, format='json')
        second = self.client.post('/api/messages/', payload, format='json')
        third = self.client.post('/api/messages/', payload, format='json')
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(third.status_code, 429, third.data)
        self.assertEqual(Message.objects.filter(sender=self.owner).count(), 2)

    def test_follow_burst_is_throttled_and_recorded(self):
        self.client.force_authenticate(self.owner)
        last = None
        for _ in range(13):
            last = self.client.post(f'/api/community/profiles/pet/{self.other_pet.id}/follow/')
        self.assertEqual(last.status_code, 429, last.data)
        self.assertTrue(AbuseSignal.objects.filter(
            user=self.owner,
            category=AbuseSignal.CATEGORY_MASS_FOLLOW,
        ).exists())

    def test_duplicate_pending_report_is_rejected_and_recorded(self):
        post = Post.objects.create(created_by=self.other, pet=self.other_pet, text='Contenido reportable')
        self.client.force_authenticate(self.owner)
        payload = {'post': post.id, 'reason': Report.REASON_SPAM, 'details': 'Revisión solicitada.'}
        first = self.client.post('/api/community/reports/', payload, format='json')
        second = self.client.post('/api/community/reports/', payload, format='json')
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(second.status_code, 400, second.data)
        self.assertEqual(Report.objects.filter(reporter=self.owner, post=post).count(), 1)
        self.assertTrue(AbuseSignal.objects.filter(
            user=self.owner,
            category=AbuseSignal.CATEGORY_FALSE_REPORT,
        ).exists())

    def test_three_dismissed_reports_flag_the_reporter(self):
        moderator_group, _ = Group.objects.get_or_create(name='community_moderators')
        self.admin.groups.add(moderator_group)
        reports = []
        self.client.force_authenticate(self.owner)
        for index in range(3):
            post = Post.objects.create(
                created_by=self.other,
                pet=self.other_pet,
                text=f'Contenido diferente {index}',
            )
            response = self.client.post('/api/community/reports/', {
                'post': post.id,
                'reason': Report.REASON_OTHER,
                'details': f'Reporte distinto {index}',
            }, format='json')
            self.assertEqual(response.status_code, 201, response.data)
            reports.append(response.data['id'])
        self.client.force_authenticate(self.admin)
        for report_id in reports:
            response = self.client.post(
                f'/api/community/reports/{report_id}/moderate/',
                {'decision': 'dismiss', 'notes': 'No corresponde.'},
                format='json',
            )
            self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(AbuseSignal.objects.filter(
            user=self.owner,
            category=AbuseSignal.CATEGORY_FALSE_REPORT,
            action_key='report',
        ).exists())

    def test_registration_burst_is_flagged_and_then_throttled(self):
        ip = '203.0.113.55'
        for index in range(3):
            password = token_urlsafe(24)
            response = self.client.post('/api/users/register/', {
                'username': f'burst-user-{index}',
                'email': f'burst-user-{index}@vetpaw.test',
                'password': password,
                'password2': password,
                'first_name': 'Prueba',
                'last_name': 'Registro',
            }, format='json', REMOTE_ADDR=ip)
            self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(AbuseSignal.objects.filter(
            category=AbuseSignal.CATEGORY_REGISTRATION_BURST,
            ip_address=ip,
        ).exists())
        password = token_urlsafe(24)
        blocked = self.client.post('/api/users/register/', {
            'username': 'burst-user-4',
            'email': 'burst-user-4@vetpaw.test',
            'password': password,
            'password2': password,
        }, format='json', REMOTE_ADDR=ip)
        self.assertEqual(blocked.status_code, 429, blocked.data)

    def test_non_admin_cannot_access_abuse_panel(self):
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get('/api/users/admin/abuse/signals/').status_code, 403)
        self.assertEqual(self.client.get('/api/users/admin/abuse/accounts/').status_code, 403)

    def test_admin_can_list_and_review_signals(self):
        signal = AbuseSignal.objects.create(
            user=self.owner,
            category=AbuseSignal.CATEGORY_DUPLICATE_CONTENT,
            severity=AbuseSignal.SEVERITY_HIGH,
            action_key='post',
            occurrences=3,
        )
        self.client.force_authenticate(self.admin)
        listing = self.client.get('/api/users/admin/abuse/signals/?status=pending')
        accounts = self.client.get('/api/users/admin/abuse/accounts/')
        self.assertEqual(listing.status_code, 200, listing.data)
        self.assertEqual(accounts.status_code, 200, accounts.data)
        self.assertTrue(any(row['id'] == signal.id for row in listing.data['results']))
        self.assertTrue(any(row['user_id'] == self.owner.id for row in accounts.data['results']))
        reviewed = self.client.post(
            f'/api/users/admin/abuse/signals/{signal.id}/',
            {'decision': 'review', 'notes': 'Revisada manualmente.'},
            format='json',
        )
        self.assertEqual(reviewed.status_code, 200, reviewed.data)
        signal.refresh_from_db()
        self.assertEqual(signal.status, AbuseSignal.STATUS_REVIEWED)
        self.assertEqual(signal.reviewed_by, self.admin)

    def test_sanction_can_be_linked_to_abuse_signal(self):
        signal = AbuseSignal.objects.create(
            user=self.owner,
            category=AbuseSignal.CATEGORY_ACCOUNT_RISK,
            severity=AbuseSignal.SEVERITY_HIGH,
            action_key='new_account_activity',
        )
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            f'/api/users/admin/moderation/accounts/{self.owner.id}/',
            {
                'action': 'suspend',
                'days': 3,
                'reason': 'Actividad sospechosa confirmada.',
                'source_abuse_signal_id': signal.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        sanction = AccountSanction.objects.get(user=self.owner)
        signal.refresh_from_db()
        self.assertEqual(sanction.source_abuse_signal_id, signal.id)
        self.assertEqual(signal.status, AbuseSignal.STATUS_ACTIONED)
