from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from community.models import Post
from community.privacy import privacy_for
from messaging.models import Message
from partners.models import BusinessProfile
from users.permissions import is_vetpaw_admin

from .models import (
    BusinessAccess,
    BusinessFavorite,
    BusinessInquiry,
    BusinessProfileView,
    BusinessReservation,
    CatalogItem,
    Promotion,
)
from .notifications import create_business_notification
from .serializers import (
    BusinessAccessSerializer,
    BusinessFavoriteSerializer,
    BusinessInquirySerializer,
    BusinessReservationSerializer,
    CatalogItemSerializer,
    PromotionSerializer,
)


def owned_business(user):
    if not user.is_authenticated or user.role != 'business':
        return None
    return getattr(user, 'business_profile', None)


class CatalogItemViewSet(viewsets.ModelViewSet):
    serializer_class = CatalogItemSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        queryset = CatalogItem.objects.select_related('business', 'business__owner', 'shared_post').annotate(favorite_total=Count('favorites'))
        business = owned_business(self.request.user)
        mine = str(self.request.query_params.get('mine') or '').lower() in {'1', 'true', 'yes'}
        if mine and business:
            queryset = queryset.filter(business=business)
        elif business and self.action in {'retrieve', 'partial_update', 'update', 'destroy', 'share'}:
            queryset = queryset.filter(
                Q(business=business)
                | Q(is_active=True, business__is_active=True, business__owner__is_approved=True)
            )
        else:
            queryset = queryset.filter(is_active=True, business__is_active=True, business__owner__is_approved=True)
        slug = str(self.request.query_params.get('business') or '').strip()
        if slug:
            queryset = queryset.filter(business__slug=slug)
        query = str(self.request.query_params.get('q') or '').strip()[:100]
        if query:
            queryset = queryset.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(business__name__icontains=query))
        item_type = str(self.request.query_params.get('type') or '').strip()
        if item_type in dict(CatalogItem.TYPE_CHOICES):
            queryset = queryset.filter(item_type=item_type)
        category = str(self.request.query_params.get('category') or '').strip()
        if category in dict(CatalogItem.CATEGORY_CHOICES):
            queryset = queryset.filter(category=category)
        species = str(self.request.query_params.get('species') or '').strip()
        if species:
            queryset = queryset.filter(species__contains=[species])
        for param in ('home_service', 'delivery', 'pickup', 'requires_booking'):
            if str(self.request.query_params.get(param) or '').lower() in {'1', 'true', 'yes'}:
                queryset = queryset.filter(**{param: True})
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        business = owned_business(self.request.user)
        if not business or not business.is_active or not self.request.user.is_approved:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Solo un negocio aprobado puede administrar un catálogo.')
        BusinessAccess.objects.get_or_create(business=business)
        serializer.save(business=business)

    def perform_update(self, serializer):
        if serializer.instance.business.owner_id != self.request.user.id and not is_vetpaw_admin(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Solo podés editar elementos de tu negocio.')
        serializer.save()

    def perform_destroy(self, instance):
        if instance.business.owner_id != self.request.user.id and not is_vetpaw_admin(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Solo podés eliminar elementos de tu negocio.')
        instance.delete()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if not request.user.is_authenticated or request.user.id != instance.business.owner_id:
            CatalogItem.objects.filter(pk=instance.pk).update(views_count=F('views_count') + 1)
            instance.refresh_from_db(fields=['views_count'])
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=['post'])
    def share(self, request, pk=None):
        item = self.get_object()
        if item.business.owner_id != request.user.id:
            return Response({'detail': 'Solo el negocio puede compartir este elemento.'}, status=403)
        price = 'Consultar precio' if item.price_on_request else f'${item.display_price}'
        text = f"🛍️ {item.title}\n{item.description[:500]}\n{price}\nVer en el catálogo de {item.business.name}."
        post = item.shared_post
        if post:
            post.text = text
            post.image = item.image
            post.moderation_status = Post.STATUS_PUBLISHED
            post.save(update_fields=['text', 'image', 'moderation_status', 'updated_at'])
        else:
            post = Post.objects.create(
                created_by=request.user,
                business=item.business,
                post_type=Post.TYPE_BUSINESS,
                text=text,
                image=item.image,
                province=item.business.province,
                locality=item.business.locality,
            )
            item.shared_post = post
            item.save(update_fields=['shared_post', 'updated_at'])
        return Response({'post_id': post.id}, status=201)


class PromotionViewSet(viewsets.ModelViewSet):
    serializer_class = PromotionSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        now = timezone.now()
        queryset = Promotion.objects.select_related('business', 'business__owner', 'catalog_item', 'shared_post')
        business = owned_business(self.request.user)
        mine = str(self.request.query_params.get('mine') or '').lower() in {'1', 'true', 'yes'}
        if mine and business:
            queryset = queryset.filter(business=business)
        elif business and self.action in {'retrieve', 'partial_update', 'update', 'destroy', 'share'}:
            queryset = queryset.filter(
                Q(business=business)
                | Q(is_active=True, starts_at__lte=now, ends_at__gte=now,
                    business__is_active=True, business__owner__is_approved=True)
            )
        else:
            queryset = queryset.filter(
                is_active=True, starts_at__lte=now, ends_at__gte=now,
                business__is_active=True, business__owner__is_approved=True,
            )
        slug = str(self.request.query_params.get('business') or '').strip()
        if slug:
            queryset = queryset.filter(business__slug=slug)
        locality = str(self.request.query_params.get('locality') or '').strip()[:100]
        if locality:
            queryset = queryset.filter(Q(locality__icontains=locality) | Q(business__locality__icontains=locality))
        return queryset.order_by('ends_at', '-created_at')

    def perform_create(self, serializer):
        business = owned_business(self.request.user)
        if not business or not self.request.user.is_approved:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Solo un negocio aprobado puede crear promociones.')
        serializer.save(business=business)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['business'] = owned_business(self.request.user)
        return context

    def perform_update(self, serializer):
        if serializer.instance.business.owner_id != self.request.user.id and not is_vetpaw_admin(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Solo podés editar promociones de tu negocio.')
        serializer.save()

    def perform_destroy(self, instance):
        if instance.business.owner_id != self.request.user.id and not is_vetpaw_admin(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Solo podés eliminar promociones de tu negocio.')
        instance.delete()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if not request.user.is_authenticated or request.user.id != instance.business.owner_id:
            Promotion.objects.filter(pk=instance.pk).update(views_count=F('views_count') + 1)
            instance.refresh_from_db(fields=['views_count'])
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=['post'])
    def share(self, request, pk=None):
        promotion = self.get_object()
        if promotion.business.owner_id != request.user.id:
            return Response({'detail': 'Solo el negocio puede compartir esta promoción.'}, status=403)
        text = f"🎁 {promotion.title}\n{promotion.description[:500]}\nVálida hasta {timezone.localtime(promotion.ends_at).strftime('%d/%m/%Y')}.\nVer promoción de {promotion.business.name}."
        post = promotion.shared_post
        if post:
            post.text = text
            post.image = promotion.image
            post.moderation_status = Post.STATUS_PUBLISHED
            post.save(update_fields=['text', 'image', 'moderation_status', 'updated_at'])
        else:
            post = Post.objects.create(
                created_by=request.user,
                business=promotion.business,
                post_type=Post.TYPE_BUSINESS,
                text=text,
                image=promotion.image,
                province=promotion.business.province,
                locality=promotion.business.locality,
            )
            promotion.shared_post = post
            promotion.save(update_fields=['shared_post', 'updated_at'])
        return Response({'post_id': post.id}, status=201)


class FavoriteViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BusinessFavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return BusinessFavorite.objects.filter(user=self.request.user).select_related(
            'business', 'catalog_item__business', 'promotion__business', 'promotion__catalog_item'
        )

    @action(detail=False, methods=['post'])
    def toggle(self, request):
        target_type = str(request.data.get('target_type') or '')
        target_id = request.data.get('target_id')
        mapping = {
            'business': (BusinessProfile, 'business'),
            'catalog_item': (CatalogItem, 'catalog_item'),
            'promotion': (Promotion, 'promotion'),
        }
        if target_type not in mapping or not target_id:
            return Response({'detail': 'Objetivo inválido.'}, status=400)
        model, field = mapping[target_type]
        try:
            target = model.objects.get(pk=target_id)
        except model.DoesNotExist:
            return Response({'detail': 'No encontramos ese elemento.'}, status=404)
        favorite, created = BusinessFavorite.objects.get_or_create(user=request.user, **{field: target})
        if not created:
            favorite.delete()
        return Response({'favorite': created})


class InquiryViewSet(viewsets.ModelViewSet):
    serializer_class = BusinessInquirySerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'patch']

    def get_queryset(self):
        business = owned_business(self.request.user)
        queryset = BusinessInquiry.objects.select_related('business', 'business__owner', 'user', 'catalog_item', 'promotion', 'message')
        return queryset.filter(business=business) if business else queryset.filter(user=self.request.user)

    @transaction.atomic
    def perform_create(self, serializer):
        inquiry = serializer.save(user=self.request.user)
        subject = inquiry.catalog_item.title if inquiry.catalog_item_id else inquiry.promotion.title if inquiry.promotion_id else inquiry.business.name
        content = f"Hola, me interesa “{subject}”.\n\n{inquiry.content}"
        message = Message.objects.create(sender=self.request.user, recipient=inquiry.business.owner, content=content)
        inquiry.message = message
        inquiry.save(update_fields=['message', 'updated_at'])
        create_business_notification(
            inquiry.business.owner, self.request.user, inquiry.business,
            'business_inquiry', f'Nueva consulta por {subject}',
        )

    def partial_update(self, request, *args, **kwargs):
        inquiry = self.get_object()
        if inquiry.business.owner_id != request.user.id:
            return Response({'detail': 'Solo el negocio puede actualizar la consulta.'}, status=403)
        new_status = request.data.get('status')
        if new_status not in dict(BusinessInquiry.STATUS_CHOICES):
            return Response({'status': 'Estado inválido.'}, status=400)
        inquiry.status = new_status
        inquiry.save(update_fields=['status', 'updated_at'])
        return Response(self.get_serializer(inquiry).data)


class ReservationViewSet(viewsets.ModelViewSet):
    serializer_class = BusinessReservationSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'patch']

    def get_queryset(self):
        business = owned_business(self.request.user)
        queryset = BusinessReservation.objects.select_related('business', 'business__owner', 'user', 'pet', 'catalog_item')
        return queryset.filter(business=business) if business else queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        reservation = serializer.save(user=self.request.user)
        create_business_notification(
            reservation.business.owner, self.request.user, reservation.business,
            'business_reservation', f'Reserva para {reservation.catalog_item.title} el {reservation.date.strftime("%d/%m/%Y")}',
        )

    @action(detail=True, methods=['patch'])
    def status(self, request, pk=None):
        reservation = self.get_object()
        new_status = str(request.data.get('status') or '')
        note = str(request.data.get('business_note') or '')[:500]
        business_owner = reservation.business.owner_id == request.user.id
        customer = reservation.user_id == request.user.id
        if business_owner:
            allowed = {choice[0] for choice in BusinessReservation.STATUS_CHOICES}
        elif customer:
            allowed = {BusinessReservation.STATUS_CANCELLED}
        else:
            allowed = set()
        if new_status not in allowed:
            return Response({'detail': 'No podés aplicar ese cambio.'}, status=403)
        reservation.status = new_status
        if business_owner:
            reservation.business_note = note
        reservation.save(update_fields=['status', 'business_note', 'updated_at'])
        actor = request.user
        recipient = reservation.user if business_owner else reservation.business.owner
        create_business_notification(
            recipient, actor, reservation.business, 'business_reservation_update',
            f'{reservation.get_status_display()}: {reservation.catalog_item.title}',
        )
        return Response(self.get_serializer(reservation).data)


class BusinessDashboardViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        business = owned_business(request.user)
        if not business:
            return Response({'detail': 'Esta sección pertenece a negocios.'}, status=403)
        access, _ = BusinessAccess.objects.get_or_create(business=business)
        now = timezone.now()
        catalog = CatalogItem.objects.filter(business=business)
        promotions = Promotion.objects.filter(business=business)
        reservations = BusinessReservation.objects.filter(business=business)
        inquiries = BusinessInquiry.objects.filter(business=business)
        data = {
            'business': {'id': business.id, 'name': business.name, 'slug': business.slug},
            'access': BusinessAccessSerializer(access).data,
            'stats': {
                'profile_views': BusinessProfileView.objects.filter(business=business).count(),
                'catalog_items': catalog.filter(is_active=True).count(),
                'catalog_views': catalog.aggregate(total=Sum('views_count'))['total'] or 0,
                'promotions_active': promotions.filter(is_active=True, starts_at__lte=now, ends_at__gte=now).count(),
                'favorites': BusinessFavorite.objects.filter(Q(business=business) | Q(catalog_item__business=business) | Q(promotion__business=business)).count(),
                'inquiries_new': inquiries.filter(status=BusinessInquiry.STATUS_NEW).count(),
                'reservations_pending': reservations.filter(status=BusinessReservation.STATUS_PENDING).count(),
                'reservations_total': reservations.count(),
            },
            'recent_inquiries': BusinessInquirySerializer(inquiries[:5], many=True, context={'request': request}).data,
            'upcoming_reservations': BusinessReservationSerializer(
                reservations.filter(date__gte=timezone.localdate()).order_by('date', 'start_time')[:8],
                many=True, context={'request': request},
            ).data,
        }
        return Response(data)
