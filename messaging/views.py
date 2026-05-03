from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import Message
from .serializers import MessageSerializer


class MessageViewSet(viewsets.ModelViewSet):
    serializer_class   = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names  = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        user = self.request.user
        return Message.objects.filter(
            Q(sender=user) | Q(recipient=user)
        ).select_related('sender', 'recipient', 'appointment', 'appointment__pet')

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)

    @action(detail=False, methods=['post'])
    def mark_read(self, request):
        other_id = request.data.get('other_user_id')
        if not other_id:
            return Response({'error': 'other_user_id requerido.'}, status=400)
        Message.objects.filter(
            recipient=request.user,
            sender_id=other_id,
            read=False,
        ).update(read=True)
        return Response({'message': 'Mensajes marcados como leídos.'})

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        count = Message.objects.filter(recipient=request.user, read=False).count()
        return Response({'unread': count})

    @action(detail=False, methods=['get'])
    def conversations(self, request):
        """
        Devuelve la lista de conversaciones del usuario.
        Cada conversación es el último mensaje con cada contacto.
        """
        user = self.request.user
        messages = Message.objects.filter(
            Q(sender=user) | Q(recipient=user)
        ).select_related('sender', 'recipient', 'appointment', 'appointment__pet')

        seen = {}
        for msg in reversed(list(messages)):
            other = msg.recipient if msg.sender == user else msg.sender
            if other.id not in seen:
                seen[other.id] = {
                    'other_user_id':   other.id,
                    'other_username':  other.username,
                    'last_message':    msg.content,
                    'last_date':       msg.created_at,
                    'unread':          Message.objects.filter(
                        sender=other, recipient=user, read=False
                    ).count(),
                    'appointment_id':  msg.appointment_id,
                    'pet_name':        msg.appointment.pet.name if msg.appointment else None,
                }
        return Response(list(seen.values()))