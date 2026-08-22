from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Ticket


@login_required
def dashboard(request):
    user = request.user

    if user.role == 'ADMIN':
        tickets = Ticket.objects.all()
    elif user.role == 'SUPPORT':
        tickets = Ticket.objects.filter(assigned_to=user)
    else:  # EMPLOYEE
        tickets = Ticket.objects.filter(created_by=user)

    context = {
        'tickets': tickets,
        'total_count': tickets.count(),
    }
    return render(request, 'tickets/dashboard.html', context)