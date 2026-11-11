from django.contrib import messages
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.db import transaction
from . import newsletter
from .decorators import setup_required
from .signals import _get_ip
from .forms import RegisterForm, LoginForm, OrganizationSetupForm, StyledPasswordChangeForm, TeamMemberForm
from .models import LoginEvent, User

_MAX_ATTEMPTS = 5
_LOCKOUT_SECONDS = 900  # 15 minut


def _check_rate_limit(request):
    attempts = request.session.get('login_attempts', 0)
    lockout_until = request.session.get('login_lockout_until')
    if lockout_until:
        if timezone.now().timestamp() < lockout_until:
            return False
        request.session.pop('login_lockout_until', None)
        request.session['login_attempts'] = 0
    return True


def register(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            if form.cleaned_data.get('newsletter'):
                # Po zatwierdzeniu zapisu konta; błąd sieci tylko w logu, rejestracja przechodzi.
                transaction.on_commit(lambda ip=_get_ip(request): newsletter.zapisz(user.email, ip))
            login(request, user)
            return redirect('accounts:setup')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    if not _check_rate_limit(request):
        lockout_until = request.session.get('login_lockout_until', 0)
        remaining = int(lockout_until - timezone.now().timestamp())
        messages.error(request, f'Zbyt wiele nieudanych prób. Spróbuj ponownie za {remaining // 60 + 1} min.')
        return render(request, 'accounts/login.html', {'form': LoginForm(), 'locked': True})

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            request.session.pop('login_attempts', None)
            request.session.pop('login_lockout_until', None)
            next_url = request.GET.get('next', '')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect('core:dashboard')
        else:
            attempts = request.session.get('login_attempts', 0) + 1
            request.session['login_attempts'] = attempts
            if attempts >= _MAX_ATTEMPTS:
                request.session['login_lockout_until'] = (
                    timezone.now().timestamp() + _LOCKOUT_SECONDS
                )
                messages.error(request, 'Konto tymczasowo zablokowane po zbyt wielu błędnych próbach (15 min).')
    else:
        form = LoginForm()
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    if request.method == 'POST':
        logout(request)
    return redirect('accounts:login')


@login_required
def setup(request):
    if request.user.organization_id:
        return redirect('core:dashboard')
    if request.method == 'POST':
        form = OrganizationSetupForm(request.POST)
        if form.is_valid():
            form.save(request.user)
            messages.success(request, 'Witaj! Twój lokal jest gotowy. Zacznij od dodania składników.')
            return redirect('core:dashboard')
    else:
        form = OrganizationSetupForm()
    return render(request, 'accounts/setup.html', {'form': form})


@login_required
def password_change(request):
    if request.method == 'POST':
        form = StyledPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # bez tego zmiana hasła wylogowuje od razu
            messages.success(request, 'Hasło zostało zmienione.')
            return redirect('core:dashboard')
    else:
        form = StyledPasswordChangeForm(request.user)
    return render(request, 'accounts/password_change.html', {'form': form})


@login_required
@setup_required
def team_list(request):
    org = request.user.organization
    members = User.objects.filter(organization=org).order_by('date_joined')
    return render(request, 'accounts/team_list.html', {'members': members})


@login_required
@setup_required
def team_add(request):
    org = request.user.organization
    if not request.user.is_org_admin:
        messages.error(request, 'Tylko właściciel lub administrator może dodawać osoby do organizacji.')
        return redirect('accounts:team-list')

    generated_password = None
    new_user = None
    if request.method == 'POST':
        form = TeamMemberForm(request.POST)
        if form.is_valid():
            new_user, generated_password = form.save(org)
    else:
        form = TeamMemberForm()

    return render(request, 'accounts/team_add.html', {
        'form': form, 'new_user': new_user, 'generated_password': generated_password,
    })


@login_required
@setup_required
def team_remove(request, pk):
    org = request.user.organization
    if request.method != 'POST':
        return redirect('accounts:team-list')
    if not request.user.is_org_admin:
        messages.error(request, 'Tylko właściciel lub administrator może usuwać osoby z organizacji.')
        return redirect('accounts:team-list')

    member = get_object_or_404(User, pk=pk, organization=org)

    if member == request.user:
        messages.error(request, 'Nie możesz usunąć samego siebie z zespołu.')
    elif member.is_org_admin and not User.objects.filter(
        organization=org, role__in=[User.ROLE_OWNER, User.ROLE_ADMIN],
    ).exclude(pk=member.pk).exists():
        messages.error(request, 'To ostatnia osoba z uprawnieniami administratora — usuń kogoś innego najpierw albo nadaj tę rolę komuś jeszcze.')
    else:
        member.organization = None
        member.save(update_fields=['organization'])
        messages.success(request, f'{member.email} został/a usunięty/a z organizacji (konto zostaje, tylko traci dostęp).')

    return redirect('accounts:team-list')
