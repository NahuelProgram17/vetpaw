from django.db import transaction
from django.db.models import Q
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from partners.models import ShelterProfile
from community.models import BlockedUser, Post
from .models import AdoptionAnimal, AdoptionPhoto, AdoptionApplication, HelpOffer, AdoptionStatusHistory
from .serializers import AdoptionAnimalSerializer, AdoptionApplicationSerializer, HelpOfferSerializer, AdoptionStatusHistorySerializer

def shelter_for(user):
    return ShelterProfile.objects.filter(owner=user,is_active=True).first()

def visible_qs(user=None):
    qs=AdoptionAnimal.objects.filter(is_published=True,shelter__is_active=True).select_related('shelter','shelter__owner').prefetch_related('photos')
    if user and user.is_authenticated:
        blocked=BlockedUser.objects.filter(Q(blocker=user)|Q(blocked=user)); ids=set()
        for row in blocked: ids.add(row.blocked_id if row.blocker_id==user.id else row.blocker_id)
        qs=qs.exclude(shelter__owner_id__in=ids)
    return qs

class AdoptionListCreateView(generics.ListCreateAPIView):
    serializer_class=AdoptionAnimalSerializer; permission_classes=[permissions.AllowAny]
    def get_queryset(self):
        qs=visible_qs(self.request.user); p=self.request.query_params
        for field in ('species','status','province','locality','size','sex','age_group'):
            if p.get(field): qs=qs.filter(**{field:p[field]})
        if p.get('q'):
            q=p['q'][:100]; qs=qs.filter(Q(name__icontains=q)|Q(breed__icontains=q)|Q(story__icontains=q)|Q(locality__icontains=q)|Q(shelter__name__icontains=q))
        if p.get('shelter'):
            qs=qs.filter(shelter__slug=p['shelter'])
        return qs
    def get_permissions(self): return [permissions.IsAuthenticated()] if self.request.method=='POST' else [permissions.AllowAny()]
    def perform_create(self,serializer):
        shelter=shelter_for(self.request.user)
        if not shelter: raise PermissionDenied('Solo un refugio aprobado puede publicar animales.')
        animal=serializer.save(shelter=shelter)
        AdoptionStatusHistory.objects.create(animal=animal,new_status=animal.status,changed_by=self.request.user)

class AdoptionDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class=AdoptionAnimalSerializer; lookup_field='pk'; permission_classes=[permissions.AllowAny]
    def get_queryset(self):
        if self.request.method in permissions.SAFE_METHODS:
            if self.request.user.is_authenticated:
                return AdoptionAnimal.objects.filter(
                    Q(is_published=True, shelter__is_active=True) | Q(shelter__owner=self.request.user)
                ).select_related('shelter', 'shelter__owner').prefetch_related('photos').distinct()
            return visible_qs(None)
        return AdoptionAnimal.objects.all().select_related('shelter')
    def get_object(self):
        obj=super().get_object()
        if self.request.method not in permissions.SAFE_METHODS and not (self.request.user.is_authenticated and (obj.shelter.owner_id==self.request.user.id or self.request.user.is_staff)): raise PermissionDenied('No podés modificar esta ficha.')
        return obj
    def perform_update(self,serializer):
        old=self.get_object().status; animal=serializer.save()
        if old!=animal.status:
            AdoptionStatusHistory.objects.create(animal=animal,old_status=old,new_status=animal.status,changed_by=self.request.user)
            if animal.status==AdoptionAnimal.STATUS_ADOPTED: self._share(animal,adopted=True)
    def _share(self,animal,adopted=False):
        text=(f'🎉 {animal.name} encontró una familia. Gracias a toda la comunidad VetPaw.' if adopted else f'🏠 {animal.name} busca una familia. {animal.get_status_display()} en {animal.locality}.')
        if animal.community_post_id:
            post=animal.community_post; post.text=text; post.save(update_fields=['text','updated_at']); return post
        post=Post.objects.create(created_by=animal.shelter.owner,shelter=animal.shelter,post_type=Post.TYPE_ADOPTION,text=text,image=animal.cover,province=animal.province,locality=animal.locality)
        animal.community_post=post; animal.save(update_fields=['community_post']); return post

class ShareAdoptionView(APIView):
    permission_classes=[permissions.IsAuthenticated]
    def post(self,request,pk):
        animal=AdoptionAnimal.objects.select_related('shelter').get(pk=pk)
        if animal.shelter.owner_id!=request.user.id: raise PermissionDenied()
        view=AdoptionDetailView(); post=view._share(animal,adopted=animal.status==AdoptionAnimal.STATUS_ADOPTED)
        return Response({'post_id':post.id},status=status.HTTP_201_CREATED)

class AdoptionPhotoView(APIView):
    permission_classes=[permissions.IsAuthenticated]
    def post(self,request,pk):
        animal=AdoptionAnimal.objects.select_related('shelter').get(pk=pk)
        if animal.shelter.owner_id!=request.user.id: raise PermissionDenied()
        image=request.FILES.get('image')
        if not image: return Response({'image':['Seleccioná una imagen.']},status=400)
        photo=AdoptionPhoto.objects.create(animal=animal,image=image,caption=request.data.get('caption','')[:180])
        return Response({'id':photo.id},status=201)

class ApplicationCreateView(generics.CreateAPIView):
    serializer_class=AdoptionApplicationSerializer; permission_classes=[permissions.IsAuthenticated]
    def perform_create(self,serializer):
        animal=visible_qs(self.request.user).get(pk=self.kwargs['pk'])
        if animal.shelter.owner_id==self.request.user.id: raise PermissionDenied('No podés solicitar tu propio animal.')
        serializer.save(animal=animal,applicant=self.request.user)

class MyApplicationsView(generics.ListAPIView):
    serializer_class=AdoptionApplicationSerializer; permission_classes=[permissions.IsAuthenticated]
    def get_queryset(self): return AdoptionApplication.objects.filter(applicant=self.request.user).select_related('animal')

class ShelterApplicationsView(generics.ListAPIView):
    serializer_class=AdoptionApplicationSerializer; permission_classes=[permissions.IsAuthenticated]
    def get_queryset(self):
        shelter=shelter_for(self.request.user)
        if not shelter: return AdoptionApplication.objects.none()
        return AdoptionApplication.objects.filter(animal__shelter=shelter).select_related('animal','applicant')

class ApplicationStatusView(APIView):
    permission_classes=[permissions.IsAuthenticated]
    def patch(self,request,pk):
        app=AdoptionApplication.objects.select_related('animal__shelter').get(pk=pk)
        if app.animal.shelter.owner_id!=request.user.id: raise PermissionDenied()
        allowed=dict(AdoptionApplication.STATUS_CHOICES)
        new=request.data.get('status')
        if new not in allowed: return Response({'status':['Estado inválido.']},status=400)
        app.status=new; app.shelter_notes=request.data.get('shelter_notes',app.shelter_notes)[:1500]; app.save(update_fields=['status','shelter_notes','updated_at'])
        if new==AdoptionApplication.STATUS_COMPLETED:
            old=app.animal.status; app.animal.status=AdoptionAnimal.STATUS_ADOPTED; app.animal.save(update_fields=['status','updated_at']); AdoptionStatusHistory.objects.create(animal=app.animal,old_status=old,new_status=app.animal.status,changed_by=request.user)
        return Response(AdoptionApplicationSerializer(app,context={'request':request}).data)

class HelpOfferCreateView(generics.CreateAPIView):
    serializer_class=HelpOfferSerializer; permission_classes=[permissions.IsAuthenticated]
    def perform_create(self,serializer): serializer.save(animal=visible_qs(self.request.user).get(pk=self.kwargs['pk']),user=self.request.user)

class ShelterHelpOffersView(generics.ListAPIView):
    serializer_class=HelpOfferSerializer; permission_classes=[permissions.IsAuthenticated]
    def get_queryset(self):
        shelter=shelter_for(self.request.user); return HelpOffer.objects.filter(animal__shelter=shelter).select_related('animal','user') if shelter else HelpOffer.objects.none()

class StatusHistoryView(generics.ListAPIView):
    serializer_class=AdoptionStatusHistorySerializer; permission_classes=[permissions.AllowAny]
    def get_queryset(self): return AdoptionStatusHistory.objects.filter(animal_id=self.kwargs['pk'])
