from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action, api_view, parser_classes, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from clinics.models import Clinic
from lost_pets.models import LostPet
from pets.models import BirthdayCelebration, Pet

from .models import BlockedUser, Comment, PetFollow, PetSocialProfile, Post, Reaction, Report, SavedPost
from .permissions import IsOwnerOrModerator, is_community_moderator
from .throttles import CommunityActionThrottle, CommunityCommentThrottle, CommunityPostThrottle
from .serializers import (
    BlockedUserSerializer,
    CommentSerializer,
    PetSocialProfileSerializer,
    PostSerializer,
    ReportSerializer,
    absolute_file_url,
)


class CommunityPostPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 30


class CommunityPostViewSet(viewsets.ModelViewSet):
    serializer_class = PostSerializer
    pagination_class = CommunityPostPagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_throttles(self):
        if self.action == 'create':
            return [CommunityPostThrottle()]
        if self.action == 'comments_action' and self.request.method == 'POST':
            return [CommunityCommentThrottle()]
        if self.action in ('react', 'save_post'):
            return [CommunityActionThrottle()]
        return []

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [permissions.AllowAny()]
        if self.action in ('destroy', 'partial_update', 'update'):
            return [permissions.IsAuthenticated(), IsOwnerOrModerator()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = Post.objects.filter(
            is_public=True,
            moderation_status=Post.STATUS_PUBLISHED,
        ).filter(
            Q(related_lost_pet__isnull=True) | Q(related_lost_pet__expires_at__gt=timezone.now())
        ).select_related(
            'created_by', 'pet__owner', 'pet__social_profile', 'clinic__owner',
            'related_lost_pet__owner', 'related_birthday__pet',
        ).prefetch_related('comments__author').annotate(
            reactions_total=Count('reactions', distinct=True),
            comments_total=Count('comments', filter=Q(comments__moderation_status=Comment.STATUS_PUBLISHED), distinct=True),
        )

        request = self.request
        user = request.user
        if user.is_authenticated:
            blocked_ids = BlockedUser.objects.filter(blocker=user).values_list('blocked_id', flat=True)
            blocker_ids = BlockedUser.objects.filter(blocked=user).values_list('blocker_id', flat=True)
            queryset = queryset.exclude(created_by_id__in=list(blocked_ids) + list(blocker_ids))

        feed = request.query_params.get('feed')
        if feed == 'following':
            if not user.is_authenticated:
                return queryset.none()
            pet_ids = PetFollow.objects.filter(follower=user).values_list('pet_id', flat=True)
            queryset = queryset.filter(Q(pet_id__in=pet_ids) | Q(created_by=user))
        elif feed == 'saved':
            if not user.is_authenticated:
                return queryset.none()
            saved_ids = SavedPost.objects.filter(user=user).values_list('post_id', flat=True)
            queryset = queryset.filter(id__in=saved_ids)

        post_type = request.query_params.get('type')
        if post_type in dict(Post.TYPE_CHOICES):
            queryset = queryset.filter(post_type=post_type)
        pet_id = request.query_params.get('pet')
        if pet_id:
            queryset = queryset.filter(pet_id=pet_id)
        clinic_id = request.query_params.get('clinic')
        if clinic_id:
            queryset = queryset.filter(clinic_id=clinic_id)
        locality = request.query_params.get('locality')
        if locality:
            queryset = queryset.filter(locality__icontains=locality)
        province = request.query_params.get('province')
        if province:
            queryset = queryset.filter(province__icontains=province)
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(text__icontains=search)
                | Q(pet__name__icontains=search)
                | Q(clinic__name__icontains=search)
                | Q(related_lost_pet__pet_name__icontains=search)
            )
        return queryset.order_by('-created_at')

    def perform_update(self, serializer):
        instance = self.get_object()
        allowed = {'text', 'image'}
        cleaned = {key: value for key, value in serializer.validated_data.items() if key in allowed}
        for key, value in cleaned.items():
            setattr(instance, key, value)
        instance.save(update_fields=[*cleaned.keys(), 'updated_at'])

    @action(detail=True, methods=['post'])
    def react(self, request, pk=None):
        post = self.get_object()
        reaction, created = Reaction.objects.get_or_create(post=post, user=request.user)
        if not created:
            reaction.delete()
        return Response({
            'reacted': created,
            'reactions_count': post.reactions.count(),
        })

    @action(detail=True, methods=['post'])
    def save_post(self, request, pk=None):
        post = self.get_object()
        saved, created = SavedPost.objects.get_or_create(post=post, user=request.user)
        if not created:
            saved.delete()
        return Response({'saved': created})

    @action(detail=True, methods=['get', 'post'], url_path='comments')
    def comments_action(self, request, pk=None):
        post = self.get_object()
        if request.method == 'GET':
            comments = post.comments.filter(moderation_status=Comment.STATUS_PUBLISHED).select_related('author')
            if request.user.is_authenticated:
                blocked_ids = BlockedUser.objects.filter(blocker=request.user).values_list('blocked_id', flat=True)
                blocker_ids = BlockedUser.objects.filter(blocked=request.user).values_list('blocker_id', flat=True)
                comments = comments.exclude(author_id__in=list(blocked_ids) + list(blocker_ids))
            return Response(CommentSerializer(comments, many=True, context={'request': request}).data)
        serializer = CommentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        comment = serializer.save(post=post, author=request.user)
        return Response(CommentSerializer(comment, context={'request': request}).data, status=status.HTTP_201_CREATED)


class CommentViewSet(mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrModerator]

    def perform_destroy(self, instance):
        instance.delete()


class PetSocialProfileViewSet(viewsets.GenericViewSet):
    serializer_class = PetSocialProfileSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_throttles(self):
        return [CommunityActionThrottle()] if self.action == 'follow' else []

    def get_permissions(self):
        if self.action == 'retrieve':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_object(self):
        pet = get_object_or_404(Pet.objects.select_related('owner'), pk=self.kwargs['pk'])
        profile, _ = PetSocialProfile.objects.get_or_create(pet=pet)
        request = self.request
        if not profile.is_public:
            allowed = request.user.is_authenticated and (
                pet.owner_id == request.user.id or is_community_moderator(request.user)
            )
            if not allowed:
                from rest_framework.exceptions import NotFound
                raise NotFound('Este perfil no es público.')
        return profile

    def retrieve(self, request, pk=None):
        profile = self.get_object()
        return Response(self.get_serializer(profile, context={'request': request}).data)

    def partial_update(self, request, pk=None):
        profile = self.get_object()
        if profile.pet.owner_id != request.user.id and not is_community_moderator(request.user):
            return Response({'error': 'Solo el dueño puede editar este perfil.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(profile, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        if 'is_public' in serializer.validated_data:
            updated.pet.community_posts.update(is_public=updated.is_public)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def follow(self, request, pk=None):
        profile = self.get_object()
        pet = profile.pet
        if pet.owner_id == request.user.id:
            return Response({'error': 'No necesitás seguir a tu propia mascota.'}, status=status.HTTP_400_BAD_REQUEST)
        follow, created = PetFollow.objects.get_or_create(follower=request.user, pet=pet)
        if not created:
            follow.delete()
        return Response({'following': created, 'followers_count': pet.social_followers.count()})


class ReportViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_throttles(self):
        return [CommunityActionThrottle()] if self.action in ('create', 'moderate') else []

    def get_queryset(self):
        if is_community_moderator(self.request.user):
            queryset = Report.objects.select_related(
                'reporter', 'post', 'comment', 'reported_user', 'reviewed_by'
            )
            status_filter = self.request.query_params.get('status')
            if status_filter in dict(Report.STATUS_CHOICES):
                queryset = queryset.filter(status=status_filter)
            return queryset
        return Report.objects.filter(reporter=self.request.user)

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user)

    @action(detail=True, methods=['post'])
    def moderate(self, request, pk=None):
        if not is_community_moderator(request.user):
            return Response({'error': 'Acceso denegado.'}, status=status.HTTP_403_FORBIDDEN)
        report = self.get_object()
        decision = request.data.get('decision')
        notes = request.data.get('notes', '')
        if decision not in ('dismiss', 'hide', 'remove', 'review'):
            return Response({'error': 'Decisión inválida.'}, status=status.HTTP_400_BAD_REQUEST)
        if decision in ('hide', 'remove'):
            target_status = Post.STATUS_HIDDEN if decision == 'hide' else Post.STATUS_REMOVED
            if report.post_id:
                report.post.moderation_status = target_status
                report.post.save(update_fields=['moderation_status', 'updated_at'])
            elif report.comment_id:
                report.comment.moderation_status = target_status
                report.comment.save(update_fields=['moderation_status', 'updated_at'])
        report.status = {
            'dismiss': Report.STATUS_DISMISSED,
            'review': Report.STATUS_REVIEWED,
            'hide': Report.STATUS_ACTIONED,
            'remove': Report.STATUS_ACTIONED,
        }[decision]
        report.moderator_notes = notes
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.save(update_fields=['status', 'moderator_notes', 'reviewed_by', 'reviewed_at'])
        return Response(self.get_serializer(report).data)


class BlockedUserViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = BlockedUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_throttles(self):
        return [CommunityActionThrottle()] if self.action == 'toggle' else []

    def get_queryset(self):
        return BlockedUser.objects.filter(blocker=self.request.user).select_related('blocked')

    @action(detail=False, methods=['post'])
    def toggle(self, request):
        blocked_id = request.data.get('user_id')
        if not blocked_id:
            return Response({'error': 'Falta el usuario.'}, status=status.HTTP_400_BAD_REQUEST)
        if str(blocked_id) == str(request.user.id):
            return Response({'error': 'No podés bloquearte a vos mismo.'}, status=status.HTTP_400_BAD_REQUEST)
        from users.models import User
        if not User.objects.filter(pk=blocked_id).exists():
            return Response({'error': 'Usuario no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        block, created = BlockedUser.objects.get_or_create(blocker=request.user, blocked_id=blocked_id)
        if not created:
            block.delete()
        return Response({'blocked': created})


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def community_discover(request):
    user = request.user
    blocked_ids = []
    if user.is_authenticated:
        blocked_ids = list(BlockedUser.objects.filter(blocker=user).values_list('blocked_id', flat=True))

    suggested_pets = Pet.objects.filter(
        social_profile__is_public=True,
    ).exclude(owner_id__in=blocked_ids).select_related('owner', 'social_profile').annotate(
        followers_total=Count('social_followers', distinct=True),
        posts_total=Count('community_posts', filter=Q(community_posts__moderation_status=Post.STATUS_PUBLISHED), distinct=True),
    ).order_by('-followers_total', '-posts_total', '-created_at')
    if user.is_authenticated:
        suggested_pets = suggested_pets.exclude(owner=user)
    suggested_pets = suggested_pets[:6]

    clinics = Clinic.objects.filter(is_active=True).select_related('owner').annotate(
        posts_total=Count('community_posts', filter=Q(community_posts__moderation_status=Post.STATUS_PUBLISHED), distinct=True)
    ).order_by('-posts_total', '-created_at')[:5]

    lost = LostPet.objects.filter(expires_at__gt=timezone.now()).order_by('-created_at')[:5]
    birthdays = BirthdayCelebration.objects.filter(
        birthday_date__gte=timezone.localdate() - timedelta(days=2),
        birthday_date__lte=timezone.localdate() + timedelta(days=1),
        pet__social_profile__is_public=True,
    ).select_related('pet__owner').order_by('-birthday_date')[:5]

    return Response({
        'suggested_pets': [
            {
                'id': pet.id,
                'name': pet.name,
                'species_display': pet.get_species_display(),
                'breed': pet.breed,
                'photo': absolute_file_url(request, pet.photo),
                'locality': pet.owner.locality,
                'province': pet.owner.province,
                'followers_count': pet.followers_total,
                'following': bool(user.is_authenticated and PetFollow.objects.filter(follower=user, pet=pet).exists()),
            }
            for pet in suggested_pets
        ],
        'clinics': [
            {
                'id': clinic.id,
                'name': clinic.name,
                'slug': clinic.slug,
                'logo': absolute_file_url(request, clinic.logo),
                'locality': clinic.locality,
                'province': clinic.province,
                'is_24h': clinic.is_24h,
                'posts_count': clinic.posts_total,
            }
            for clinic in clinics
        ],
        'lost_pets': [
            {
                'id': item.id,
                'pet_name': item.pet_name or 'Mascota',
                'report_type': item.report_type,
                'photo': absolute_file_url(request, item.photo),
                'locality': item.locality,
                'province': item.province,
                'created_at': item.created_at,
            }
            for item in lost
        ],
        'birthdays': [
            {
                'id': item.id,
                'pet_id': item.pet_id,
                'pet_name': item.pet.name,
                'age': item.age,
                'photo': absolute_file_url(request, item.pet.photo),
                'birthday_date': item.birthday_date,
            }
            for item in birthdays
        ],
    })
