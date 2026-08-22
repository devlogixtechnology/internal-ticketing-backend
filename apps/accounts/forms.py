from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Department


class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True)
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        empty_label="Select Department"
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'department', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.department = self.cleaned_data.get('department')
        user.role = CustomUser.Role.EMPLOYEE  # strictly enforced
        if commit:
            user.save()
        return user