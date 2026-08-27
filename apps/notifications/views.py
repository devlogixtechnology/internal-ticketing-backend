from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import Notification
from .serializers import NotificationSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_notifications_api(request):
    notifications = Notification.objects.filter(recipient=request.user, is_read=False)
    serializer = NotificationSerializer(notifications, many=True)
    return Response({
        "unread_count": notifications.count(),
        "notifications": serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read_api(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.is_read = True
    notification.save()
    return Response({"message": "Notification marked as read."}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_read_api(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return Response({"message": "All notifications marked as read."}, status=status.HTTP_200_OK)