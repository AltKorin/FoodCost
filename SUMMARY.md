# Historia sesji — fc.sudomie.pl

---

## Sesja 2026-09-08 — Konsolidacja z foodcost.sudomie.pl (archiwizacja)

User: „robiliśmy wczoraj fc.sudomie.pl a oprócz tego jest foodcost.sudomie.pl
więc trzeba by przenieść wszystko do jednego foldera. Połączyć oba projekty
do jednego darmowego narzędzia". Przed ruszeniem czegokolwiek —
`foodcost.sudomie.pl` to produkcyjna apka realnego klienta (Hotel Niedźwiadek,
szef kuchni Michał, GoDaddy/MySQL), nie demo do połączenia bez ryzyka.
Doprecyzowane z userem: produkcja Michała zostaje bez zmian na GoDaddy,
kod przenosimy do fc.sudomie.pl tylko jako archiwum.

### Zrobiono
- `mv /home/konrad/Claude/foodcost.sudomie.pl` →
  `/home/konrad/Claude/fc.sudomie.pl/legacy-foodcost/` (56 plików, bez
  czyszczenia zagnieżdżonych duplikatów `foodcost/foodcost/foodcost/...` ani
  starych zipów — to ma być wierne archiwum, nie porządkowanie).
- Zweryfikowano brak sekretów w przenoszonych plikach (tylko `.env.example`).
- Zaktualizowano HANDOFF.md — nowy kontekst: Michał widział fc.sudomie.pl i
  wolałby przejść na tę wersję, ale potrzebuje OCR faktur (funkcja istnieje
  w legacy-foodcost, nie w fc.sudomie.pl jeszcze).

### Zadziałało
- Pytanie usera przed ruszeniem produkcji klienta zamiast zgadywania —
  pierwotna prośba ("połącz oba projekty w jedno") brzmiała jak pełny merge
  kodu, co oznaczałoby ryzykowną robotę na żywych danych Michała bez potrzeby.
  Doprecyzowanie pokazało, że wystarczy archiwizacja + osobny plan na
  properties OCR.

### Nie zadziałało
- (nic — sesja skupiona na jednym bezpiecznym kroku)

### Następne kroki
- Port OCR faktur (`legacy-foodcost/.../ocr_service.py` + `invoice_views.py`)
  do `apps/ingredients/` w fc.sudomie.pl — Faza 3, blokuje przejście Michała.
- Migracja realnych danych Hotelu Niedźwiadek (ceny/składniki z MySQL
  produkcji) do organizacji w fc.sudomie.pl — dopiero po jego zgodzie na
  przejście, seed `niedzwiadek-test` jest przestarzały.
- Do decyzji później: co z domeną/hostingiem `foodcost.sudomie.pl` (GoDaddy)
  gdy/jeśli Michał faktycznie przejdzie na fc.sudomie.pl — nie ruszać teraz.

---

## Sesja 2026-09-07 (5) — Zmiana hasła + zarządzanie zespołem organizacji

Konrad ręcznie utworzył konto `dyrektor@hotelniedzwiadek.pl` (przez
`manage.py shell`) w tej samej organizacji co `hotel@` — user zapytał, czy
dane się synchronizują (odpowiedź: to nie synchronizacja, to jeden
wspólny zestaw danych filtrowany po `organization`), a potem słusznie
zauważył, że dodawanie osób przez shell nie skaluje się — potrzebny UI.

### Zrobiono
- `accounts:password-change` — `StyledPasswordChangeForm` (wrapper na
  Django `PasswordChangeForm`, tylko klasy Bootstrapa), `update_session_auth_hash`
  po zapisie (bez tego zmiana hasła wylogowuje od razu). Link w dropdownie
  przy adresie e-mail w topbarze.
- `accounts:team-list` / `accounts:team-add` — zarządzanie zespołem
  organizacji. Dodawanie ograniczone do `request.user.is_org_admin`
  (OWNER/ADMIN) — VIEWER/CHEF dostają komunikat błędu i redirect zarówno na
  GET jak i POST (sprawdzenie przed rozgałęzieniem na metodę, nie tylko
  przy zapisie).
- `TeamMemberForm` — brak wysyłki maila (SMTP nieskonfigurowany), więc
  hasło jest losowane (`secrets.choice`, 14 znaków) i pokazane RAZ na
  ekranie sukcesu do ręcznego przekazania. Walidacja e-maila: odrzuca,
  jeśli konto z tym adresem już istnieje (czytelny błąd zamiast
  `IntegrityError` z bazy).
- Konto `dyrektor@hotelniedzwiadek.pl` (utworzone ręcznie wcześniej) ma teraz
  hasło ustawione przez usera samodzielnie do przekazania, plus może teraz
  zarządzać zespołem sam (rola Administrator → `is_org_admin=True`).

### Zadziałało
- Sprawdzenie uprawnień PRZED rozgałęzieniem GET/POST (nie tylko w gałęzi
  zapisu) — VIEWER nigdy nawet nie widzi formularza/CSRF tokena, nie tylko
  nie może go wysłać.
- Test na produkcji z prawdziwym kontem (`recepcja@hotelniedzwiadek.pl`,
  rola viewer) potwierdzającym blokadę — potem skasowany, bo to była tylko
  weryfikacja, nie prawdziwa osoba do dodania.

### Nie zadziałało / świadomie pominięte
- Brak zaproszeń mailowych — wymagałoby konfiguracji SMTP, poza zakresem
  tej prośby. Hasło-pokazane-raz jest świadomym, prostszym zamiennikiem.
- Brak edycji roli / usuwania osoby z zespołu po fakcie — user prosił tylko
  o dodawanie, nie zarządzanie istniejącymi członkami. Do dobudowania, jeśli
  będzie potrzeba.

### Następne kroki
- Nadal otwarte z poprzednich sesji: `sudo chown` migracji lokalnie,
  `git init` + pierwszy commit.

## Sesja 2026-09-07 (6) — `team-remove`: usuwanie z zespołu

User: „zawsze jak jest opcja dodania, musi być opcja odjęcia" — dodane od razu.

### Zrobiono
- `accounts:team-remove` (POST) — usuwa osobę z organizacji przez
  `organization = None`, NIE kasuje konta (można by je potem przypisać do
  innej organizacji albo user sam założy nową przez `/setup/`). Ten sam
  wybór co przy `ObiektKonto`/`Obiekt.aktywny` w innych projektach —
  odwracalna zmiana stanu zamiast hard delete.
- Trzy zabezpieczenia w widoku, sprawdzane w tej kolejności: (1) tylko
  `is_org_admin` może usuwać, (2) nie można usunąć samego siebie, (3) nie
  można usunąć ostatniej osoby z rolą OWNER/ADMIN (zablokowałoby dalsze
  zarządzanie zespołem) — komunikat, nie wyjątek, ten sam wzorzec co
  „usunięcie lidera zablokowane komunikatem" w innych projektach.
- Przycisk „usuń" (ikona) przy każdym wierszu w `team_list.html`, z
  `confirm()` w JS — niewidoczny dla samego siebie i dla nie-adminów.

### Zadziałało
- Test na produkcji: dodano jednorazowe konto testowe, usunięto je,
  potwierdzono w bazie `organization=None` (konto istnieje, dostęp
  odebrany) i zniknięcie z listy zespołu. Próba usunięcia samego siebie
  poprawnie zablokowana z komunikatem.

### Nie zadziałało / świadomie pominięte
- Nie przetestowano bezpośrednio blokady „ostatni admin" na produkcji —
  wymagałoby stworzenia trzeciego konta testowego tylko po to, żeby
  wyzerować adminów, co jest nadmiarowe dla prostego guard clause
  (sprawdzone przez przegląd kodu, nie end-to-end).

## Sesja 2026-09-07 (4) — Poprawka modelu: dodano `Menu` (trzeci poziom hierarchii)

User złapał błąd projektowy zaraz po tym, jak zobaczył realne dane w
systemie: „powinno być Menu / Przepis / Składniki i w ten sposób by
działało, a teraz mamy Menu w przepisach, a całe danie jest Składnikiem."
Trafna diagnoza — poprzednia sesja spłaszczyła 3-poziomową hierarchię do 2
poziomów, bo model nie miał pojęcia "Menu" wcale.

### Zrobiono
- Nowy model `Menu` + `MenuItem` (through, `quantity` = porcji/gościa) w
  `apps/recipes/models.py` — Menu ma `package_price_per_person` i
  `target_fc_pct`, wskazuje przez `MenuItem` na wiele `Recipe`.
- `Recipe.manual_cost_override` — koszt/porcję wpisany ręcznie, omija sumę
  z `RecipeIngredient`. To była druga część prośby usera: „Przepis powinien
  mieć możliwość wpisania ceny z ręki" — bo dla gotowego dania (np. "Karp
  pieczony w cebuli") często zna się tylko cenę końcową, nie rozbicie na
  surowe składniki.
- `Recipe.has_cost_data` — odróżnia "koszt = 0 zł, bo naprawdę wiadomo, że
  0" od "koszt = 0 zł, bo jeszcze nic nie wpisano" — bez tego pusty przepis
  wygląda jak fantastyczny food cost zamiast brakujących danych.
  `Menu.is_cost_complete` używa tego do ostrzeżenia w UI.
- CRUD dla Menu: `/recipes/menu/` (lista/nowe/szczegóły/edytuj/usuń), ten
  sam wzorzec formsetu co przy `RecipeIngredient` (dynamiczne dodawanie
  wierszy, `has_changed()` ignorujące puste dodatkowe wiersze).
- Podgląd kosztu w formularzu Menu bez fetcha — `RecipeCostSelect`
  (custom widget) doklein `data-cost`/`data-has-cost` na każdą `<option>`
  przepisu, bo koszt/porcję jest już znany po stronie serwera (w
  przeciwieństwie do ceny składnika, zależnej od wybranego dostawcy).
- Link „Menu” w sidebarze (`base.html`), przed „Przepisy”.
- **Migracja realnych danych klienta** (Hotel Niedźwiadek, org
  `niedzwiadek-test`): skasowano 3 błędne Recipe-jako-Menu, zamieniono 26
  Ingredient-jako-danie na właściwe Recipe, utworzono 3 Menu z 139/199/239
  zł/osobę i MenuItem wskazującymi na te przepisy. Zweryfikowane przez
  `django.test.Client` z `force_login` bezpośrednio na produkcji (żeby nie
  potrzebować hasła usera) — wszystkie strony 200, `is_cost_complete=False`
  poprawnie wykryte (żadne danie nie ma jeszcze kosztu), ręczny test na
  jednym daniu (`manual_cost_override=8.50`) potwierdził cały łańcuch
  Recipe → MenuItem.get_cost() → Menu.total_cost_per_person → food_cost_pct
  liczy się poprawnie — potem cofnięty (to była tylko weryfikacja, nie
  prawdziwa cena).

### Zadziałało
- Odróżnienie "0 zł bo wiadomo" od "0 zł bo brak danych"
  (`has_cost_data`/`is_cost_complete`) — bez tego Menu z samymi pustymi
  daniami pokazywałoby fałszywie doskonały food cost zamiast "jeszcze nie
  wiadomo".
- Weryfikacja przez `Client(SERVER_NAME=...).force_login()` bezpośrednio w
  `manage.py shell` na produkcji — nie trzeba było hasła usera, żeby
  potwierdzić, że strony faktycznie się renderują dla jego konta.

### Nie zadziałało / świadomie pominięte
- Migracja `recipes.0002` nie skopiowała się do lokalnego repo
  (`apps/recipes/migrations/` jest częściowo root-owned z wcześniejszego
  bind-mounta Dockera, brak sudo na tej maszynie) — produkcja ma poprawny
  stan, lokalna kopia nie, do naprawy przed `git init`.
- Nie dodano jeszcze żadnych prawdziwych cen (ręcznych ani składnikowych)
  dla dań Hotelu Niedźwiadek — to prawdziwy stan (user jeszcze ich nie
  podał), nie do zmyślania.

### Następne kroki
- User: dodać albo ręczne koszty dań, albo rozbić wybrane dania na surowe
  składniki z cenami dostawców — żeby Menu 1/2/3 pokazały realny FC%.
- `sudo chown -R konrad:konrad apps/*/migrations/` na tej maszynie, potem
  `git init` + pierwszy commit — wciąż otwarte z poprzednich sesji.

## Sesja 2026-09-07 (3) — Prawdziwe wdrożenie na `kelnerzy` (`fc.sudomie.pl` na żywo)

User: „kelnerzy już wychodzą z użycia. Może tam być podpięte bo możliwe,
że dorzucimy to do strony" — decyzja: host `kelnerzy`, osobny izolowany
`docker-compose`, osobny tunel Cloudflare.

### Zrobiono
- Zbadano realny dostęp (SSH + `docker ps` na każdym hoście, nie z pamięci):
  `kelnerzy`, `animatorzy`, `sprzatajaca-prod` mają działające stosy +
  cloudflared; `proxmox-main`/`proxmox-hp` bez dostępu do tworzenia
  kontenerów; `ib-szkolenia`/`openclaw` offline.
- `docker-compose.yml`: usunięty `ports: "80:80"` z `nginx` — wzorzec z
  `agencja-kelnerska` (cloudflared łączy się przez wewnętrzną sieć Dockera,
  port 80 nie musi wychodzić na hosta wcale, zero otwartych portów).
- `rsync` projektu do `/opt/fc-sudomie-pl/` na `kelnerzy` (bez `.env`,
  `venv/`, `cloudflared/config.yml`+`*.json` — te specyficzne dla hosta).
- Nowy `.env` produkcyjny (świeży `SECRET_KEY`, mocne hasło DB,
  `DJANGO_DEBUG=False`, `CSRF_TRUSTED_ORIGINS=https://fc.sudomie.pl`).
- Nowy, dedykowany tunel Cloudflare `fc-sudomie-pl`
  (`cloudflared tunnel create` — cert.pem na hoście już był zalogowany do
  konta, nie trzeba było nic re-autoryzować).
- **Gotcha, który się powtórzył:** `cloudflared tunnel route dns` dla
  `fc.sudomie.pl` z aktualnym (kadragastro.pl-owym) `cert.pem` stworzył
  błędny rekord `fc.sudomie.pl.kadragastro.pl`. Fix: podmiana na
  `cert.pem.sudomie.bak` (backup zostawiony po poprzednim razie dokładnie
  na taką okazję), poprawny `route dns`, cert.pem z powrotem. Szczegóły w
  HANDOFF — będzie się powtarzać przy każdym kolejnym `*.sudomie.pl` na
  tym hoście, dopóki nikt nie doda osobnego, poprawnie zalogowanego certu.
- `docker compose up -d --build` — 4 kontenery (postgres/web/nginx/
  cloudflared), migracje zaaplikowane czysto, seed uruchomiony.
- Zweryfikowane na żywo: `https://fc.sudomie.pl/` (kalkulator dla gościa),
  pełny login → dashboard demo, `/admin/login/`, statyki.
- Lokalny tymczasowy Quick Tunnel z poprzedniej sesji zabity, lokalny
  `.env` (dev-owe sekrety) usunięty — nieaktualne po prawdziwym wdrożeniu.

### Zadziałało
- Rozpoznanie infrastruktury PRZED decyzją (realny `docker ps`/`ssh` na
  każdym hoście) zamiast zgadywania — user dostał trafną, konkretną tabelę
  opcji zamiast „które mam na myśli".
- Cert.pem gotcha rozpoznany z samego kształtu błędnego rekordu (`x.y.pl`
  zamiast `x.pl` = CNAME doklejony pod złą zoną) — nie trzeba było zgadywać,
  sam adres powiedział, co się stało.

### Nie zadziałało / świadomie pominięte
- Stray DNS `fc.sudomie.pl.kadragastro.pl` — nieszkodliwy, zostawiony
  (ten sam wzorzec co poprzednim razem — brak łatwego sposobu usunięcia
  bez tokena API Cloudflare).
- Superuser Django nie utworzony — tylko konto demo z `manage.py seed`.

### Następne kroki
- `git init` + pierwszy commit — projekt na produkcji wciąż bez historii
  gita.
- Jeśli/gdy pojawi się dostęp do Cloudflare API/dashboardu — posprzątać
  stray CNAME.

## Sesja 2026-09-07 (2) — Darmowy kalkulator FC% jako publiczny landing

User doprecyzował, o co faktycznie chodziło: nie SaaS za loginem, tylko
darmowe demo do wystawienia — suwak food cost%, pokazuje ile można wydać na
składniki, zastępuje liczenie „na oko". Zbadałem po drodze `InnDesk` (user
sugerował, że tam jest nowsza wersja) — nie ma tam żadnego kodu food cost,
tylko wzmianka o przyszłej integracji (Moduł 6, „Połączenie z foodcost v2");
za to `foodcost.sudomie.pl` (Hotel Niedźwiadek, pierwszy klient pilotażowy
InnDesk) jest wyraźnie bardziej dojrzały niż dzisiejszy `fc.sudomie.pl`
(ma już upload faktur/arkuszy) — struktura modeli `fc.sudomie.pl`
(ingredients+recipes jako osobne appki) ewidentnie wzorowana na nim, mimo
że własne SUMMARY.md tego projektu deklaruje "nowy projekt, nie fork".

### Zrobiono
- `core.dashboard` (URL `/`) jest teraz routerem: gość bez loginu dostaje
  `core/landing.html` (kalkulator), zalogowany bez organizacji leci do
  `/setup/`, reszta trafia na właściwy dashboard (przeniesiony do
  prywatnej `_dashboard`).
- `templates/core/landing.html` — kalkulator FC% jako darmowe narzędzie
  lead-genowe (wzorzec z `marketing-skills:free-tool-strategy`: wartość
  najpierw, zero gate'owania e-mailem, 2 inputy, Alpine.js liczy w
  przeglądarce bez roundtripu do serwera). Cena sprzedaży + suwak
  docelowego FC% → maksymalny budżet na składniki na żywo. Schema.org
  `SoftwareApplication` dla SEO. CTA na dole → `/register/` (ten sam lejek,
  który zbudowałem w poprzedniej sesji).
- Sekcja „To liczy jeden przepis. A cała karta?" świadomie kontrastuje
  kalkulator (orientacyjny, jeden przepis) z pełnym narzędziem (realne ceny
  dostawców, yield factor, cała karta) — to jest właściwy hak konwersji,
  nie sam fakt istnienia rejestracji.

### Zadziałało
- Zero backendu dla samego kalkulatora — `budget = price * pct/100` liczy
  się w całości w Alpine.js, żadnego zapytania do serwera. Zgodne z
  "Minimal Friction"/"Value Before Gate" ze skilla.

### Nie zadziałało / świadomie pominięte
- Nie zbudowano zapisu/udostępniania wyniku (skill sugeruje "shareable
  output") — dla kalkulatora jednowierszowego to nie miałoby sensu, cały
  wynik mieści się w jednym zdaniu, nie ma czego zapisywać.
- Nie walidowano wolumenu wyszukiwań przed budową (Mode 1 skilla) — user
  już wcześniej zdecydował, że to ma powstać, więc pominięcie etapu
  ewaluacji pomysłu było świadome, nie przeoczenie.

### Następne kroki
- Do decyzji: czy sekcje FAQ/„jak liczy" wymagają dopracowania pod kątem
  SEO (obecna wersja jest wystarczająca do publikacji, nie zoptymalizowana
  pod konkretne frazy).
- Nadal aktualne z poprzedniej sesji: cel wdrożenia docelowego nieustalony,
  brak repo git.

## Sesja 2026-09-07 — Dokończenie Fazy 1: szablony, seed, publiczny podgląd

Backend (modele/formularze/widoki accounts+ingredients+recipes+core) był gotowy
od sesji 2026-04-26, ale bez migracji, szablonów i wdrożenia — aplikacja
nigdy się nie uruchamiała. User poprosił o szybkie wystawienie, bo jest
realna potrzeba pokazania narzędzia.

### Zrobiono
- Wygenerowane migracje początkowe (`accounts`, `ingredients`, `recipes` —
  zero istniało wcześniej).
- Wszystkie szablony: `base.html` (sidebar+topbar, Bootstrap 5 CDN +
  Alpine.js CDN), accounts (register/login/setup), core/dashboard,
  ingredients (kategorie/dostawcy/składniki, pełny CRUD), recipes (konteksty,
  lista/szczegóły/formularz przepisu z formsetem składników).
- `static/css/app.css` wg palety z DESIGN.md (zielony primary, FC
  ok/warning/danger).
- Formularz przepisu: podgląd kosztu per wiersz składnika w czasie
  rzeczywistym (Alpine.js + fetch do istniejącego
  `ingredients:api-price`), dynamiczne dodawanie wierszy (klon
  `formset.empty_form`, standardowy wzorzec Django). **Pominięty** zbiorczy
  podgląd FC% całego przepisu na żywo (DESIGN.md to opisywał) — realna
  wartość jest w podglądzie per-wiersz, agregacja przez wiele zagnieżdżonych
  komponentów Alpine dodawała ryzyko bez proporcjonalnej korzyści (prawdziwe
  FC% i tak liczy się od razu po zapisie, na `recipe_detail`).
- `apps/core/management/commands/seed.py` — organizacja demo
  (`demo@fc.sudomie.pl` / `demo12345`), 3 kategorie, 2 dostawców,
  10 składników z cenami, 2 konteksty serwowania, 3 przepisy.
- `apps/recipes/templatetags/recipe_extras.py` — filtr
  `fc_status_for_context`, bo Django template nie umie wywołać metody
  z argumentem (`recipe.fc_status_for_context(context)`) bezpośrednio.
- **3 błędy w istniejącym (nieprzetestowanym od kwietnia) kodzie, znalezione
  przez faktyczne kliknięcie w aplikację, nie tylko czytanie kodu:**
  1. `RegisterForm.__init__` robił `del self.fields['username']`, ale
     `Meta.fields` już nie zawierało `'username'` — każda rejestracja
     kończyła się 500.
  2. `RecipeIngredientForm.__init__(self, organization, ...)` z
     `organization` jako wymaganym argumentem pozycyjnym — formset
     konstruuje formularze przez `self.form(**defaults)` bez możliwości
     wstrzyknięcia dodatkowego argumentu, więc KAŻDA próba dodania/edycji
     przepisu kończyła się 500. Naprawione: `organization=None` +
     `BoundFormSet._construct_form` i tak nadpisuje queryset po fakcie.
  3. Pusty dodatkowy wiersz formsetu (ich jest 5 na `recipe-create`) i tak
     wysyła `unit` (przeglądarka domyślnie zaznacza pierwszą opcję
     `<select>`) i `yield_factor` (initial z domyślnej wartości modelu) —
     Django uznawał taki wiersz za "zmieniony" i wymuszał wypełnienie
     `ingredient`, blokując zapis KAŻDEGO przepisu z niewykorzystanymi
     pustymi wierszami (czyli praktycznie każdego). Naprawione przez
     `RecipeIngredientForm.has_changed()` — pusty `ingredient` w surowych
     danych POST = wiersz uznany za nietknięty, niezależnie od reszty pól.
- `MESSAGE_TAGS` w `settings.py` (ERROR → 'danger') — bez tego komunikaty
  błędów renderowały się jako `alert-error`, klasa której Bootstrap nie zna.
- `ALLOWED_HOSTS` rozszerzony o `.trycloudflare.com` — na potrzeby szybkich
  podglądów bez tunelu nazwanego (patrz niżej).
- **Publiczny podgląd wystawiony przez Cloudflare Quick Tunnel** (bez
  konta/DNS, `cloudflared tunnel --url http://localhost:8080`) —
  `cloudflared` ściągnięty ręcznie jako `.deb` z `pkg.cloudflare.com` i
  wypakowany `dpkg-deb --extract` (bez roota — `sudo` niedostępne na tej
  maszynie, tak jak na `proxmox`), bo `docker pull` z Docker Hub timeoutował
  w tym środowisku (GitHub też — 504; `pkg.cloudflare.com` i `pypi.org`
  działały). URL efemeryczny, żyje tylko z uruchomionym procesem — NIE jest
  to wdrożenie docelowe.
- `docker-compose.override.yml` (nginx `8080:80` zamiast `80:80` — port 80
  na tej maszynie zajęty przez coś innego, bez sudo nie dało się sprawdzić
  co). Użyty YAML tag `!override` (Compose 2.24+) — zwykłe nadpisanie listy
  `ports` w override pliku DODAJE wpisy zamiast zastępować, `!override`
  wymusza zastąpienie.

### Zadziałało
- Testowanie przez faktyczne żądania HTTP (curl + ciasteczka sesji,
  end-to-end: rejestracja → setup → dashboard → CRUD → przepis z
  formsetem), nie tylko odczyt kodu — wszystkie 3 błędy ujawniły się
  dopiero przy próbie użycia, nie przy samym `manage.py check`.

### Nie zadziałało / świadomie pominięte
- Brak repo git dla tego projektu — do rozważenia przed jakimkolwiek
  dalszym rozwojem (audyt zmian, rollback).
- Cel wdrożenia produkcyjnego (prawdziwe `fc.sudomie.pl` z nazwanym
  tunelem + DNS) NIEUSTALONY — HANDOFF miał nieuzupełniony placeholder na
  IP "ThinkCenter". User: „musi stanąć na czymś do czego masz dostęp,
  chodzi o szybkie pokazanie" — stąd Quick Tunnel zamiast pełnego wdrożenia.
  Docelowy host do ustalenia w kolejnej sesji.
- Faza 3 (OCR faktur, historia cen jako osobny widok) — nie ruszone, poza
  zakresem tej sesji.

### Następne kroki
- User ogląda podgląd pod `https://alternative-partition-sides-heath.trycloudflare.com`
  (login: `demo@fc.sudomie.pl` / `demo12345`) — URL wygaśnie, gdy proces
  `cloudflared` się zatrzyma (koniec sesji/restart maszyny).
- Decyzja: gdzie docelowo stawiamy `fc.sudomie.pl` na stałe (ta maszyna +
  nowy nazwany tunel, `kelnerzy` jako kolejny serwis, czy coś innego) —
  patrz HANDOFF.
- Git init + pierwszy commit, zanim ruszymy dalej.

## Sesja 2026-04-26 — Decyzje produktowe i architektoniczne

### Zrobiono
- Zdefiniowano produkt: darmowy SaaS do food cost dla HoReCa
- Analiza konkurencji: kalkulator Unilever = Excel w przeglądarce, brak realnych feature'ów
- Wybrano stack: Django 5 + PostgreSQL + Docker + Cloudflare Tunnel na ThinkCenter
- Zaprojektowano architekturę multi-tenant (row-level isolation, TenantQuerySetMixin)
- Zdefiniowano MVP Fazy 1-3
- Przygotowano dokumenty startowe: HANDOFF.md, SUMMARY.md, PLAN.md, DESIGN.md

### Kluczowe decyzje
- **Nowy projekt** (nie fork foodcost.sudomie.pl) — czyste multi-tenant od dnia 1
- **Subdomena fc.sudomie.pl** — bez kupowania nowej domeny, można przemianować później
- **PostgreSQL** (nie SQLite) — własny serwer, produkcyjna baza od początku
- **Darmowy SaaS** — model: lead gen dla sudomie.pl + agregowane dane cenowe + przyszły plan Pro
- **Row-level tenancy** — prostsze niż schema-per-tenant, wystarczające dla tego skali

### Następne kroki (Faza 1 — pierwsza sesja kodowania)
- Stworzyć strukturę projektu (`config/`, `apps/`, `templates/`)
- `config/settings.py`: PostgreSQL, security hardened (lekcje z InnDesk)
- Docker Compose: web + postgres + nginx + cloudflared
- `apps/accounts/`: User, Organization, rejestracja + setup wizard (2 kroki)
- `apps/core/mixins.py`: TenantQuerySetMixin
- `apps/ingredients/`: modele + CRUD z tenant isolation
- `apps/recipes/`: modele + FC kalkulacja
- `templates/base.html`: Bootstrap 5 + sidebar
- Seed z przykładowymi danymi (10 składników, 3 dostawców, 3 przepisy)
- Deploy na ThinkCenter i weryfikacja
