import secrets
import string

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm
from django.utils.text import slugify
from django.utils import timezone
from django.utils.safestring import mark_safe
from .models import User, Organization


from . import newsletter  # noqa: E402


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        label='Adres e-mail',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'twoj@email.pl'}),
    )
    accept_tos = forms.BooleanField(
        label=mark_safe(
            'Akceptuję <a href="/regulamin/" target="_blank">regulamin FoodCost</a> i znam '
            '<a href="https://sudomie.pl/polityka-prywatnosci.html#foodcost" target="_blank">politykę prywatności</a>'
        ),
        error_messages={'required': 'Zaakceptuj regulamin, żeby założyć konto.'},
    )
    newsletter = forms.BooleanField(
        required=False,
        label='Chcę dostawać newsletter sudomie raz w miesiącu: nowości w FoodCost i poradniki. '
              'Potwierdzę zapis linkiem z maila, wypiszę się w każdej chwili.',
    )

    class Meta:
        model = User
        fields = ('email', 'password1', 'password2', 'accept_tos')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs['class'] = 'form-control'
        self.fields['password2'].widget.attrs['class'] = 'form-control'
        self.fields['accept_tos'].widget.attrs['class'] = 'form-check-input'
        if newsletter.wlaczony():
            self.fields['newsletter'].widget.attrs['class'] = 'form-check-input'
        else:
            del self.fields['newsletter']  # flaga: bez klucza pola nie ma

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.username = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Adres e-mail'
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'twoj@email.pl',
            'autofocus': True,
        })
        self.fields['password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': '••••••••',
        })


class StyledPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class TeamMemberForm(forms.Form):
    """Dodanie osoby do tej samej organizacji — bez wysyłki maila (brak
    skonfigurowanego SMTP), więc hasło jest losowane i pokazane RAZ na
    ekranie sukcesu, do przekazania ręcznie."""

    email = forms.EmailField(
        label='Adres e-mail',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'osoba@firma.pl', 'autofocus': True}),
    )
    role = forms.ChoiceField(
        label='Rola',
        choices=User.ROLE_CHOICES,
        initial=User.ROLE_VIEWER,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Konto z tym adresem e-mail już istnieje.')
        return email

    def save(self, organization):
        alphabet = string.ascii_letters + string.digits
        password = ''.join(secrets.choice(alphabet) for _ in range(14))
        email = self.cleaned_data['email']
        user = User.objects.create(
            username=email, email=email, organization=organization, role=self.cleaned_data['role'],
        )
        user.set_password(password)
        user.save()
        return user, password


class OrganizationSetupForm(forms.Form):
    name = forms.CharField(
        label='Nazwa lokalu / restauracji',
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'np. Restauracja Pod Lipą',
            'autofocus': True,
        }),
    )

    def save(self, user):
        name = self.cleaned_data['name']
        slug_base = slugify(name)
        slug = slug_base
        counter = 1
        while Organization.objects.filter(slug=slug).exists():
            slug = f'{slug_base}-{counter}'
            counter += 1

        org = Organization.objects.create(
            name=name,
            slug=slug,
            accepted_tos_at=timezone.now(),
        )
        user.organization = org
        user.role = User.ROLE_OWNER
        user.save(update_fields=['organization', 'role'])
        return org
