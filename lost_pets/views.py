# lost_pets views - v1
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.utils import timezone
from .models import LostPet
from .serializers import LostPetSerializer


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
        serializer.save()
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