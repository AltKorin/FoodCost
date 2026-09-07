# PLAN — FoodCost SaaS

## Produkt

Darmowe narzędzie SaaS do zarządzania food costem dla HoReCa. Multi-tenant, każda restauracja ma swoje dane. Real-time kalkulacja FC%, import faktur OCR, yield factor, preferred supplier.

Konkurencja: kalkulator Unilever — Excel w przeglądarce z PDF. Nie ma: real-time, historii cen, importu, yield factor, multi-supplier.

---

## Modele danych

### accounts app

**Organization**
- `name` CharField(200)
- `slug` SlugField(unique=True)
- `created_at` auto_now_add
- `plan` CharField choices: free/pro (na przyszłość)

**User** (extend AbstractUser)
- `organization` FK(Organization, null=True, blank=True)
- `role` CharField choices: owner / admin / chef / viewer

### core app

**TenantQuerySetMixin** — mixin do każdego widoku CRUD:
```python
def get_queryset(self):
    return super().get_queryset().filter(
        organization=self.request.user.organization
    )
```

### ingredients app

**Category**
- `organization` FK
- `name` CharField(100)
- `order` PositiveSmallIntegerField(default=0)

**Supplier**
- `organization` FK
- `name`, `contact_name`, `phone`, `email`, `notes`
- `delivery_days` CharField (opcjonalne)

**Ingredient**
- `organization` FK
- `name`, `category` FK, `base_unit` (kg/g/l/ml/szt/opak)
- `notes`, `is_active` (soft delete)
- `get_best_price()` → najtańsza aktualna cena w jednostce bazowej
- `get_current_prices()` → wszystkie aktualne ceny

**SupplierPrice**
- `ingredient` FK, `supplier` FK
- `price` Decimal, `unit` CharField, `package_size` Decimal nullable
- `price_per_base_unit` Decimal (auto w save())
- `valid_from` auto_now_add, `is_current` Bool, `is_netto` Bool
- `source_note` CharField (skąd pochodzi cena)
- `save()` archiwizuje poprzednią cenę (is_current=False) i przelicza price_per_base_unit

Stałe konwersji jednostek (jak w starym foodcost):
```python
UNIT_CONVERSIONS = {
    'g': {'kg': 0.001, 'g': 1},
    'kg': {'kg': 1, 'g': 1000},
    'ml': {'l': 0.001, 'ml': 1},
    'l': {'l': 1, 'ml': 1000},
    'szt': {'szt': 1},
    'opak': {'opak': 1},
}
```

### recipes app

**RecipeContext**
- `organization` FK
- `name` CharField (np. "Bufet", "Karta", "Grupy")
- `target_fc_pct` Decimal (np. 30.00)

**Recipe**
- `organization` FK
- `name`, `meal_type` choices (breakfast/lunch/dinner/soup/appetizer/main/dessert/snack/side)
- `contexts` M2M → RecipeContext
- `yield_portions` Decimal, `selling_price` Decimal, `package_price_per_person` Decimal
- `notes`
- Properties: `total_cost`, `cost_per_portion`, `food_cost_pct`, `food_cost_pct_package`
- `fc_status(context)` → 'ok' / 'warning' / 'danger'

**RecipeIngredient**
- `recipe` FK, `ingredient` FK, `preferred_supplier` FK nullable
- `quantity` Decimal, `unit` CharField, `yield_factor` Decimal(default=1.00)
- `is_optional` Bool, `notes`
- `get_price()` → cena wg wybranego dostawcy lub najtańszego
- `get_cost()` → koszt z uwzględnieniem konwersji i yield_factor

---

## Flow rejestracji

```
/register/  →  email + hasło  →  User (organization=None)
/setup/     →  nazwa lokalu   →  Organization + user.organization = org, user.role = owner
/dashboard/ →  pusty stan z CTA
```

Redirect guard: `@setup_required` decorator — jeśli `request.user.organization is None` → redirect `/setup/`.

---

## Infrastruktura Docker

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data

  web:
    build: .
    depends_on: [postgres]
    env_file: .env
    volumes:
      - staticfiles:/app/staticfiles
      - media:/app/media

  nginx:
    image: nginx:alpine
    ports: ["80:80"]
    volumes:
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf
      - staticfiles:/app/staticfiles:ro

  cloudflared:
    image: cloudflare/cloudflared:latest
    command: tunnel --no-autoupdate run
    volumes:
      - ./cloudflared:/etc/cloudflared

volumes:
  pgdata:
  staticfiles:
  media:
```

---

## Security — checklist (wbudowane od początku)

- [ ] SECRET_KEY bez fallbacku → `raise ImproperlyConfigured`
- [ ] `SESSION_COOKIE_SECURE = True` hardcoded
- [ ] `CSRF_COOKIE_SECURE = True` hardcoded
- [ ] `SESSION_COOKIE_HTTPONLY = True`
- [ ] `SESSION_COOKIE_SAMESITE = 'Lax'`
- [ ] `SECURE_HSTS_SECONDS = 31536000`
- [ ] `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`
- [ ] `SECURE_CONTENT_TYPE_NOSNIFF = True`
- [ ] nginx: `server_tokens off`
- [ ] nginx: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`
- [ ] `/media/` przez Django `serve_media` z `@login_required` (nie przez nginx)
- [ ] `FileExtensionValidator` na uploadach
- [ ] Tenant isolation przez queryset (nie przez URL)
- [ ] Rate-limit na login (session-based, bez django-ratelimit)

---

## MVP Fazy

### Faza 1 — Szkielet (pierwsza sesja)
Cel: działa rejestracja, dodanie składnika, utworzenie przepisu, poprawny FC%.

### Faza 2 — Core UX
Cel: Michał (lub podobny szef kuchni) może prowadzić całą kuchnię w tym narzędziu.
Panel cen, live FC preview, dashboard, PDF, import Excel.

### Faza 3 — Wzrost i integracje
Cel: gotowe do pokazania Triadzie.
OCR faktur, API `/api/v1/`, historia cen.

---

## Co przenieść ze starego foodcost (port, nie fork)

| Feature | Plik źródłowy |
|---|---|
| Logika konwersji jednostek | `ingredients/models.py` — UNIT_CONVERSIONS |
| `save()` SupplierPrice z archiwizacją | `ingredients/models.py` |
| Live FC JS | `templates/recipes/recipe_edit.html` |
| OCR serwis | `ingredients/ocr_service.py` |
| Import Excel/CSV | `ingredients/spreadsheet_service.py` |
| fuzzy_match_ingredients | `ingredients/invoice_views.py` |
| `_dec()` fix dla polskiego locale | `recipes/views.py` |

Portować ręcznie, nie kopiować — nowa architektura wymaga `organization` FK wszędzie.
