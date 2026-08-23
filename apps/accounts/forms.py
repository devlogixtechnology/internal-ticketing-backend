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

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'email', 'department')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.department = self.cleaned_data.get('department')
        if hasattr(CustomUser, 'Role'):
            user.role = CustomUser.Role.EMPLOYEE
        else:
            user.role = 'EMPLOYEE'

        if commit:
            user.save()
        return user