# FoodCost — fc.sudomie.pl

Koszt dań i pakietów weselnych na osobę dla gastronomii: składniki z cenami dostawców i historią,
przepisy z wydajnością (yield), pakiety (menu) z food cost względem celu, oferty dla klientów,
odczyt faktur ze zdjęć i PDF (OCR, plan Pro / 30 dni próby), eksport CSV / Excel / Word.

## Stos

Django 5.2, PostgreSQL 16, gunicorn, nginx, Cloudflare Tunnel (Docker Compose), django-simple-history, jazzmin.

## Uruchomienie lokalne

```sh
cp .env.example .env          # sekrety, DJANGO_DEBUG=True, CSRF_TRUSTED_ORIGINS
docker compose -p fc-local up -d --build postgres web   # BEZ cloudflared — to tunel produkcji
docker compose -p fc-local exec -T web python manage.py test
```

Podgląd w przeglądarce: dołóż `nginx` z własnym portem (np. plik override z `127.0.0.1:8097:80`).

## Flagi (`.env`)

- `OFFERS_ENABLED` — moduł Ofert.
- `DEMO_MAX`, `DEMO_HOURS`, `DEMO_PER_HOUR` — „Wypróbuj demo” bez rejestracji (0 = wyłączone).
- `DEMO_PASSWORD` — konto do pokazów `demo@fc.sudomie.pl` (`manage.py seed --reset` przed pokazem).

Dane demo: `apps/core/data/demo.json` i `demo-faktura.json` (przykładowa faktura bez wywołania OpenAI).

## Dokumenty

`HANDOFF.md` (stan, wdrożenie, pułapki), `SUMMARY.md` (historia sesji), `PLAN.md`, `DESIGN.md`, `docs/WDROZENIA.md`.

Repozytorium prywatne — kod produktu komercyjnego (Komorowski & Windorpski sp. z o.o.).
