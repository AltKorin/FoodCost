# HANDOFF — Food Cost Manager
## Hotel Niedźwiadek / sudomie.pl

---

## Kontekst projektu

Aplikacja Django do zarządzania food costem dla **Hotel Niedźwiadek** (Wdzydze Kiszewskie). Zbudowana przez Konrada (sudomie.pl) na potrzeby szefa kuchni **Michała**. Wdrożona na `foodcost.sudomie.pl`.

**Właściciel:** Konrad Komorowski (admin, developer)
**Główny użytkownik:** Michał (szef kuchni) — ma dostęp do wszystkiego poza zarządzaniem użytkownikami

---

## Stack i hosting

| Element | Szczegóły |
|---|---|
| Framework | Django 4.2.11 |
| Baza danych | MySQL (GoDaddy cPanel) — baza `foodcost` |
| Hosting | GoDaddy shared hosting, cPanel, Passenger WSGI |
| Python | 3.11 (virtualenv: `~/virtualenv/foodcost/3.11/`) |
| URL | `foodcost.sudomie.pl` |
| App root | `~/foodcost/` |
| Log Passengera | `~/foodcost_logs` |
| Restart | `touch ~/foodcost/tmp/restart.txt` |

### Krytyczna zasada — passenger_wsgi.py
Na GoDaddy Passenger wczytuje `passenger_wsgi.py` przez `imp.load_source` co powoduje rekursję jeśli plik zawiera cokolwiek poza absolutnym minimum. Plik MUSI być:

```python
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodcost_project.settings')
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

Nigdy nie dodawać tu żadnej logiki, importów Django, ładowania .env itp.

---

## Struktura projektu

```
~/foodcost/
├── passenger_wsgi.py          ← minimalny, patrz wyżej
├── manage.py                  ← ładuje .env automatycznie
├── .env                       ← klucze i dane bazy (nie w repo)
├── requirements.txt
├── fixtures/
│   ├── initial_data.json      ← kategorie + RecipeContext (bufet/grupy/karta)
│   ├── suppliers.json         ← Triada, Iglotex, Chef Culinar
│   └── ingredients_seed.json  ← 60 składników + ceny orientacyjne
├── foodcost_project/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── ingredients/               ← app: składniki, dostawcy, ceny, import
│   ├── models.py
│   ├── views.py               ← dashboard, price_update, ingredient/supplier CRUD
│   ├── invoice_views.py       ← OCR faktur PDF (OpenAI Vision)
│   ├── spreadsheet_views.py   ← import Excel/CSV
│   ├── ocr_service.py         ← PDF → OpenAI Vision → JSON
│   ├── spreadsheet_service.py ← Excel/CSV → parsed rows
│   ├── context_processors.py  ← sidebar_suppliers (globalne dla wszystkich widoków)
│   └── templatetags/
│       └── foodcost_tags.py   ← filtry: get_item, split, enumerate
└── recipes/                   ← app: przepisy, food cost
    ├── models.py
    ├── views.py               ← recipe CRUD, FC kalkulacja, ingredient report
    └── urls.py
```

---

## Modele danych

### ingredients app

**Category** — kategorie składników (Mięso i drób, Ryby, Nabiał itd.), pole `order` do sortowania

**Supplier** — dostawcy (Triada, Iglotex, Chef Culinar), pola: name, contact_name, phone, email, delivery_days, notes

**Ingredient** — składniki, pola: name, category(FK), base_unit (kg/g/l/ml/szt/opak), notes, is_active
- Miękkie usuwanie: `is_active=False` zamiast DELETE
- `get_current_best_price()` → najniższa aktualna cena w jednostce bazowej
- `get_current_prices()` → wszystkie aktualne ceny

**SupplierPrice** — ceny składników u dostawców
- Klucze: ingredient(FK), supplier(FK)
- Pola: price, unit, package_size (opcjonalnie — ilość w kartonie), price_per_base_unit (auto-kalkulowane w save()), valid_from (auto_now_add), is_current, is_netto, source_note
- `save()` automatycznie archiwizuje poprzednią cenę tego dostawcy (is_current=False) i przelicza price_per_base_unit
- UNIT_CONVERSIONS i BASE_UNITS w models.py — słowniki do normalizacji jednostek

### recipes app

**RecipeContext** — konteksty serwowania (bufet/grupy/karta) z docelowym FC%

**Recipe** — przepisy/dania
- Pola: name, meal_type (breakfast/lunch/dinner/soup/appetizer/main/dessert/snack/side), contexts(M2M→RecipeContext), yield_portions, selling_price, package_price_per_person, notes
- Properties: `total_cost`, `cost_per_portion`, `food_cost_percentage`, `food_cost_percentage_package`
- `get_fc_status()` → 'ok' (≤30%), 'warning' (30-38%), 'danger' (>38%)

**RecipeIngredient** — składniki przepisu
- Klucze: recipe(FK), ingredient(FK), preferred_supplier(FK nullable)
- Pola: quantity, unit, yield_factor (odpad — 0.85 = 15% strat), is_optional, notes
- `get_price()` → cena wg wybranego dostawcy lub najtańszego
- `get_cost()` → koszt z uwzględnieniem konwersji jednostek i yield_factor

---

## Zmienne środowiskowe (.env)

```
DJANGO_SECRET_KEY=...
DJANGO_DEBUG=False
DB_NAME=foodcost
DB_USER=konrad
DB_PASSWORD=...
DB_HOST=localhost
DB_PORT=3306
OPENAI_API_KEY=sk-...   ← osobny klucz dla tego projektu
```

---

## URL-e aplikacji

```
/                           dashboard
/login/ /logout/

/skladniki/                 lista składników
/skladniki/nowy/            nowy składnik
/skladniki/<pk>/edytuj/     edycja składnika
/skladniki/<pk>/usun/       usunięcie (miękkie)

/dostawcy/                  lista dostawców
/dostawcy/nowy/             nowy dostawca
/dostawcy/<pk>/edytuj/
/dostawcy/<pk>/usun/

/ceny/<supplier_id>/        panel aktualizacji cen (główny widok dla Michała)

/faktury/wgraj/             OCR — wgraj PDF faktury
/faktury/potwierdz/         OCR — potwierdź wyciągnięte ceny

/cennik/wgraj/              Excel/CSV — wgraj plik
/cennik/kolumny/            Excel/CSV — mapowanie kolumn
/cennik/potwierdz/          Excel/CSV — potwierdź ceny

/recipes/                   lista przepisów
/recipes/nowy/              nowy przepis (z live FC preview)
/recipes/<pk>/              szczegół przepisu (breakdown kosztów)
/recipes/<pk>/edytuj/       edycja przepisu
/recipes/raport/skladniki/  strategia zakupów (które składniki się powtarzają)
/recipes/api/cena/<id>/     API — ceny składnika dla live preview (JSON)

/admin/                     Django admin
```

---

## Kluczowe decyzje projektowe

### Normalizacja cen
Wszystkie ceny są normalizowane do jednostki bazowej składnika przy zapisie (`price_per_base_unit`). Przykład: kupujesz łososia po 52 PLN/kg → `price_per_base_unit = 0.0520 PLN/g`. Dzięki temu FC% liczy się poprawnie niezależnie od tego czy w przepisie użyjesz g czy kg.

### Yield factor
W `RecipeIngredient.yield_factor` — np. 0.85 dla ziemniaków po obraniu. Koszt = `(quantity_in_base / yield_factor) * price_per_base_unit`. Domyślnie 1.00 (brak odpadu).

### Wybrany dostawca per składnik w przepisie
`RecipeIngredient.preferred_supplier` — Michał może wybrać konkretnego dostawcę dla każdego składnika w przepisie. Jeśli null → auto-wybiera najtańszego. Widoczne w edytorze przepisu jako tabelka z możliwością kliknięcia w dostawcę.

### Soft delete
Składniki i dostawcy nie są fizycznie usuwane — `is_active=False`. Historia cen zostaje zachowana.

### Context processor
`ingredients.context_processors.sidebar_suppliers` dostarcza listę aktywnych dostawców do każdego szablonu (dla sidebaru). Zarejestrowany w settings.py.

---

## Import danych (trzy metody)

### 1. Panel ręczny — `/ceny/<supplier_id>/`
Tabela inline editable — Michał wpisuje nowe ceny z papierowego cennika. Tab/Enter nawigacja między polami. Batch save jednym przyciskiem.

### 2. OCR faktur PDF — `/faktury/wgraj/`
- `ocr_service.py`: PDF → PyMuPDF → base64 obrazy → OpenAI gpt-4o Vision → JSON
- Prompt wyciąga: nazwa, cena, jednostka, rozmiar opakowania, VAT
- `fuzzy_match_ingredients()` dopasowuje nazwy z faktury do składników w bazie (word overlap ≥50%)
- Krok potwierdzenia: Michał weryfikuje dopasowania, poprawia ręcznie, zatwierdza

### 3. Excel/CSV — `/cennik/wgraj/`
- `spreadsheet_service.py`: openpyxl dla xlsx, csv.reader dla CSV
- Auto-wykrywanie nagłówków przez słowa kluczowe (COLUMN_HINTS)
- Auto-wykrywanie separatora CSV (średnik vs przecinek)
- Krok mapowania kolumn → krok potwierdzenia (identyczny jak PDF)

---

## Szablony — struktura

```
templates/
├── base.html                  ← sidebar + hamburger mobile, Bootstrap 5 CDN
├── dashboard.html             ← statystyki FC, alerty, szybki dostęp do cenników
├── login.html                 ← standalone (bez base.html)
├── ingredients/
│   ├── ingredient_list.html
│   ├── ingredient_edit.html
│   ├── ingredient_confirm_delete.html
│   ├── supplier_list.html
│   ├── supplier_edit.html
│   ├── supplier_confirm_delete.html
│   ├── price_update.html      ← kluczowy widok, desktop tabela + mobile karty
│   ├── invoice_upload.html
│   ├── invoice_confirm.html   ← wspólny wzorzec dla PDF i Excel confirm
│   ├── spreadsheet_upload.html
│   ├── spreadsheet_map.html
│   └── spreadsheet_confirm.html
└── recipes/
    ├── recipe_list.html
    ├── recipe_detail.html     ← breakdown kosztów per składnik + porównanie dostawców
    ├── recipe_edit.html       ← live FC preview, tabelka dostawców, wybór preferred_supplier
    └── ingredient_report.html ← strategia zakupów
```

**Ważne**: Szablony używają `{% load foodcost_tags %}` dla filtrów `get_item`, `split`, `enumerate`. Template tag w `ingredients/templatetags/foodcost_tags.py`.

---

## JavaScript w recipe_edit.html

Live FC preview działa przez:
1. `fetchIngredientData(ingId)` → `/recipes/api/cena/<id>/` → cache w `priceCache`
2. API zwraca: `{price_per_base_unit, base_unit, prices: [{supplier_id, supplier, price, unit, is_netto, is_best}]}`
3. `renderSupplierPanel()` → tabelka dostawców z możliwością kliknięcia
4. `selectSupplier()` → ustawia hidden input `supplier_id[]` + przelicza FC
5. `recalculateFC()` → iteruje składniki, liczy koszt z uwzględnieniem wybranego dostawcy
6. `updateFCPanel()` → aktualizuje prawy panel z FC%, progress bary

---

## Znane problemy i pułapki

| Problem | Rozwiązanie |
|---|---|
| Passenger rekursja | passenger_wsgi.py musi być absolutnie minimalny |
| MySQL charset | Baza musi mieć `utf8mb4` — polskie znaki w auth_permission crashują migrate na latin1 |
| makemigrations zapomniany | Przy nowych modelach zawsze `makemigrations ingredients recipes` przed `migrate` |
| static/ nie istnieje | `mkdir ~/foodcost/static` — usuwa warning, nie wpływa na działanie (Bootstrap z CDN) |
| .env nie ładuje się | settings.py i manage.py ładują .env sami — passenger_wsgi.py tego nie robi (celowo) |
| DNS na az.pl | sudomie.pl miało stare rekordy A na az.pl (37.31.159.52) — zmienione na GoDaddy (92.205.169.115) |

---

## Co zostało do zrobienia (backlog)

### Faza 2 — Planowanie
- Planer tygodniowy (które dania w które dni)
- Automatyczna lista zakupów z planera
- Alerty email gdy FC przekroczy target

### Faza 3 — Analityka
- Historia cen składnika (wykres wzrostu kosztu w czasie)
- Raport rentowności per pozycja karty
- Eksport menu z FC do PDF dla właściciela

### Do poprawy
- fuzzy_match_ingredients — słaba jakość dopasowania dla specyficznych nazw hurtowych (np. "FILET ŁOSOSIA ATL. 2-3KG" → "Filet z łososia")
- Import Excel/CSV — potrzebny test z realnym plikiem od Triady/Iglo/Chef Culinar żeby dostroić COLUMN_HINTS
- OCR — przetestować z realną fakturą, dostroić prompt jeśli wyniki niedokładne

---

## Deployment — szybka ściąga

```bash
# Aktywuj venv
source ~/virtualenv/foodcost/3.11/bin/activate && cd ~/foodcost

# Po zmianach w modelach
python manage.py makemigrations ingredients recipes
python manage.py migrate

# Po zmianach w kodzie/szablonach
touch tmp/restart.txt

# Sprawdź błędy
tail -30 ~/foodcost_logs

# Zainstaluj nowe zależności
pip install -r requirements.txt
```

---

## Dane testowe

Po fresh deploy:
```bash
python manage.py loaddata fixtures/initial_data.json    # kategorie + konteksty
python manage.py loaddata fixtures/suppliers.json       # Triada, Iglotex, Chef Culinar
python manage.py loaddata fixtures/ingredients_seed.json # 60 składników + ceny orientacyjne
```

Ceny w seedzie są **orientacyjne z marca 2025** — Michał powinien zaktualizować przez panel cen lub import z faktury/Excela.
