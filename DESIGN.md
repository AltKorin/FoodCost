# DESIGN — FoodCost SaaS

## Kolorystyka

| Rola | Kolor | Hex |
|---|---|---|
| Primary | Zieleń (food, świeżość) | `#2d6a4f` |
| Primary dark | Hover/active | `#1b4332` |
| FC OK | Zielony | `#2d6a4f` |
| FC Warning | Pomarańczowy | `#f4a261` |
| FC Danger | Czerwony | `#e63946` |
| Background | Jasny szary | `#f8f9fa` |
| Sidebar | Ciemny | `#1b2a23` |

## Zasada kolorowania FC%

```
FC% ≤ target              → badge zielony (ok)
target < FC% ≤ target+8%  → badge pomarańczowy (warning)
FC% > target+8%           → badge czerwony (danger)
```

Target FC% definiowany per RecipeContext (bufet: 28%, karta: 32% itp.).

## Typografia

Bootstrap 5 defaults — bez custom fontów (szybkość ładowania, zero CDN font).

## Layout

### Desktop
```
┌─────────────────────────────────────────┐
│  Navbar (logo + user + nav links)       │
├──────────┬──────────────────────────────┤
│ Sidebar  │  Content area               │
│          │                             │
│ Dostawcy │  Tabele / Formularze        │
│ (szybki  │  / Dashboard cards          │
│  dostęp) │                             │
└──────────┴──────────────────────────────┘
```

### Mobile
- Hamburger → overlay sidebar
- Topbar z akcją Zapisz po prawej
- Tabele → karty (Bootstrap `d-none d-md-table-row` pattern)
- FC bar fixed na dole ekranu w edytorze przepisu (IntersectionObserver hide)

## Komponenty

### FC Badge
```html
<span class="badge fc-badge fc-{{ recipe.fc_status }}">{{ recipe.food_cost_pct }}%</span>
```
CSS klasy: `.fc-ok` (zielony), `.fc-warning` (pomarańczowy), `.fc-danger` (czerwony).

### Live FC Preview (edytor przepisu)
- Alpine.js `x-data` na formularzu
- `fetch('/api/ingredients/<id>/price/')` → cache w JS object
- Przelicza przy każdej zmianie quantity/unit/supplier
- Prawy panel: Koszt/porcję | FC% | Status

### Panel cen dostawcy
- Tabela inline editable: `<input type="number" step="0.01">` per składnik
- Tab/Enter nawigacja między polami
- Batch save jednym przyciskiem (jeden POST)
- Mobile: karty zamiast tabeli

### Dashboard cards
```
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ Łączna   │ │ Dania    │ │ Dania    │ │ Śr. FC%  │
│ liczba   │ │ ok FC%   │ │ danger   │ │ wszystk. │
│ przepisów│ │          │ │          │ │          │
└──────────┘ └──────────┘ └──────────┘ └──────────┘
```

## Przewaga UX nad konkurencją (Unilever kalkulator)

| Feature | Nasz SaaS | Unilever |
|---|---|---|
| Real-time FC przy wpisywaniu | ✅ Alpine.js | ❌ ręczne odświeżanie |
| Yield factor (odpady) | ✅ per składnik | ❌ brak |
| Preferred supplier per składnik | ✅ | ❌ brak |
| Historia cen | ✅ (Faza 3) | ❌ brak |
| Import faktur OCR | ✅ (Faza 3) | ❌ brak |
| Import Excel/CSV | ✅ | ❌ brak |
| Multi-context (bufet/karta/grupy) | ✅ | ❌ brak |
| Mobile-first | ✅ | ❌ słabo |
| Multi-tenant (wiele restauracji) | ✅ | ❌ jednoosobowy |
| Darmowy | ✅ | ✅ |

## Onboarding flow — pustostany

Puste stany z CTA zamiast pustych tabel:
- Brak składników → "Dodaj pierwszy składnik" + przycisk
- Brak dostawców → "Dodaj dostawcę" + krótki opis po co
- Brak przepisów → "Utwórz pierwszy przepis"
- Dashboard bez danych → wizard krok po kroku

## Emaile transakcyjne (Faza 2)

- Potwierdzenie rejestracji
- Reset hasła
- Alerty FC% (tygodniowy digest — dania które przekroczyły target)

From: `noreply@sudomie.pl` (lub dedykowany dla fc.sudomie.pl)
