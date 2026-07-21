# lost_pets views - v1
from datetime import timedelta
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.utils import timezone
from .models import LostPet
from .serializers import LostPetSerializer
from users.permissions import is_vetpaw_admin


@api_view(['GET'])
@permission_classes([AllowAny])
def list_lost_pets(request):
    pets = LostPet.objects.filter(expires_at__gt=timezone.now())
    
    province = request.query_params.get('province')
    locality = request.query_params.get('locality')
    
    if province:
        pets = pets.filter(province__icontains=province)
    if locality:
        pets = pets.filter(locality__icontains=locality)
    
    serializer = LostPetSerializer(pets, many=True)
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def create_lost_pet(request):
    serializer = LostPetSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(owner=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def report_lost_pet(request, pk):
    try:
        pet = LostPet.objects.get(pk=pk, expires_at__gt=timezone.now())
    except LostPet.DoesNotExist:
        return Response({'error': 'No encontrado'}, status=status.HTTP_404_NOT_FOUND)
    pet.report_count += 1
    pet.save()
    return Response({'message': 'Reporte enviado', 'report_count': pet.report_count})

def is_lost_pet_admin(user):
    return is_vetpaw_admin(user)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_list_lost_pets(request):
    if not is_lost_pet_admin(request.user):
        return Response({'error': 'Acceso denegado.'}, status=status.HTTP_403_FORBIDDEN)

    pets = LostPet.objects.all()

    status_filter = request.query_params.get('status')
    province = request.query_params.get('province')
    report_type = request.query_params.get('report_type')
    search = request.query_params.get('search')

    if status_filter == 'active':
        pets = pets.filter(expires_at__gt=timezone.now())
    elif status_filter == 'expired':
        pets = pets.filter(expires_at__lte=timezone.now())
    if province:
        pets = pets.filter(province__icontains=province)
    if report_type in ['lost', 'found']:
        pets = pets.filter(report_type=report_type)
    if search:
        pets = pets.filter(
            Q(pet_name__icontains=search) |
            Q(description__icontains=search) |
            Q(locality__icontains=search) |
            Q(province__icontains=search) |
            Q(contact_value__icontains=search) |
            Q(owner__username__icontains=search) |
            Q(owner__email__icontains=search)
        )

    serializer = LostPetSerializer(pets, many=True)
    return Response(serializer.data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def admin_update_lost_pet(request, pk):
    if not is_lost_pet_admin(request.user):
        return Response({'error': 'Acceso denegado.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        pet = LostPet.objects.get(pk=pk)
    except LostPet.DoesNotExist:
        return Response({'error': 'Publicación no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = LostPetSerializer(pet, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_expire_lost_pet(request, pk):
    if not is_lost_pet_admin(request.user):
        return Response({'error': 'Acceso denegado.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        pet = LostPet.objects.get(pk=pk)
    except LostPet.DoesNotExist:
        return Response({'error': 'Publicación no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    pet.expires_at = timezone.now()
    pet.save(update_fields=['expires_at'])
    return Response({'message': 'Publicación ocultada correctamente.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_renew_lost_pet(request, pk):
    if not is_lost_pet_admin(request.user):
        return Response({'error': 'Acceso denegado.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        pet = LostPet.objects.get(pk=pk)
    except LostPet.DoesNotExist:
        return Response({'error': 'Publicación no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    pet.expires_at = timezone.now() + timedelta(days=10)
    pet.save(update_fields=['expires_at'])
    return Response({'message': 'Publicación reactivada por 10 días.'})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def admin_delete_lost_pet(request, pk):
    if not is_lost_pet_admin(request.user):
        return Response({'error': 'Acceso denegado.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        pet = LostPet.objects.get(pk=pk)
    except LostPet.DoesNotExist:
        return Response({'error': 'Publicación no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    pet.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
