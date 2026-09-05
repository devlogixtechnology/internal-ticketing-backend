from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.views import LoginView
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth import logout

from .forms import SignupForm

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .models import APIKey, MagicLinkToken  
from apps.accounts.models import APIKey

import hashlib
import secrets
from datetime import timedelta
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views import View
from django.utils import timezone
from django.contrib.auth import login
from django.contrib.auth import get_user_model
from apps.accounts.models import MagicLinkToken
get_user_model()



class SignupView(CreateView):
    form_class = SignupForm
    template_name = 'accounts/signup.html'
    success_url = reverse_lazy('accounts:login')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Account created successfully! Please log in.")
        return response


class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

def custom_logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('accounts:login')




class MagicLinkRequestView(View):
    template_name = "accounts/magic_link_request.html"

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        email = request.POST.get("email")
        user = User.objects.filter(email=email).first()

        if user:
            raw_token = secrets.token_urlsafe(32)
            hashed_token = hashlib.sha256(raw_token.encode()).hexdigest()

            # Fix: expires_at remove kar diya gaya hai
            MagicLinkToken.objects.create(
                user=user,
                token=hashed_token,
                is_used=False
            )

            # Verification URL generate karein
            magic_url = request.build_absolute_uri(
                f"/accounts/auth/magic-link/verify/{raw_token}/"
            )

            messages.success(
                request, 
                f"Magic link generated successfully! Link (Valid for 15 mins): {magic_url}"
            )
            return redirect("accounts:login")

        messages.error(request, "No account found with this email address.")
        return redirect("accounts:magic_link_request")


class MagicLinkVerifyView(View):
    def get(self, request, token, *args, **kwargs):
        hashed_token = hashlib.sha256(token.encode()).hexdigest()
        
        token_obj = MagicLinkToken.objects.filter(
            token=hashed_token, 
            is_used=False
        ).first()

        if not token_obj:
            messages.error(request, "Invalid or already used Magic Link.")
            return redirect("accounts:login")

        # 15 Minutes Expiry Check (created_at field se check hoga)
        if timezone.now() - token_obj.created_at > timedelta(minutes=15):
            messages.error(request, "This Magic Link has expired (15 minutes limit exceeded).")
            return redirect("accounts:login")

        # Link ko mark as used karein aur user ko login karwein
        token_obj.is_used = True
        token_obj.save()

        login(request, token_obj.user)
        messages.success(request, "Successfully logged in via Magic Link!")
        return redirect("tickets:dashboard")
class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and (self.request.user.is_staff or getattr(self.request.user, 'role', '') == 'STAFF')



class APIKeyManagementView(View):
    template_name = "accounts/api_keys.html"

    def get(self, request, *args, **kwargs):
        # User login check
        if not request.user.is_authenticated:
            return redirect("accounts:login")

        # Role access check (Only Support / Admin allowed)
        if request.user.role not in ["SUPPORT", "ADMIN"] and not request.user.is_superuser:
            messages.error(request, "Permission denied. Only Support and Admin can manage API Keys.")
            return redirect("tickets:dashboard")

        # API keys list retrieval
        keys = APIKey.objects.filter(user=request.user).order_by("-created_at")
        return render(request, self.template_name, {"api_keys": keys})

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")

        if request.user.role not in ["SUPPORT", "ADMIN"] and not request.user.is_superuser:
            messages.error(request, "Permission denied.")
            return redirect("tickets:dashboard")

        # Key generation with updated model field names
        raw_key = f"dtk_{secrets.token_hex(20)}"
        prefix = raw_key[:8]
        hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()

        APIKey.objects.create(
            user=request.user,
            prefix=prefix,
            hashed_key=hashed_key,
            is_active=True,
        )

        messages.success(
            request,
            f"API Key successfully generated! Copy your raw key now: {raw_key}"
        )
        return redirect("accounts:api_keys")