# Historia sesji — foodcost.sudomie.pl

## Sesja 2026-04-26 — Audyt bezpieczeństwa + aktualizacja dokumentacji
### Zrobiono
- Audyt bezpieczeństwa na podstawie doświadczeń z InnDesk security hardening
- Zaktualizowano HANDOFF.md: dodano sekcję "Workflow sesji", "Stan bezpieczeństwa"
- Zidentyfikowano priorytety do naprawy przed wersją demo

### Zadziałało
- Audyt statyczny (bez uruchamiania serwera) — wystarczający do identyfikacji kluczowych problemów

### Nie zadziałało
- (sesja tylko dokumentacyjna, brak zmian w kodzie)

### Następne kroki
- **Nowe zadanie:** wersja demo foodcost dla pokazywania klientom
  - Izolowane sesje demo (wzorowane na InnDesk `apps/demo_session`)
  - Seed z przykładowymi danymi (receptury, składniki, dostawcy)
  - Auto-login po wyborze roli
- Naprawić CRITICAL: usunąć fallback `SECRET_KEY` z `settings.py`
- Rozważyć `SESSION_COOKIE_SECURE = True` i `CSRF_COOKIE_SECURE = True`

---

## Sesja 2026-03-22

### Zrobiono
- Dodano endpoint API `GET /recipes/api/v1/recipes/` z autoryzacją Bearer token (`OFERTY_API_TOKEN`)
- Dodano `_check_api_token()` i `api_recipes()` w `recipes/views.py`
- Dodano URL `recipes/api/v1/recipes/` w `recipes/urls.py`
- Dodano `OFERTY_API_TOKEN` do `settings.py` (czytany z `.env`)
- Bugfix: polskie locale "60,00" w polach Decimal przy zapisie przepisu:
  - `recipe_edit.html` — `{% load l10n %}` + `|unlocalize` na polach: `selling_price`, `package_price_per_person`, `yield_portions`, `quantity[]`, `yield_factor[]`
  - `recipe_edit` view — funkcja `_dec(val)` zamieniająca przecinek na kropkę jako backup

### Zadziałało
- `|unlocalize` w szablonie — renderuje "60.00" zamiast "60,00", eliminuje błąd `ValidationError: 'Wartością „60,00" musi być liczba dziesiętna'`
- API endpoint działa poprawnie — grupy.sudomie.pl pobiera przepisy i synchronizuje koszty FC

### Nie zadziałało
- Sama funkcja `_dec()` w widoku nie wystarczyła jako jedyne rozwiązanie — błąd był identyczny po jej dodaniu. Przyczyna: nowe pliki wgrywane ale template cache Passengera. Dopiero kombinacja `_dec()` + `|unlocalize` w szablonie rozwiązała problem kompletnie.

### Stan systemu
- Aplikacja działa na GoDaddy shared hosting, Django 4.2, MySQL utf8mb4
- Integracja z oferty.sudomie.pl (grupy.sudomie.pl) aktywna przez REST API z Bearer token
- Restart: `touch ~/foodcost/tmp/restart.txt`
- Logi: `tail -30 ~/foodcost_logs`

### Następne kroki
- Przetestować przepływ end-to-end: zmiana ceny składnika → sync FC → zmiana kosztu menu w ofercie
- Rozważyć automatyczny sync (cron lub webhook) zamiast ręcznego przycisku "Sync FC"
- Backlog: planer tygodniowy, historia cen składnika, eksport menu do PDF

---

## Sesja 2026-03-22 — mobile UX dla Michała

### Zrobiono
- Audyt mobilny całej aplikacji — większość widoków już miała mobile wersje
- `recipe_edit.html` — dodano FC summary bar dla mobile:
  - Fixed bar przyklejony na dole ekranu podczas scrollowania (widoczny cały czas)
  - Gdy naturalny blok na końcu strony wchodzi do widoku → fixed bar zjeżdża w dół (IntersectionObserver)
  - Pokazuje: Koszt/porcja | FC% (kolorowy pill) | Łączny koszt
  - Oba bary aktualizują się na bieżąco przez ten sam JS (updateFCPanel)

### Zadziałało
- IntersectionObserver na naturalnym bloku — czyste przejście fixed→static bez JS scroll listener
- `transition: opacity + transform` — płynne chowanie fixed bara
- Pattern: dwa elementy z tymi samymi danymi (fixed + base), Observer przełącza widoczność

### Stan mobilny aplikacji po sesji
| Widok | Mobile |
|---|---|
| `base.html` (sidebar) | ✅ overlay + hamburger |
| `dashboard.html` | ✅ karty 2×2 |
| `recipe_list.html` | ✅ desktop tabela + mobile karty |
| `recipe_edit.html` | ✅ responsywne składniki + FC bar na dole |
| `recipe_detail.html` | ✅ table-responsive |
| `price_update.html` | ✅ desktop tabela + mobile karty |

### Następne kroki
- Backlog bez zmian: planer tygodniowy, historia cen, eksport PDF
