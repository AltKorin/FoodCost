# HANDOFF — FoodCost SaaS

## 2026-10-28 wieczór: Oferty WŁĄCZONE, repozytorium przygotowane

- `OFFERS_ENABLED=True` na produkcji (20:10). Demo i konto do pokazów mają 2 oferty (`apps/core/data/demo.json` → `offers`).
- GitHub: przygotowane do prywatnego `AltKorin/FoodCost` (gałąź `master`, README), push czeka na zgodę (#484).
  Historia przejrzana pod sekrety: tylko wzorce z `.env.example` i nieaktywne `demo12345` ze starego seeda; brak danych klientów.

## 2026-10-28: wyrównanie git ↔ produkcja + demo bez rejestracji — WDROŻONE 19:25 (`af539fd`)

- **Git = produkcja**: commit `7a23a35` zawiera 32 pliki wdrażane wybiórczo od 8.09 (sha256 = `/opt/fc-sudomie-pl`).
  Porównanie: kopia produkcji (rsync tylko do odczytu) vs lokalnie vs git. Różnice po nim tylko celowe: commit `af539fd`.
- **`af539fd`**: „Wypróbuj demo” (`apps/core/demo.py`, piaskownica na sesję, `Organization.demo_until`, migracja
  `accounts.0003`), Oferty za flagą `OFFERS_ENABLED` (domyślnie off → menu ukryte, `/offers/*` = 404; migracja `offers.0001`),
  stopka sudomie (#474), `seed` bez hasła w kodzie (było `demo12345`; teraz `DEMO_PASSWORD`, na serwerze wymagane).
- **OCR w demo wyłączony** (`ocr_available`, `ocr_access.reserve_read`) — każdy odczyt kosztuje w OpenAI.
- Testy 54/54: `docker compose -p fc-local exec -T web python manage.py test`.
- **Wdrożone** (backup `kelnerzy:/root/fc-backup-demo-20261028-1752`: `db.dump` + `code.tgz`; `.env`: `OFFERS_ENABLED=False`, `DEMO_MAX=200`, `DEMO_HOURS=24`, `DEMO_PER_HOUR=60`, `DEMO_PASSWORD`). Przebieg: backup bazy → rsync całego drzewa (bez `.env`, `media`, `cloudflared`, `legacy-foodcost`,
  `docs`) → do `.env`: `DEMO_MAX=200`, `OFFERS_ENABLED=False`, `DEMO_PASSWORD` → `docker compose up -d --build web` →
  `migrate` (accounts.0003, offers.0001; sprawdzić najpierw `showmigrations`) → `collectstatic` → GA/Consent na `/`,
  `/register/`, `/regulamin/` (zasada wdrożeń) → smoke.
- **Konto do pokazów** `demo@fc.sudomie.pl` (Restauracja Demo, nie wygasa): hasło = `DEMO_PASSWORD` z `.env` na serwerze
  (`ssh kelnerzy grep DEMO_PASSWORD /opt/fc-sudomie-pl/.env`). Dane z `apps/core/data/demo.json` (`15eaa37`, wdrożone 19:37).
  **Przykładowa faktura** (`ac8a75f`, wdrożone 20:00): w demo i na koncie do pokazów „Odczytaj przykładową fakturę” —
  gotowy wynik OCR z `apps/core/data/demo-faktura.json` przez prawdziwe dopasowanie i zatwierdzenie, bez OpenAI.
  Pozycje tylko z dostawcy, od którego demo już kupuje (Makro) — inaczej podwyżka nie zmienia kosztu (liczy się najtańsza cena).
  **Przed pokazem**: `ssh kelnerzy 'cd /opt/fc-sudomie-pl && docker compose exec -T web python manage.py seed --reset'`.
- **INCYDENT 28.10 18:00–19:17**: pierwszy `docker build` → ext4 LXC 120 `emergency_ro` (pula LVM-thin hosta `kawaleryjska`
  przepełniona; 128 GB przydziałów na 58 GB puli) → fc i kelnerzy 502. Naprawa: `pct stop/fsck/start 120` (Konrad),
  `docker builder prune -af` + usunięte 3 obrazy `before-*` (zostaje `before-trial30-20260921`), `pct fstrim 120` → pula 81%.
  **Przed każdym buildem na 120 sprawdzić pulę hosta** (`lvs pve/data`) i czyścić build cache po wdrożeniu.

### Gotcha (28.10)
- Pasek zgody GA jest `position-fixed` na dole — zasłaniał ostatni przycisk strony (`e44c6bf`: margines body, gdy widoczny).
  Lokalnie bez `GA_MEASUREMENT_ID` paska nie ma: testy przycisków na dole strony rób też na produkcji.
- W HTML `gtag('config', 'G\u002D…')` (escapejs) — `grep` po ID liczy 1 trafienie; sprawdzaj `dataLayer` w przeglądarce.
- Wysyłka: `rsync -rltz` (bez `-a` — nie nadpisywać właściciela/uprawnień na serwerze), wykluczenia jak w HANDOFF, w tym
  `docker-compose.override.yml` (lokalny port 8080 — na produkcji otworzyłby nginx).
- Lokalnie uruchamiaj TYLKO `postgres web` (+ `nginx` z własnym portem) pod `-p fc-local` — samo `up` podniosłoby
  `cloudflared` z lokalnymi poświadczeniami tunelu produkcji.
- Kod jest w obrazie: `makemigrations` w kontenerze zapisuje plik w kontenerze → `docker compose cp` na dysk.
- `RecipeIngredient`/`MenuItem` mają PROTECT: usunięcie organizacji blokuje się nawet w jednej kaskadzie — najpierw te wiersze.

## 2026-10-04: zdjęcie i infografika WDROŻONE

Po akceptacji użytkownika wdrożono 5 plików visual/deploy. Zdjęcie zespołu
kuchni przy hero (static/images/kitchen-team-v1.webp, ~107 KB), infografika
przy 3 krokach (static/images/foodcost-workflow-v1.png, lazy). CSS v20261004-3.
Backup: kelnerzy:/root/fc-backup-visual-20261004-1525/ ze ścieżkami i analytics.
Rebuild web i collectstatic wykonane. Backend i niewdrożone Oferty bez zmian.
HTTP /, /register/, /regulamin/: 200, GA4 G-6DYFBNNH6X i Consent Mode obecne.
Chromium: oba obrazy, 320/375/768/1280 bez overflow, kalkulatory, klawiatura,
mail gastro_2026_10, zgoda i pamięć wyboru: PASS. Testowe pingi GA blokowano;
nie potwierdzano GA Realtime. Zrzuty/dowody/prompt: docs/landing-2026-10-04/visual/.
Zasady przyszłych wdrożeń: docs/WDROZENIA.md, tracking obowiązkowy.

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

## 2026-10-04: BACKEND — stan końcowy sesji audytu (dla agenta frontendowego i następnej sesji)

- **Na produkcji (wdrożone, kontener przebudowany i zrestartowany):** U1–U3 — `is_cost_complete` (Recipe/Menu), FC% = brak przy niekompletnym koszcie,
  ceny/jednostki niezgodne z bazową pomijane i odrzucane. Landing krok 3 („aplikacja pokazuje ostrzeżenie”) jest teraz **prawdziwy** także dla składnika bez ceny
  i dla niezgodnej jednostki — treść landingu nie wymaga zmiany z powodu U1–U3.
- **Landing:** wdraża agent frontendowy; backend nie jest do tego potrzebny (zmiany tylko szablony/CSS, brak migracji). Kod jest w obrazie Dockera:
  po wgraniu plików wymagane `docker compose up -d --build web` (samo `restart` nie ładuje kodu). Przed wdrożeniem porównać produkcję (backend zmieniony 14:46).
- **NIE obiecywać na landingu:** monitoringu marży imprezy, alertów ani porównania „wtedy → dziś” — tego produkt nie ma (raport, sekcja 6).
- **Otwarte (nienaprawione, kolejność w `docs/audyt-pakietow-2026-10-04.md` sekcja 8):** U5 data faktury vs czas zapisu, U6 atomowość/raport zatwierdzania faktury,
  U4 źródło i wiek ceny w UI, U10 walidatory (yield 0, ilość < 0), U8 constraint unikalności ceny aktualnej (na produkcji 0 duplikatów — można dodać), U7 netto/brutto,
  U9 historia składu, kontrola marży imprezy (wymaga decyzji produktowych). Oferty (`apps/offers`) nadal tylko lokalnie.
- **Testy:** `apps/recipes/tests.py` (12, wdrożone razem z kodem opcjonalnie — na produkcji nie ma), reprodukcje audytu i pre-check w `docs/audyt-pakietow-2026-10-04-testy/`.
  Uruchamianie: venv z Django 5.2 + `PYTHONPATH=docs/audyt-pakietow-2026-10-04-testy DJANGO_SECRET_KEY=x python -m django test <moduł> --settings=audit_settings`.
- Backup sprzed U1–U3: `kelnerzy:/root/fc-backup-u1u3-202610041446/`. Dane produkcyjne: 3 menu i 26/29 przepisów niekompletne (dane testowe/niedokończone).

## Zasady każdego wdrożenia — tracking Google obowiązkowy

Wymóg użytkownika z 2026-10-04: zachować wszystkie istniejące kody Google.
Przed deployem porównaj HTML/tagi na produkcji; po deployem sprawdź rzeczywisty
HTML i Consent Mode. FoodCost: `G-6DYFBNNH6X`, oba include analytics, context
processor i GA_MEASUREMENT_ID. Kontrola `/`, `/register/`, `/regulamin/` jest
obowiązkowa; brak tagu/zgody blokuje zakończenie wdrożenia. Pełna procedura:
`docs/WDROZENIA.md`. Nie wystarczy sprawdzenie źródła szablonu.

## 2026-10-04: landing pakietu WDROŻONY

Użytkownik zaakceptował podgląd i autoryzował deploy po naprawach backendu U1–U3.
Przesłano wyłącznie landing/base/CSS z `docs/landing-2026-10-04/deploy/`;
produkcyjny base zachowuje GA i nie zawiera niewdrożonych Ofert.
Backup ze strukturą ścieżek i oboma analytics include:
`kelnerzy:/root/fc-backup-landing-20261004-1508/`.
`docker compose up -d --build web`, collectstatic, Django check: OK.
Kontrola HTTP i Chromium: nowy hero, oba kalkulatory, wyniki 477,60/10,50,
zmiana ceny, klawiatura, 375/1280 px, mail `gastro_2026_10` otwiera danie.
`/`, `/register/`, `/regulamin/`: 200, GA4 `G-6DYFBNNH6X` i Consent Mode.
Baner/zgoda granted po akceptacji/pamięć wyboru: PASS. W przeglądarkowym teście
ruch do Google blokowano, nie potwierdzano raportu GA Realtime.
Raport: `docs/landing-2026-10-04/RAPORT.md`, dowody `live-results.json`.

## 2026-10-04: U1–U3 WDROŻONE na fc.sudomie.pl (14:50)

Backup: `kelnerzy:/root/fc-backup-u1u3-202610041446/` (9 plików sprzed zmiany). Wysłano 9 plików z listy poniżej, `docker compose up -d --build web`.
Gotcha: kod jest w obrazie, nie w wolumenie — samo `docker compose restart web` NIE ładuje nowych plików (pierwsza próba nic nie zmieniła; stary kod dalej działał).
Weryfikacja: / i /login/ 200, logi bez błędów, `makemigrations --check` czysto, 34/34 składników z ceną, przepisy kompletne 3/29, wszystkie 3 menu „niepełne” (FC% = brak) — dane testowe/niedokończone.
Rollback: skopiować pliki z backupu do `/opt/fc-sudomie-pl/` i `docker compose up -d --build web`. Landing wdraża agent frontendowy.

## 2026-10-04: przygotowanie wdrożenia U1–U3 (wykonane powyżej)

Pre-check produkcji (tylko odczyt, `docs/audyt-pakietow-2026-10-04-testy/prod_precheck_readonly.py`):
34 aktualne ceny, **0** w niezgodnej jednostce; **0** duplikatów `is_current`; **0** składników przepisów w niezgodnej jednostce;
3 menu — **żadne nie zmieni się na „niepełne”**; przepisy: 26 z 29 będą „niepełne” (brak składników/cen — FC% przepisu zniknie, to dane testowe/niedokończone).
Bez migracji. Plik lokalny = produkcja poza zmianami U1–U3 (zweryfikowane diffem).

Pliki do wysłania do `/opt/fc-sudomie-pl/` (tylko te; NIE `apps/offers/*`, Oferty nie są na produkcji):
`apps/ingredients/models.py`, `apps/ingredients/views.py`, `apps/ingredients/invoice_views.py`,
`apps/recipes/models.py`, `apps/recipes/forms.py`, `apps/recipes/export_views.py`,
`templates/recipes/menu_detail.html`, `templates/recipes/recipe_detail.html`, `templates/recipes/recipe_list.html`
(opcjonalnie `apps/recipes/tests.py`). Landing osobno z `docs/landing-2026-10-04/deploy/`.
Kolejność: backup (`/root/fc-backup-<data>/`) → scp → `docker compose restart web` → sprawdzić /recipes/menu/ i cenę składnika → landing.
Rollback: przywrócić pliki z backupu i zrestartować `web`.

## 2026-10-04: audyt pakietów — raport gotowy, bez zmian w kodzie

Raport: `docs/audyt-pakietow-2026-10-04.md`; testy/reprodukcje: `docs/audyt-pakietow-2026-10-04-testy/`
(uruchomienie w raporcie, sekcja 7). Modele Menu/Ceny/Faktury lokalnie = produkcja (sha256), Oferty i nowy landing tylko lokalnie.
Wniosek: kalkulator kosztu pakietu działa (scenariusz 6→7,50 zł/os., +120 zł/80 os. potwierdzony); kontroli marży imprezy NIE ma.
**NAPRAWIONE lokalnie (niewdrożone): U1–U3** (`apps/recipes/tests.py`, `is_cost_complete`; bez migracji). Poniżej stan sprzed naprawy. Przed wdrożeniem landingu było: U1+U2 (składnik bez ceny / puste menu = „kompletny”, FC 0% zielony) i U3 (niezgodne jednostki liczone 1:1),
albo zmiana tekstu kroku 3 landingu („ostrzeżenie” działa tylko dla dania bez żadnego składnika).
Gotcha: `SupplierPrice.save()` nieatomowy — na PostgreSQL do 8 „aktualnych” cen naraz; przed constraintem sprawdzić duplikaty na produkcji.
Nie zweryfikowano: dane produkcyjne (duplikaty cen, niezgodne jednostki), atomowość przy błędzie DB, OCR (nieuruchamiane).

## 2026-10-04: przygotowanie landingu — historia (wdrożony powyżej)

Przygotowano nowy landing z pakietem na osobę (domyślnie 199/80/30/10),
utraconą marżą 477,60 zł, zakładką dotychczasowego kalkulatora dania,
3 krokami, CTA, FAQ i meta. `utm_campaign=gastro_2026_10` otwiera danie
i dotychczasowy nagłówek, zgodnie z obietnicą maila. Kalkulacje wyłącznie
w przeglądarce, brak nowych zależności; app.css?v=20261004.

Node, render Django, Chromium 320/375/768/1280, klawiatura, noscript,
walidacja, brak requestów i routing kampanii: PASS. Lighthouse podglądu:
97 performance / 100 accessibility / 96 best practices / 100 SEO.
Zrzuty i szczegółowy raport: `docs/landing-2026-10-04/RAPORT.md`.
Nie przetestowano rzeczywistego czytnika ekranu, tylko aria-live i zmiany DOM.

Gotcha: lokalny base ma link do niewdrożonych Ofert. Do wdrożenia po
akceptacji użyć trzech plików `docs/landing-2026-10-04/deploy/`; base tam
pochodzi z produkcji i ma wyłącznie podbitą wersję CSS. Zachowano lokalny
link Oferty w głównym base. Przed deploy ponownie porównać produkcję.
CSS naprawia `#cc-bar[hidden]` (Bootstrap d-flex !important blokował
ukrywanie banera). Treść i logika zgody pozostały bez zmian.

Content-gapy: nie znamy rzeczywistych strat ani trendu cen; nie ma zgody
na nazwę hotelu/opinii. 10% i 477,60 zł to przykład, bez social proof.
Brak podziału kampanii na wejścia/rejestracje/aktywację — diagnoza lejka
pozostaje do wykonania. W tym etapie produkcja była niezmieniona; landing wdrożono później (sekcja powyżej).

## 2026-10-04: moduł ofert — przygotowany lokalnie, niewdrożony

Użytkownik wybrał moduł w fc.sudomie.pl zamiast osobnej aplikacji grupy.
Nowa `apps.offers`, adresy `/offers/`, pozycja Oferty w sidebarze i wejście
z dashboardu. Wspólne konta/organizacje FC; rola Podgląd bez prawa zapisu.

- Tworzenie i edycja ofert: dane lokalu i klienta, termin, liczba osób,
  ważność, status, procent wpłaty, warunki dla klienta, notatki wewnętrzne.
- Dowolne pozycje: wyżywienie z Menu FC lub ręczne, noclegi, usługi.
  Noclegi: ilość = pokoje × noce, cena = cena pokoju za noc.
- Menu: snapshot treści dań i kosztu przy pierwszym wyborze. Ręczne
  odświeżenie checkboxem nie zmienia wpisanej ceny sprzedaży.
  Brak ceny pozycji pobiera cenę z FC; jawne 0 pozostaje zerem.
- Kalkulacja wewnętrzna: sprzedaż/koszt gastronomii i FC% wyłącznie
  przy pełnych danych (puste menu i brak ceny składnika = niepełne).
- Dokument dla klienta `/offers/<id>/print/`, chroniony logowaniem,
  bez kosztów/notatek wewnętrznych; PDF przez okno drukowania.
  Nie ma publicznego linku ani automatycznej wysyłki maila.
- Snapshoty kosztów pozostają przy edycji; numer z roku i ID unikalny,
  revision + blokada wiersza chronią przed nadpisaniem równoległych edycji.
- Migracja `offers.0001_initial` do wykonania przy wdrożeniu. Stare dane
  z GoDaddy/grupy NIE zostały przeniesione ani zmienione.

Walidacja: 8 testów na Django 5.2.14 i izolowanej SQLite: zapis, obliczenia,
menu obcego lokalu, obce oferty, snapshot/refresh, konflikt revision,
Podgląd, wydruk bez danych wewnętrznych, ręczne pozycje, noclegi/usługi,
zerowa cena, niepełne menu, daty i procenty. Check bez błędów,
makemigrations --check bez rozbieżności. Nie wykonano testu przeglądarki
ani testu współbieżności na PostgreSQL. Brak wdrożenia produkcyjnego.

Następne: backup kodu/bazy na kelnerzy, przesłanie WYŁĄCZNIE nowych
plików offers oraz zmian config/urls.py, config/settings.py,
templates/base.html i templates/core/dashboard.html, migracja i rebuild.
Przed wdrożeniem porównać zmieniane pliki z produkcją (repo ma wcześniejsze
niezatwierdzone zmiany). Nie przesyłać całego lokalnego repo w ciemno.

## 🟢 2026-10-04: foodcost.sudomie.pl wygaszony → 301 na fc.sudomie.pl

- Cloudflare: rekord `foodcost` przełączony na Proxied; Redirect Rule
  „foodcost -> fc (wygaszenie 2026-10-04)”: `(http.host eq "foodcost.sudomie.pl")`
  → `concat("https://fc.sudomie.pl", "/")`, 301, bez query stringa. Cofnięcie = wyłącz regułę.
- Zrzut MySQL: `legacy-foodcost/db-dump/foodcost_db_202610040331.sql.gz`
  (+ kopia `godaddy:~/backups/`). Baza była prawie pusta (po 1 wierszu).
- Aplikacja na GoDaddy (`~/foodcost`, cPanel) NIE usunięta — do usunięcia ~2026-11-04.
- `oferty_grupowe` (grupy.sudomie.pl) miało integrację z API foodcost:
  `FOODCOST_API_URL=` wyczyszczone (backup `godaddy:~/backups/oferty_grupowe.env.20261004`),
  kod pokazuje „Brak konfiguracji” zamiast 500.
- Do zrobienia: monitor foodcost w `uptime.sudomie.pl` usunąć / przepiąć na fc.

## 🟢 Stan na 2026-10-04: GA4 włączony (`G-6DYFBNNH6X`)

- Flaga: `GA_MEASUREMENT_ID` w `.env` na `kelnerzy` (puste = brak tagu). Kod:
  `apps/core/context_processors.py`, `templates/_analytics_head.html`,
  `templates/_analytics_banner.html`, include w `base.html`.
- Consent Mode v2: default `denied` (pingi bez cookies → modelowany ruch z UE),
  „Akceptuję” w banerze → `analytics_storage: granted`, wybór w `localStorage['cc']`.
- Link w banerze → `sudomie.pl/polityka-prywatnosci.html` (GA4 tam już opisany).
- Kampanie mailowe: linki z `?utm_campaign=...` — widać w GA (Pozyskanie) i w
  `docker compose logs nginx` (logi czyszczone przy redeployu).
- Backup przed zmianą: `kelnerzy:/root/fc-backup-202610041023/`.

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

## Aktualizacja 2026-09-21: odświeżenie interfejsu (lokalnie)

Zmienione: `static/css/app.css`, wspólny `base.html`, landing, dashboard
oraz dostępność wyszukiwania i akcji na listach składników/przepisów.
Jasna nawigacja, czytelniejsze formularze i tabele, prostszy publiczny
kalkulator z widocznym logowaniem, walidacją ceny i polskim formatem PLN.
Mobilny sidebar używa Bootstrap offcanvas zamiast własnego przełączania klasy.

Weryfikacja: Django check i Playwright na lokalnych danych demo, widoki
390/768/1440 px, kalkulator, logowanie, FAQ, menu mobilne i fokus.
Podgląd: `127.0.0.1:8766`, tymczasowe środowisko `/tmp/fc-design-venv`,
settings `/tmp/fc_design_settings.py`, baza `/tmp/fc-design-preview.sqlite3`.
Lokalne migracje wciąż nie odtwarzają aktualnych modeli (m.in.
`manual_cost_override`); wyłącznie testowa baza powstała przez syncdb.
Nie zmieniano konfiguracji ani danych produkcji. Zmiany nie są wdrożone.

### Wdrożenie 2026-09-21
Odświeżenie interfejsu jest już na https://fc.sudomie.pl. Przesłano tylko
sześć plików szablonów/CSS, przebudowano i odtworzono usługę web.
CSS ma parametr `v=20260921`. Django check bez błędów; publiczny test
Chromium potwierdził HTTP 200, nowe HTML/CSS, obliczenia kalkulatora,
widoki 390/1440 px i wejście do logowania, bez błędów JS.
Backup: `/opt/fc-backups/ui-before-20260921.tar.gz` na kelnerzy,
obraz poprzedniej wersji: `fc-sudomie-pl-web:before-ui-20260921`.

Użytkownik zgłosił problemy z OCR i chce wybrać nowszy model. Obecnie
`ocr_service.py` nadal używa gpt-4o z limitem 2000 tokenów. Rozpoznane
ryzyka niezależne od modelu: niejednoznaczny prompt ceny/opakowania,
brak wymuszonego schematu JSON, podwójne dzielenie ceny opakowania
oraz zdublowane pola desktop/mobile w formularzu potwierdzenia.
Zmiana OCR nie została jeszcze wdrożona; trwa ustalenie objawu problemu.

### OCR GPT-4.1 mini: wdrożone 2026-09-21

- Domyślny model `gpt-4.1-mini`, konfigurowalny przez `OPENAI_OCR_MODEL`.
  Jeden model dla JPG/PNG/WEBP oraz PDF renderowanych przez PyMuPDF.
- Wymuszony JSON Schema, limit odpowiedzi 12000 tokenów, jawna obsługa
  ucięcia/odmowy, timeout 45 s bez automatycznych ponowień API.
- Prompt rozdziela ilość zakupioną i zawartość jednego opakowania, wymaga
  dosłownej nazwy, ceny jednostkowej po rabacie i podstawy netto/brutto.
- Formularz potwierdzenia zachowuje cenę opakowania: 20 zł / 5 kg daje
  4 zł/kg, bez ponownego dzielenia. Jedna wersja pól dla desktop/mobile
  zapobiega nadpisywaniu korekt przez ukryte pola. Ilość zakupiona widoczna.
- Nieczytelne krytyczne wartości zatrzymują import zamiast zamiany na zero
  lub cichego pominięcia pozycji. PDF >10 stron zgłasza potrzebę podziału.
- Testy: 9 testów Django w `apps/ingredients/tests/test_ocr.py`, przeglądarka
  390/1440 px (edycja ceny, odznaczanie pozycji), dwa prawdziwe wywołania
  API na syntetycznej fakturze PDF i PNG. Nazwa, 3 worki po 5 kg, cena
  20 zł netto za worek zostały odczytane poprawnie w obu formatach.
- Produkcyjny `manage.py check` bez błędów; potwierdzony aktywny model.
  Backup `/opt/fc-backups/ocr-before-20260921.tar.gz`, poprzedni obraz
  `fc-sudomie-pl-web:before-ocr-20260921` na kelnerzy.
- Do sprawdzenia: realne faktury, które wcześniej miały błędne nazwy/ilości.
  Nie ma jeszcze dowodu poprawy dokładności na dokumentach klienta.

## 2026-09-21: 30 dni / 100 stron OCR, wdrożone

- Organizacje Free mają dostęp do OCR. Próba zaczyna się od pierwszego
  UDANEGO odczytu (nie rejestracji/wyboru pliku); 30*24 h, 100 stron
  łącznie dla całej organizacji. Zdjęcie = 1 strona; PDF = liczba stron.
- Zachowany nieograniczony dostęp istniejących organizacji Pro.
- Organization: `ocr_trial_started_at`, `ocr_trial_pages_used`,
  `ocr_access_requested_at`. Migracja accounts.0002 dodaje też OCRRead.
- Rezerwacja stron w krótkiej transakcji `select_for_update` blokuje
  równoległe przekroczenie limitu. Nieudany odczyt zwalnia rezerwację.
  UUID formularza chroni przed podwójnym wysłaniem; rezerwacje po awarii
  wygasają po 5 min. Zakończenie próby nie blokuje zapisu już odczytanych cen.
- `/ingredients/invoice/estimate/`: POST sprawdza plik i liczy strony bez
  API/startu próby; formularz pokazuje zużycie przed zatwierdzeniem.
  Rozmiar ujednolicony do 10 MB (zgodny z nginx), max 10 stron dokumentu.
- Po próbie OCR jest zatrzymany; dane i ręczne funkcje zostają. Użytkownik
  może zgłosić zainteresowanie dalszym dostępem (POST request-access).
  Zgłoszenia w adminie Organizacje: data + e-mail właściciela.
- User ma spółkę bez konta bankowego: na razie BRAK płatności, kart,
  automatycznych opłat i aktywnej sprzedaży pakietów. UI mówi wprost,
  że pakiety są w przygotowaniu; zainteresowanie nie jest zamówieniem.
- Landing/rejestracja/dashboard/sidebar prowadzą do próby. Open Graph
  zawiera tytuł i opis do udostępniania na Facebooku (bez grafiki og:image).
- Testy: 26/26 na izolowanej bazie PostgreSQL test_fc_trial_20260921,
  w tym 2 równoległe odczyty ostatnich 10 stron; baza testowa usunięta
  przez Django po testach. Lokalny Chromium: rejestracja→lokal→OCR,
  podgląd PDF 3 str., błąd bez naliczenia, 390/1440 px.
- Produkcja: migracja wykonana, Django check czysty, sprawdzono odczyt
  ekranu OCR i liczenie PDF dla istniejącego Free i Pro bez zmian danych.
- Backup na kelnerzy: `/opt/fc-backups/database-before-trial-20260921.dump`,
  `/opt/fc-backups/trial-code-before-20260921.tar.gz`, obraz
  `fc-sudomie-pl-web:before-trial-20260921`.
- Lokalnie odzyskano brakującą recipes.0002 z produkcji. Nieedytowalne
  katalogi migracji accounts/recipes zachowano jako `.migrations-backup-20260921`
  obok nowych kopii z prawami użytkownika; git/docker ignorują te backupy.
  `makemigrations --check` nie wykrywa rozbieżności. Sudo wymaga hasła,
  więc nie udało się naprawić właściciela starych katalogów.

### Aktualny limit próby: 30 stron / 30 dni (2026-09-21)
Na polecenie użytkownika limit obniżono ze 100 do 30 stron. Użytkownik
potwierdził: 30 stron łącznie przez 30 dni, BEZ limitu dziennego.
`Organization.OCR_TRIAL_PAGES = 30`, wykorzystane wcześniej strony nadal
liczą się do limitu. Nie resetowano dat ani liczników. Pro bez zmian.
Zaktualizowano landing, Open Graph, rejestrację, dashboard i ekran OCR.
26/26 testów na osobnej bazie PostgreSQL, Django check czysty, aktywne
stałe 30/30 potwierdzone w produkcji. Bez nowej migracji bazy.
Backup: `/opt/fc-backups/trial100-before-30-20260921.tar.gz`, obraz
`fc-sudomie-pl-web:before-trial30-20260921`.

## 2026-10-04: flagi prawne (przegląd marki)

- ✅ WDROŻONE: Consent Mode v2 na sudomie.pl — jeden blok gtag (AW-946213709 + G-6DYFBNNH6X,
  ten drugi był dodany ręcznie na prod 28.09 i nie było go lokalnie), default denied,
  `ccAccept()` w `home.js` robi `consent update`. Baner bez „Google Fonts”. Backup: `godaddy:~/backups/sudomie-20261004/`.
- ⏳ SZKIC: `sudomie.pl/docs/prawne/szkic/polityka-prywatnosci.html` — wspólna polityka sudomie.pl + FoodCost
  (czat→OpenAI, FoodCost, Cloudflare/OpenAI/jsDelivr, fonty lokalne). Czeka na dane spółki
  (`{{NAZWA_SPOLKI}}`, `{{ADRES_SIEDZIBY}}`, `{{KRS}}`, `{{NIP}}`, `{{DATA_WEJSCIA}}`, `{{LOKALIZACJA_GODADDY}}`).
- Regulamin FoodCost: `fc.sudomie.pl/templates/core/regulamin.html` — te same placeholdery.
  ⚠️ Django renderuje `{{X}}` jako PUSTY string — przed deployem `grep -rn '{{[A-Z_]*}}'` musi zwrócić 0.
- Po publikacji: 4 istniejące lokale w fc zaakceptowały nieistniejący regulamin → wysłać im regulamin e-mailem.
- ✅ 2026-10-04 13:10 WDROŻONE: polityka (sudomie.pl/polityka-prywatnosci.html, dane z KRS 0001265889),
  regulamin fc.sudomie.pl/regulamin/, link w rejestracji, dane spółki (art. 206 KSH) w stopkach obu stron.
  Backupy: godaddy:~/backups/sudomie-20261004/, kelnerzy:/root/fc-backup-legal-20261004/.
  Otwarte: e-mail z regulaminem do istniejących lokali; retencja LoginEvent (dziś bez limitu, polityka mówi to wprost).

## Podlinkowanie sudomie — 2026-10-28

Przygotowano lokalnie blok Narzędzia sudomie w templates/core/landing.html i styl w static/css/app.css. Źródło linków: ../sudomie.pl/data/produkty.json. Generator 0/8 nieaktualnych; podgląd szablonu Django + Chromium 390/1440 px: stopka czytelna.

Publikacja wraz z najbliższym wydaniem, [474](https://projekty.sudomie.pl/work_packages/474). Zadanie źródłowe: [473](https://projekty.sudomie.pl/work_packages/473).
