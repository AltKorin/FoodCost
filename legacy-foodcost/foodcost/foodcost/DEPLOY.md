# Deployment: foodcost.sudomie.pl na GoDaddy cPanel
# Identyczna procedura jak IB apps — znasz ten flow

## 1. cPanel — przygotowanie

### Subdomena
cPanel → Domeny → Subdomeny
- Subdomena: foodcost
- Domena: sudomie.pl
- Document Root: foodcost.sudomie.pl  ← cPanel wypełni automatycznie

### Baza danych MySQL
cPanel → Bazy danych MySQL
1. Utwórz bazę: np. `sudomie_foodcost`
2. Utwórz użytkownika: np. `sudomie_fc_user` + silne hasło
3. Dodaj użytkownika do bazy → Wszystkie uprawnienia

### Python / Virtualenv
cPanel → Setup Python App
- Python version: 3.11
- Application root: foodcost.sudomie.pl
- Application URL: foodcost.sudomie.pl
- Application startup file: passenger_wsgi.py
- Application Entry point: application
→ Utwórz

## 2. Upload plików

```bash
# Lokalnie — spakuj projekt
zip -r foodcost.zip foodcost/ --exclude "*.pyc" --exclude "__pycache__/*"
```

Przez cPanel File Manager lub SCP:
- Wgraj do katalogu głównego konta (nie do public_html)
- Rozpakuj: `unzip foodcost.zip`
- Skopiuj zawartość do `~/foodcost.sudomie.pl/`

Struktura docelowa:
```
~/foodcost.sudomie.pl/
├── passenger_wsgi.py
├── manage.py
├── requirements.txt
├── .env
├── foodcost_project/
├── ingredients/
├── recipes/
├── templates/
├── static/
└── fixtures/
```

## 3. Instalacja zależności

W cPanel → Python App → otwórz terminal (lub SSH):

```bash
cd ~/foodcost.sudomie.pl
source ~/virtualenv/foodcost.sudomie.pl/3.11/bin/activate
pip install -r requirements.txt
```

Uwaga: jeśli mysqlclient nie chce się zbudować:
```bash
pip install mysqlclient --no-cache-dir
```

## 4. Plik .env

```bash
cp .env.example .env
nano .env  # wypełnij danymi z cPanel
```

Wygeneruj SECRET_KEY:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## 5. Migracje i dane startowe

```bash
python manage.py migrate
python manage.py loaddata fixtures/initial_data.json
python manage.py collectstatic --noinput
python manage.py createsuperuser
# Login: konrad (lub admin)
# Hasło: silne
```

Utwórz konto dla Michała:
```bash
python manage.py shell -c "
from django.contrib.auth.models import User
u = User.objects.create_user('michal', '', 'haslo_michala')
u.first_name = 'Michał'
u.is_staff = False
u.save()
print('OK')
"
```

## 6. Wczytaj settings z .env

Dodaj na górę settings.py (jeśli jeszcze nie ma):
```python
from pathlib import Path
import os

# Wczytaj .env ręcznie (bez python-dotenv dla prostoty)
env_file = Path(__file__).resolve().parent.parent / '.env'
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, val = line.split('=', 1)
            os.environ.setdefault(key.strip(), val.strip())
```

## 7. Restart aplikacji

cPanel → Python App → Restart

Lub przez SSH:
```bash
touch ~/foodcost.sudomie.pl/tmp/restart.txt
```

## 8. Media (zdjęcia — na przyszłość)

```bash
mkdir -p ~/foodcost.sudomie.pl/media
# Symlink do public_html jak w IB:
ln -s ~/foodcost.sudomie.pl/media ~/foodcost.sudomie.pl/public_html/media
```

## Typowe problemy (z IB — te same pułapki)

| Problem | Rozwiązanie |
|---|---|
| 500 error po deploy | Sprawdź passenger_wsgi.py — ścieżki |
| Static files 404 | `collectstatic` + sprawdź STATIC_ROOT |
| mysqlclient build error | `pip install mysqlclient --no-cache-dir` |
| `request.build_absolute_uri` zwraca http:// | Nie dotyczy tej apki — brak emaili |
| Zmiany w kodzie nie działają | `touch tmp/restart.txt` |

## Pierwsze kroki po deploy

1. Zaloguj się jako admin: foodcost.sudomie.pl/admin
2. Dodaj dostawców (Makro, Metro, lokalna hurtownia ryb, etc.)
3. Dodaj pierwsze składniki z kategoriami
4. Wejdź na /ceny/<id>/ i wpisz pierwsze ceny z cennika
5. Utwórz pierwszy przepis → sprawdź FC
6. Daj Michałowi login i hasło
