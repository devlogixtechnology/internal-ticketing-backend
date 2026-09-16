import json
import time
import psutil
from datetime import timedelta

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.admin.views.decorators import staff_member_required

from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, generics, viewsets
from rest_framework.parsers import MultiPartParser, FormParser
from apps.clients.models import WhitelistedEmergencyEmail, Client
from apps.notifications.models import Notification
from apps.accounts.models import CustomUser
from .models import Ticket, TicketHistory, Category, TicketAttachment, ServerHealthLog
from .tasks import send_ticket_assigned_email, send_status_update_email  # Celery Tasks

User = get_user_model()
from .serializers import (
    TicketSerializer, AssignTicketSerializer, ChangeStatusSerializer, 
    CategorySerializer, TicketAttachmentSerializer
)
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Ticket
from .serializers import TicketSerializer

User = get_user_model()


# ---------------------------------------------------------
# HELPER: DRF & Template Level Queryset Scoping
# ---------------------------------------------------------
def _visible_tickets_for_user(user):
    """
    Client-scoped Querysets:
    - ADMIN/Superuser: All Tickets
    - SUPPORT: Only assigned tickets
    - CLIENT/EMPLOYEE: Only their own tickets
    """
    role = getattr(user, 'role', 'EMPLOYEE')
    queryset = Ticket.objects.select_related('created_by', 'assigned_to', 'category').prefetch_related('attachments')
    
    if role == 'ADMIN' or user.is_superuser:
        return queryset
    if role == 'SUPPORT':
        return queryset.filter(assigned_to=user)
    
    # Client scoping (User sees only their own tickets)
    return queryset.filter(created_by=user)


# ---------------------------------------------------------
# DRF VIEWSET (NEW: Client Scoped API)
# ---------------------------------------------------------
class TicketViewSet(viewsets.ModelViewSet):
    """
    DRF ViewSet for Ticket Management with scoping & zero data leak.
    """
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _visible_tickets_for_user(self.request.user)

    def perform_create(self, serializer):
        # Assign creator automatically
        serializer.save(created_by=self.request.user)


# ---------------------------------------------------------
# DRF API VIEWS
# ---------------------------------------------------------
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def ticket_list_create_api(request):
    """
    DRF API endpoint to list client-scoped tickets or create a new ticket.
    """
    if request.method == 'GET':
        tickets = _visible_tickets_for_user(request.user)
        serializer = TicketSerializer(tickets, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == 'POST':
        serializer = TicketSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            ticket = serializer.save(created_by=request.user)
            return Response({
                "message": "Ticket created successfully",
                "ticket_id": ticket.id,
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_ticket_api(request):
    serializer = TicketSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        ticket = serializer.save(created_by=request.user)
        return Response({
            "message": "Ticket created successfully",
            "ticket_id": ticket.id,
            "data": serializer.data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_ticket_api(request, ticket_id):
    if not (request.user.role == 'ADMIN' or request.user.is_superuser):
        return Response({"error": "Only Admins can assign tickets"}, status=status.HTTP_403_FORBIDDEN)

    ticket = get_object_or_404(Ticket, id=ticket_id)
    serializer = AssignTicketSerializer(data=request.data)
    
    if serializer.is_valid():
        user_id = serializer.validated_data['user_id']
        assigned_user = CustomUser.objects.filter(id=user_id).first()
        
        if not assigned_user:
            return Response({"error": "Selected user does not exist."}, status=status.HTTP_400_BAD_REQUEST)

        old_status = ticket.status
        ticket.assigned_to = assigned_user
        ticket.status = getattr(Ticket.Status, 'OPEN', 'OPEN') if hasattr(Ticket, 'Status') else 'OPEN'
        ticket.save()

        TicketHistory.objects.create(
            ticket=ticket,
            changed_by=request.user,
            old_status=old_status,
            new_status=ticket.status,
            remarks=f"Assigned to {assigned_user.username}"
        )

        return Response({
            "message": f"Ticket #{ticket.id} assigned to {assigned_user.username}"
        }, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

def assign_ticket_view(request):
    if request.method == 'POST':
        ticket_id = request.POST.get('ticket_id')
        assigned_to_id = request.POST.get('assigned_to')
        
        ticket = get_object_or_404(Ticket, id=ticket_id)
        # Update logic ...
        ticket.assigned_to_id = assigned_to_id
        ticket.save()

        # Background Celery task call karna (.delay method se)
        if ticket.assigned_to and ticket.assigned_to.email:
            send_ticket_assigned_email.delay(ticket.id, ticket.assigned_to.email)

        return redirect('ticket_list')

def update_status_view(request):
    if request.method == 'POST':
        ticket_id = request.POST.get('ticket_id')
        new_status = request.POST.get('status')

        ticket = get_object_or_404(Ticket, id=ticket_id)
        ticket.status = new_status
        ticket.save()

        # Call Celery task in background
        send_status_update_email.delay(ticket.id, new_status)

        return redirect('ticket_list')
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_status_api(request, ticket_id):
    # Only access tickets allowed to this user
    ticket = get_object_or_404(_visible_tickets_for_user(request.user), id=ticket_id)
    serializer = ChangeStatusSerializer(data=request.data)

    if serializer.is_valid():
        new_status = serializer.validated_data['status']
        remarks = serializer.validated_data.get('remarks', '')

        if hasattr(ticket, 'can_transition_to') and not ticket.can_transition_to(request.user, new_status):
            return Response({
                "error": f"Role '{request.user.get_role_display()}' is not allowed to transition ticket from {ticket.status} to {new_status}"
            }, status=status.HTTP_400_BAD_REQUEST)

        old_status = ticket.status
        ticket.status = new_status
        ticket.save()
        
        TicketHistory.objects.create(
            ticket=ticket,
            changed_by=request.user,
            old_status=old_status,
            new_status=new_status,
            remarks=remarks
        )

        return Response({
            "message": f"Ticket #{ticket.id} status updated to {new_status}"
        }, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_category_api(request):
    if not (request.user.role == 'ADMIN' or request.user.is_superuser):
        return Response({"error": "Only Admins can add new categories."}, status=status.HTTP_403_FORBIDDEN)

    serializer = CategorySerializer(data=request.data)
    if serializer.is_valid():
        category = serializer.save()
        return Response({
            "message": f"Category '{category.name}' created successfully!",
            "category": serializer.data
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
@permission_classes([IsAuthenticated])
def upload_attachment_api(request, ticket_id):
    ticket = get_object_or_404(_visible_tickets_for_user(request.user), id=ticket_id)
    file_obj = request.FILES.get('file')

    if not file_obj:
        return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

    serializer = TicketAttachmentSerializer(
        data={'file': file_obj, 'ticket': ticket.id},
        context={'request': request},
    )
    if serializer.is_valid():
        serializer.save(ticket=ticket, uploaded_by=request.user)
        return Response({
            "message": "Attachment uploaded successfully!",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------
# TEMPLATE VIEWS
# ---------------------------------------------------------
@staff_member_required
def server_health_dashboard(request):
    cpu = psutil.cpu_percent(interval=0.3)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    
    boot_time = psutil.boot_time()
    uptime_seconds = int(time.time() - boot_time)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}h {minutes}m {seconds}s"
    
    ServerHealthLog.objects.create(
        cpu_usage=cpu,
        memory_usage=memory,
        disk_usage=disk,
        system_uptime=uptime_str
    )
    latest_health = ServerHealthLog.objects.first()
    recent_logs = ServerHealthLog.objects.all()[:100]
    chart_logs = list(reversed(recent_logs[:30]))
    
    timestamps = [log.timestamp.strftime("%H:%M:%S") for log in chart_logs]
    cpu_data = [round(log.cpu_usage, 1) for log in chart_logs]
    ram_data = [round(log.memory_usage, 1) for log in chart_logs]
    disk_data = [round(log.disk_usage, 1) for log in chart_logs]
    avg_cpu = round(sum(cpu_data) / len(cpu_data), 1) if cpu_data else 0
    max_cpu = max(cpu_data) if cpu_data else 0

    context = {
        'latest_health': latest_health,
        'recent_logs': recent_logs,
        'timestamps': json.dumps(timestamps),
        'cpu_data': json.dumps(cpu_data),
        'ram_data': json.dumps(ram_data),
        'disk_data': json.dumps(disk_data),
        'avg_cpu': avg_cpu,
        'max_cpu': max_cpu,
        'total_logs_count': ServerHealthLog.objects.count(),
    }
    return render(request, 'tickets/server_health.html', context)




@login_required
def dashboard(request):
    user = request.user
    role = getattr(user, 'role', 'EMPLOYEE')

    # -------------------------------------------------------------
    # 1. POST ACTIONS (Approval, Rejection, Assignment, Status Update, Email Whitelist)
    # -------------------------------------------------------------
    if request.method == 'POST':
        ticket_id = request.POST.get('ticket_id')

        # --- Emergency Email Whitelist Actions (Admin Only) ---
        if 'add_emergency_email' in request.POST and (role == 'ADMIN' or user.is_superuser):
            client_id = request.POST.get('client_id')
            email = request.POST.get('email')
            purpose = request.POST.get('purpose')

            client_obj = get_object_or_404(Client, id=client_id)
            WhitelistedEmergencyEmail.objects.create(
                client=client_obj,
                email=email,
                purpose=purpose,
                verified=True,
                added_by=user
            )
            messages.success(request, f"Emergency email '{email}' whitelisted successfully!")
            return redirect('tickets:dashboard')

        elif 'delete_emergency_email' in request.POST and (role == 'ADMIN' or user.is_superuser):
            email_id = request.POST.get('email_id')
            WhitelistedEmergencyEmail.objects.filter(id=email_id).delete()
            messages.success(request, "Whitelisted emergency email deleted successfully!")
            return redirect('tickets:dashboard')

        # --- Existing User Role Update ---
        elif 'update_user_role' in request.POST and (role == 'ADMIN' or user.is_superuser):
            target_user_id = request.POST.get('target_user_id')
            new_role = request.POST.get('new_role')
            target_user = get_object_or_404(User, id=target_user_id)
            target_user.role = new_role
            target_user.save()
            messages.success(request, f"User {target_user.username}'s role updated to {new_role}!")
            return redirect('tickets:dashboard')

        # --- Existing Ticket Actions ---
        if ticket_id:
            ticket = get_object_or_404(Ticket, id=ticket_id)

            # Approve Ticket (Admin only)
            if 'approve_ticket' in request.POST and (role == 'ADMIN' or user.is_superuser):
                ticket.approval_status = Ticket.ApprovalStatus.APPROVED
                ticket.save()
                Notification.objects.create(
                    recipient=ticket.created_by,
                    title=f"Ticket #{ticket.id} Approved",
                    message=f"Your ticket '{ticket.title}' has been approved and is now active."
                )
                messages.success(request, f"Ticket #{ticket.id} approved!")

            # Reject Ticket (Admin only)
            elif 'reject_ticket' in request.POST and (role == 'ADMIN' or user.is_superuser):
                ticket.approval_status = Ticket.ApprovalStatus.REJECTED
                ticket.save()
                Notification.objects.create(
                    recipient=ticket.created_by,
                    title=f"Ticket #{ticket.id} Rejected",
                    message=f"Your ticket '{ticket.title}' has been rejected by Admin."
                )
                messages.warning(request, f"Ticket #{ticket.id} rejected!")

            # Assign Agent
            elif 'assign_agent' in request.POST and (role == 'ADMIN' or user.is_superuser):
                agent_id = request.POST.get('agent_id')
                assigned_agent = User.objects.filter(id=agent_id).first() if agent_id else None
                ticket.assigned_to = assigned_agent
                ticket.save()

                if assigned_agent and assigned_agent.email:
                    send_ticket_assigned_email.delay(ticket.id, assigned_agent.email)

                messages.success(request, f"Ticket #{ticket.id} assigned successfully!")

            # Update Status
            elif 'update_status' in request.POST and (role in ['SUPPORT', 'ADMIN'] or user.is_superuser):
                new_status = request.POST.get('status')
                ticket.status = new_status
                ticket.save()

                send_status_update_email.delay(ticket.id, new_status)

                messages.success(request, f"Ticket #{ticket.id} status updated to {new_status}!")

        return redirect('tickets:dashboard')

    # -------------------------------------------------------------
    # 2. GET QUERYSETS (Role & Client Scoping)
    # -------------------------------------------------------------
    base_queryset = Ticket.objects.select_related('created_by', 'assigned_to', 'category', 'client')

    if role == 'ADMIN' or user.is_superuser:
        pending_tickets = base_queryset.filter(approval_status='PENDING')
        tickets = base_queryset.filter(approval_status='APPROVED')
        rejected_tickets = base_queryset.filter(approval_status='REJECTED')

    elif role == 'SUPPORT':
        pending_tickets = Ticket.objects.none()
        tickets = base_queryset.filter(assigned_to=user, approval_status='APPROVED')
        rejected_tickets = Ticket.objects.none()

    else:
        if hasattr(user, 'client') and user.client:
            client_tickets = base_queryset.filter(client=user.client)
            pending_tickets = client_tickets.filter(approval_status='PENDING')
            tickets = client_tickets.filter(approval_status='APPROVED')
            rejected_tickets = client_tickets.filter(approval_status='REJECTED')
        else:
            user_tickets = base_queryset.filter(created_by=user)
            pending_tickets = user_tickets.filter(approval_status='PENDING')
            tickets = user_tickets.filter(approval_status='APPROVED')
            rejected_tickets = user_tickets.filter(approval_status='REJECTED')

    # Context Data Rendering
    context = {
        'tickets': tickets,
        'pending_tickets': pending_tickets,           
        'rejected_tickets': rejected_tickets,          
        'user_role': role,
        'categories': Category.objects.all(),
        'total_count': tickets.count(),
        'open_count': tickets.filter(status='OPEN').count(),
        'in_progress_count': tickets.filter(status='IN_PROGRESS').count(),
        'resolved_count': tickets.filter(status='RESOLVED').count(),
        'support_agents': User.objects.filter(role='SUPPORT'),
        'all_employees': User.objects.all().exclude(is_superuser=True),
        'status_choices': Ticket.Status.choices if hasattr(Ticket, 'Status') else [
            ('OPEN', 'Open'), 
            ('IN_PROGRESS', 'In Progress'), 
            ('RESOLVED', 'Resolved'), 
            ('CLOSED', 'Closed')
        ],
        # --- Task 1 Context Integration ---
        'whitelisted_emails': WhitelistedEmergencyEmail.objects.select_related('client', 'added_by').all(),
        'all_clients': Client.objects.filter(is_active=True),
    }
    return render(request, 'tickets/dashboard.html', context)

@login_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(_visible_tickets_for_user(request.user), id=ticket_id)
    return render(request, 'tickets/detail.html', {'ticket': ticket})


@login_required
def assign_support(request, ticket_id):
    if request.method == 'POST':
        agent_id = request.POST.get('support_agent_id') or request.POST.get('agent_id')
        ticket = get_object_or_404(Ticket, id=ticket_id)
        
        if agent_id:
            assigned_user = User.objects.filter(id=agent_id).first()
            if assigned_user:
                old_status = ticket.status
                ticket.assigned_to = assigned_user
                ticket.status = getattr(Ticket.Status, 'OPEN', 'OPEN') if hasattr(Ticket, 'Status') else 'OPEN'
                ticket.save()
                
                TicketHistory.objects.create(
                    ticket=ticket,
                    changed_by=request.user,
                    old_status=old_status,
                    new_status=ticket.status,
                    remarks=f"Assigned to {assigned_user.username}"
                )
                messages.success(request, f"Ticket #{ticket.id} successfully assigned to {assigned_user.username}!")
            else:
                messages.error(request, "Selected support agent not found.")
        else:
            messages.error(request, "Please select a support agent.")
            
    return redirect('tickets:dashboard')





class TicketViewSet(viewsets.ModelViewSet):
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Ticket.objects.select_related('client', 'assigned_to', 'created_by').all()

        # Admin / Superuser tamaam clients ke tickets dekh sakta hai
        if user.is_staff or user.is_superuser or getattr(user, 'role', '') == 'ADMIN':
            return queryset

        # Support agent ko assigned tickets nazar aayenge
        if getattr(user, 'role', '') == 'SUPPORT':
            return queryset.filter(assigned_to=user)

        # Client / Regular User Scoping: Sirf apni company/client ke tickets dekh sakein
        if hasattr(user, 'client') and user.client:
            return queryset.filter(client=user.client)

        return queryset.filter(created_by=user)