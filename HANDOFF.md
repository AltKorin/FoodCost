# HANDOFF — FoodCost SaaS
## fc.sudomie.pl

---

## Workflow sesji — OBOWIĄZKOWE

### Na początku każdej sesji
1. Przeczytaj HANDOFF.md — bieżący stan projektu
2. Przeczytaj SUMMARY.md — historia co działało, a co nie

### Na końcu każdej sesji
1. **Zaktualizuj HANDOFF.md** — bieżący stan, nowe gotcha
2. **Dopisz sekcję do SUMMARY.md**:
```
## Sesja RRRR-MM-DD
### Zrobiono
### Zadziałało
### Nie zadziałało
### Następne kroki
```

---

## 🟢 Stan na 2026-09-07 (4): dodano trzeci poziom hierarchii — `Menu`

**Poprawiony błąd projektowy z tej samej sesji:** pierwsza wersja importu
danych klienta (Wigilia Hotelu Niedźwiadek) potraktowała całe menu jako
`Recipe`, a pojedyncze dania jako `Ingredient`. User: „powinno być Menu /
Przepis / Składniki, a teraz mamy Menu w przepisach, a całe danie jest
Składnikiem." Poprawnie:

- **Menu** (nowy model, `apps/recipes/models.py`) — pakiet na wydarzenie
  (np. "Menu 1"), ma `package_price_per_person`, `target_fc_pct`, i przez
  `MenuItem` (through model, `quantity` = porcji/gościa) wskazuje na wiele
  **Recipe** (dania).
- **Recipe** = danie (np. "Karp pieczony w cebuli"), tak jak było — ale
  dostał `manual_cost_override` (koszt/porcję wpisany ręcznie, omija
  rozbicie na `RecipeIngredient`), bo dla gotowego dania często nie zna się
  jeszcze surowego rozbicia na składniki, a i tak trzeba jakoś policzyć FC%
  menu, w którym to danie występuje.
- **`Recipe.has_cost_data`** (property) — `True` gdy jest ręczna cena LUB
  choć jeden składnik. Bez tego pusty przepis wygląda jak przepis o koszcie
  zero (świetny FC%!) zamiast "jeszcze nie wiadomo" — `Menu.is_cost_complete`
  używa tego, żeby ostrzec, że suma jest zaniżona, gdy nie wszystkie dania
  mają jeszcze koszt.
- Migracja `recipes.0002` — na `kelnerzy` zastosowana, w lokalnym repo
  (`~/Claude/fc.sudomie.pl`) katalog `apps/*/migrations/` jest częściowo
  root-owned (bind mount Dockera z wcześniejszej sesji, kontener pisze jako
  root) — `0002` nie dała się skopiować lokalnie bez sudo, którego nie mam
  na tej maszynie. Nieblokujące (produkcja ma poprawny stan), ale do
  ogarnięcia (`sudo chown -R konrad:konrad apps/*/migrations/`) przed
  `git init`.
- Dane Hotelu Niedźwiadek (`niedzwiadek-test`) przebudowane pod nowy model:
  3 błędne "Recipe=Menu" skasowane, 26 "Ingredient=danie" zamienione na
  właściwe `Recipe`, utworzone 3 `Menu` (139/199/239 zł/os) z `MenuItem`
  wskazującymi na te przepisy. Żadne danie nie ma jeszcze kosztu (ani
  ręcznego, ani składników) — to prawdziwy stan, nie wymyślony.

## 🟢 Stan na 2026-09-07: WDROŻONE na `fc.sudomie.pl` (produkcyjnie, na hoście `kelnerzy`)

Backend (2026-04-26) + szablony/migracje/seed/publiczny landing z kalkulatorem
(dzisiaj) — aplikacja działa i jest publicznie dostępna. Zweryfikowane
end-to-end przez prawdziwe żądania HTTP (nie tylko `manage.py check`), po
drodze naprawione 3 blokujące błędy w kodzie z kwietnia (rejestracja 500,
tworzenie/edycja przepisu 500, zapis przepisu z pustym wierszem formsetu
zawsze failował — szczegóły w SUMMARY, sesja 2026-09-07).

**Host:** `kelnerzy` (192.168.1.190, alias SSH `ssh kelnerzy`) — TEN SAM LXC
co Kaszubska Agencja Kelnerska (`kadragastro.pl`), ale osobny, izolowany
`docker-compose` w `/opt/fc-sudomie-pl/` (własna sieć Dockera, własny
Postgres, własny `cloudflared` — zero współdzielenia kontenerów z
`/opt/agencja-kelnerska/`). User: „kelnerzy już wychodzą z użycia. Może tam
być podpięte, bo możliwe, że dorzucimy to do strony" — świadomie
współdzielony host, nie wypadek.

**Tunel Cloudflare:** nowy, dedykowany — nazwa `fc-sudomie-pl`, ID
`e284f126-8ce8-4e84-b099-ce132dfe7c0b`. Config w
`/opt/fc-sudomie-pl/cloudflared/config.yml`, credentials w tym samym
katalogu (`e284f126-....json`, skopiowane z `/root/.cloudflared/` na hoście).
**Osobny tunel, nie dopisany do istniejącego `agencja-kelnerska`** —
prościej i bezpieczniej niż spinanie dwóch projektów jedną siecią Dockera
tylko po to, żeby dzielić proces `cloudflared`.

**⚠️ Gotcha przy `cloudflared tunnel route dns` na tym hoście — POWTÓRZ SIĘ
znany problem:** `cert.pem` na `kelnerzy` jest dziś autoryzowany dla zony
`kadragastro.pl` (przelogowano się 2026-09-02 przy migracji tamtej domeny).
Próba `route dns` dla `fc.sudomie.pl` bez podmiany certu stworzyła BŁĘDNY
rekord `fc.sudomie.pl.kadragastro.pl` (CNAME pod złą zoną) — wciąż wisi w
Cloudflare jako nieszkodliwy śmieć (nikt go nie odpytuje), celowo nie
usuwany (brak prostego sposobu z CLI bez tokena API, ten sam wzorzec co
poprzedni raz — patrz stary gotcha w historii `agencja-kelnerska`). Fix:
tymczasowo podmienić `cert.pem` na `cert.pem.sudomie.bak` (backup sprzed
re-loginu do zony kadragastro.pl, leży w `/root/.cloudflared/` na hoście),
zrobić `route dns` dla hosta pod zoną `sudomie.pl`, **podmienić cert.pem
z powrotem** zaraz po (żeby nie zostawić hosta bez autoryzacji do
kadragastro.pl). **Przy KAŻDYM kolejnym `*.sudomie.pl` na tym hoście —
sprawdź cert.pem PRZED `route dns`, nie po fakcie.**

Login demo: `demo@fc.sudomie.pl` / `demo12345` (`manage.py seed`).
Admin: `/admin/` (superuser nie utworzony — do zrobienia jeśli potrzebny
ręczny dostęp poza kontem demo).

**Otwarte:**
1. Brak repo git dla tego projektu — `git init` + pierwszy commit, zanim
   cokolwiek więcej się zmieni (kod na produkcji NIE odpowiada żadnemu
   commitowi, bo commitów jeszcze nie ma).
2. Stray DNS `fc.sudomie.pl.kadragastro.pl` — nieszkodliwy, ale do
   posprzątania jeśli kiedyś będzie dostęp do Cloudflare API/dashboardu.
3. `docker-compose.override.yml` (lokalnie, nginx na 8080) — tylko do
   lokalnego dev na maszynie 192.168.1.238, nie ma go na `kelnerzy` (bazowy
   `docker-compose.yml` ma nginx bez `ports:` w ogóle — wzorzec skopiowany
   z `agencja-kelnerska`, zero otwartych portów poza tunelem).
4. **OCR faktur (Faza 3) — WDROŻONE na produkcję 2026-09-08.** Port z
   `legacy-foodcost/foodcost/foodcost/ingredients/` do `apps/ingredients/`
   (`ocr_service.py`, `invoice_views.py`), URL-e pod `/ingredients/invoice/...`,
   gate `@pro_required` (dekorator w `apps/accounts/decorators.py`) na
   `Organization.plan == 'pro'`. Link w sidebarze widoczny tylko dla planu Pro.
   Organizacja Niedźwiadka przemianowana na **"Hotel Niedźwiadek SPA & Natura"**
   i przestawiona na `plan='pro'` (jedyna organizacja z dostępem na razie).
   `OPENAI_API_KEY` (Service Account, nie osobisty — przeżywa zmiany na
   koncie OpenAI Konrada) dodany ręcznie do `.env` na `kelnerzy` przez usera
   (nie wklejany w czacie — świadomie, żeby nie trafił do transkryptu),
   zweryfikowany `client.models.list()` z kontenera — auth działa, `gpt-4o`
   dostępny. **Nie przetestowane jeszcze z prawdziwą fakturą** (upload → OCR
   → potwierdzenie → zapis SupplierPrice) — zrobić z Michałem przy okazji
   pierwszego prawdziwego wgrania.
   **Znaleziony i naprawiony blocker przed testem:** organizacja Niedźwiadka
   miała 0 dostawców i 0 składników — dropdown w kroku potwierdzenia miał
   tylko "nie dopasowano", więc fizycznie nie dało się nic zapisać z
   pierwszej faktury. Dodana opcja "+ Utwórz nowy składnik" (domyślna gdy
   fuzzy match nic nie znajdzie, dedup po `name__iexact`), checkbox "zapisz"
   teraz domyślnie zaznaczony na każdym wierszu.
   **Update:** dostawca też jest teraz opcjonalny na wgrywaniu — puste pole
   = `_match_supplier()` próbuje dopasować `supplier_name` wyciągnięty przez
   AI do istniejących `Supplier` (overlap słów), a na ekranie potwierdzenia
   jest dropdown z opcją "+ Utwórz nowy" (ten sam wzorzec co dla składników).
   Michał w ogóle nie musi nic zakładać ręcznie przed pierwszym testem.
5. **Migracja danych Hotelu Niedźwiadek** — realne ceny/składniki z produkcji
   `foodcost.sudomie.pl` (MySQL/GoDaddy) do organizacji Niedźwiadek w
   fc.sudomie.pl (Postgres) — dopiero po zgodzie Michała, seed testowy
   (`niedzwiadek-test`) jest przestarzały i nie nadaje się do podmiany 1:1.
6. **Monetyzacja OCR dla reszty klientów** — na razie tylko ręczne przełączenie
   `plan='pro'` w shellu. Docelowo albo płatność per-token/wgranie, albo prosty
   abonament — nierozstrzygnięte, do decyzji jak będzie pierwszy klient płacący.
7. **Eksport (2026-09-08) — WDROŻONE na produkcję.** CSV + Excel (`openpyxl`)
   listy składników z aktualnymi cenami dostawców — przycisk przy widoku
   Składniki (`apps/ingredients/export_views.py`). Word (`python-docx`)
   eksport Menu z rozbiciem kosztu/porcję i FC% — przycisk przy szczególe
   Menu (`apps/recipes/export_views.py`). Zweryfikowane end-to-end na
   tymczasowym stosie Postgres+Django z realnym Client i danymi testowymi
   (nie tylko `manage.py check`) — patrz SUMMARY sesji.
8. **Znany i naprawiony w tej sesji gap: brak migracji `recipes.0002` lokalnie.**
   Katalog `apps/*/migrations/` jest root-owned od kwietniowego bind-moutna
   Dockera (patrz stary wpis niżej w tym pliku) — bez sudo (ani na tej
   maszynie, ani na `proxmox`) nie da się tam nic dopisać. Migracja `0002`
   ŻYJE na produkcji (`kelnerzy`), ale nie w lokalnym repo git — jeśli ktoś
   kiedyś zrobi `git clone` tego repo i spróbuje odpalić migracje od zera,
   brakujący plik wywali błąd przy modelach `Recipe`/`Menu`. Fix: zdobyć
   sudo na tej maszynie i `sudo chown -R $(whoami) apps/*/migrations/`,
   potem dograć plik z produkcji (treść w
   `kelnerzy:/opt/fc-sudomie-pl/apps/recipes/migrations/0002_historicalrecipe_manual_cost_override_and_more.py`).

---

## Kontekst projektu

Darmowy SaaS do zarządzania food costem dla branży HoReCa.

**Problem:** Jedyna dostępna alternatywa to kalkulator Unilever — Excel w przeglądarce z eksportem PDF. Brak real-time kalkulacji, brak historii cen, brak importu faktur, brak yield factor.

**Nasz wyróżnik:** multi-tenant, real-time FC%, import faktur OCR (OpenAI Vision), yield factor, preferred supplier per składnik, mobile-first.

**Model biznesowy:** darmowy → lead gen dla sudomie.pl (custom dev), agregowane dane o cenach jako wartość rynkowa, późniejszy plan Pro.

**Polityka prywatności:** Użytkownicy dobrowolnie przesyłają dane cenowe w zamian za darmowe narzędzie. Polityka explicite pozwala na anonimową agregację cen. `accepted_tos_at` na modelu Organization.

**2026-09-08 — konsolidacja:** `foodcost.sudomie.pl` (Hotel Niedźwiadek, GoDaddy/MySQL,
kod Konrada dla szefa kuchni Michała) przeniesiony jako archiwum do
`legacy-foodcost/` w tym repo — produkcja na GoDaddy nadal działa bez zmian,
to tylko kopia kodu/kontekstu w jednym miejscu. Michał widział fc.sudomie.pl
i wolałby przejść na tę wersję, pod warunkiem że dostanie **OCR faktur**
(wgraj PDF/zdjęcie faktury → OpenAI Vision → auto-uzupełnione ceny) —
funkcja istnieje w `legacy-foodcost/foodcost/foodcost/ingredients/ocr_service.py`,
`invoice_views.py`, `spreadsheet_service.py` jako gotowy wzorzec do
przeniesienia (Faza 3, patrz sekcja "Co zostało do zrobienia" niżej).
Dane testowe organizacji `niedzwiadek-test` w fc.sudomie.pl są ze starego
seeda/importu menu — realne aktualne ceny/składniki żyją tylko w produkcji
`foodcost.sudomie.pl` (MySQL na GoDaddy), do migracji dopiero gdy Michał
faktycznie przechodzi na fc.sudomie.pl (nie robić przed jego zgodą — to
włącza/wyłącza narzędzie, którego używa codziennie).

---

## Stack

| Element | Szczegóły |
|---|---|
| Framework | Django 5.x |
| Baza | PostgreSQL 16 (Docker) |
| Serwer | gunicorn + nginx (Docker) |
| Infrastruktura | Docker Compose na ThinkCenter |
| Dostęp | Cloudflare Tunnel → fc.sudomie.pl |
| Frontend | Bootstrap 5 + Alpine.js |
| IP ThinkCenter | 192.168.1.??? (uzupełnić) |

---

## Architektura multi-tenant

Row-level isolation: każdy model biznesowy ma `organization = FK(Organization)`.

`TenantQuerySetMixin` w `apps/core/mixins.py` — każdy widok CRUD filtruje po `request.user.organization`.

**WAŻNE — guard na None:**
```python
class TenantQuerySetMixin:
    def get_queryset(self):
        if not self.request.user.organization_id:
            return super().get_queryset().none()
        return super().get_queryset().filter(
            organization=self.request.user.organization
        )
```
Bez guarda `filter(organization=None)` wycieka dane innych tenantów bez organizacji.

**Admin:** `is_staff=True` → widzi wszystkich tenantów (celowo, dla obsługi serwisu). Brak filtrowania w ModelAdmin.

---

## Struktura projektu (stan: Faza 1 w toku)

```
/home/konrad/Claude/fc.sudomie.pl/
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .dockerignore
├── entrypoint.sh
├── requirements.txt
├── manage.py
├── nginx/default.conf
├── cloudflared/config.yml.example
├── config/
│   ├── __init__.py
│   ├── settings.py          ✅ gotowe
│   ├── urls.py              ✅ gotowe
│   └── wsgi.py              ✅ gotowe
├── apps/
│   ├── core/
│   │   ├── apps.py          ✅
│   │   ├── mixins.py        ✅ TenantQuerySetMixin z guardem
│   │   ├── views.py         ✅ dashboard view
│   │   └── urls.py          ✅
│   ├── accounts/
│   │   ├── models.py        ✅ User, Organization, LoginEvent (immutable)
│   │   ├── forms.py         ✅ RegisterForm (z accept_tos), LoginForm, OrganizationSetupForm
│   │   ├── views.py         ✅ register, login (rate limit 5 prób/15min), logout, setup
│   │   ├── urls.py          ✅
│   │   ├── decorators.py    ✅ @setup_required
│   │   ├── signals.py       ✅ LoginEvent via Django signals
│   │   └── admin.py         ✅ LoginEventAdmin readonly
│   ├── ingredients/
│   │   ├── models.py        ✅ Category, Supplier, Ingredient, SupplierPrice
│   │   ├── forms.py         ✅ wszystkie formy z tenant-filtered querysetami
│   │   ├── views.py         ✅ CRUD + api_ingredient_price endpoint
│   │   ├── urls.py          ✅
│   │   └── admin.py         ✅
│   └── recipes/
│       ├── models.py        ✅ RecipeContext, Recipe, RecipeIngredient (z logiką FC%)
│       ├── forms.py         ✅ RecipeForm + make_recipe_ingredient_formset
│       ├── views.py         ✅ CRUD przepisów i kontekstów
│       ├── urls.py          ✅
│       └── admin.py         ✅
├── templates/               ❌ NIE ZACZĘTE — przerwano przed zapisem
│   ├── base.html
│   ├── core/dashboard.html
│   ├── accounts/...
│   ├── ingredients/...
│   └── recipes/...
├── static/css/app.css       ❌ NIE ZACZĘTE
└── apps/core/management/
    └── commands/seed.py     ❌ NIE ZACZĘTE
```

---

## Co zostało do zrobienia (Faza 1)

### Priorytet 1 — bez tego nic nie działa
1. **`templates/base.html`** — Bootstrap 5 + sidebar + HTMX CSRF listener
2. **Pozostałe szablony** — accounts (register, login, setup), core (dashboard), ingredients (list, form, detail), recipes (list, form, detail)
3. **`static/css/app.css`** — zmienne kolorystyczne FC%, badge styles
4. **`apps/core/management/commands/seed.py`** — dane testowe

### Priorytet 2 — deploy
5. Skopiować pliki na ThinkCenter
6. Stworzyć `.env` z prawdziwymi wartościami
7. `docker compose up -d --build`
8. Weryfikacja przez fc.sudomie.pl

---

## Kluczowe decyzje z sesji 2026-04-26 (kodowanie)

### Logika cen (SupplierPrice)
- `price_per_base_unit` przeliczany automatycznie w `save()` — formula: `price / (package_size * factor)`
- `package_size=None` → `qty=1` (cena za 1 jednostkę)
- `unit='opak'` → `price / package_size` (package_size w jednostkach bazowych)
- Przykład: 2 PLN za 500g, base='kg' → `2 / (500 * 0.001)` = 4 PLN/kg ✓

### Yield factor w RecipeIngredient
- `yield_factor=0.85` → 15% odpadów → potrzebujesz `quantity / 0.85` surowca
- `get_cost()` = `price_per_base * (quantity_in_base / yield_factor)`

### FC status (bez kontekstu)
- `≤30%` → ok (zielony)
- `30-38%` → warning (pomarańczowy)
- `>38%` → danger (czerwony)
- Z kontekstem: `fc_status_for_context(ctx)` używa `ctx.target_fc_pct` ± 8%

### Rate limiting logowania
- Session-based, bez zewnętrznych bibliotek
- 5 nieudanych prób → lockout 15 minut
- `request.session['login_attempts']` + `login_lockout_until` (timestamp)

### LoginEvent — immutability
- `save()` rzuca `PermissionError` gdy `self.pk` istnieje
- `delete()` zawsze rzuca `PermissionError`
- Zdarzenia przez Django signals (`user_logged_in`, `user_logged_out`, `user_login_failed`)

---

## Security — checklist

- [x] SECRET_KEY bez fallbacku → `raise ImproperlyConfigured`
- [x] `SESSION_COOKIE_SECURE = True` hardcoded
- [x] `CSRF_COOKIE_SECURE = True` hardcoded
- [x] `SESSION_COOKIE_HTTPONLY = True`
- [x] `SESSION_COOKIE_SAMESITE = 'Lax'`
- [x] `SECURE_HSTS_SECONDS = 31536000`
- [x] `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`
- [x] `SECURE_CONTENT_TYPE_NOSNIFF = True`
- [x] nginx: `server_tokens off`
- [x] nginx: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`
- [x] TenantQuerySetMixin z guardem na `organization=None`
- [x] Rate-limit na login (session-based)
- [x] LoginEvent immutable
- [x] `@setup_required` decorator
- [ ] `FileExtensionValidator` na uploadach (Faza 2, przy upload faktur)
- [ ] `/media/` przez Django `serve_media` z `@login_required` (Faza 2)

---

## Deployment (ThinkCenter)

```bash
cd /home/konrad/Claude/fc.sudomie.pl
docker compose up -d --build
docker compose ps
docker compose logs web --tail=20
```

Transfer plików na ThinkCenter (jeśli inna maszyna):
```bash
git archive HEAD [pliki] -o /tmp/paczka.tar
scp /tmp/paczka.tar user@thincenter:/tmp/
# Na ThinkCenter:
cd /opt/fc && tar -xf /tmp/paczka.tar
docker compose up -d --build
```

### Gotcha deployment
- `git archive | ssh` przez `!` prefix w zsh — rozbija wieloliniowe komendy. Fix: tar do pliku, potem scp
- `docker compose restart` nie przeładowuje `.env` — używać `docker compose up -d`
- Django middleware nadpisuje nginx headers (XFrameOptions, Referrer) — nie duplikować w nginx
- `DEBUG=False` wymaga `collectstatic` — robi to automatycznie `entrypoint.sh`

---

## Zmienne środowiskowe (.env)

```
DJANGO_SECRET_KEY=<generuj: python -c "import secrets; print(secrets.token_hex(50))">
DJANGO_DEBUG=False
DB_NAME=fc
DB_USER=fc
DB_PASSWORD=<silne hasło>
DB_HOST=postgres
DB_PORT=5432
CSRF_TRUSTED_ORIGINS=https://fc.sudomie.pl
OPENAI_API_KEY=<klucz dla OCR faktur — Faza 3>
```
