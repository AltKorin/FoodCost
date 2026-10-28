# Historia sesji — fc.sudomie.pl

---

## Sesja 2026-09-08 (3) — Dostawca z OCR, eksport CSV/Excel/Word

Kontynuacja. User: "czy dostawcę też mógłby ściągać z faktury?" → potem
"jeszcze eksport do pliku — excel, word, csv i mamy chyba wszystko."

### Zrobiono
- **Dostawca z OCR:** pole dostawcy na wgrywaniu faktury opcjonalne —
  puste = `_match_supplier()` (overlap słów, jak fuzzy_match_ingredients)
  dopasowuje `supplier_name` wyciągnięty przez AI do istniejących `Supplier`.
  Ekran potwierdzenia dostał dropdown dostawcy z opcją "+ Utwórz nowy" —
  ten sam wzorzec co składniki. Michał nie musi nic zakładać ręcznie przed
  pierwszym testem OCR.
- **Eksport CSV/Excel składników** (`apps/ingredients/export_views.py`) —
  jeden wiersz na (składnik, aktualna cena dostawcy), przycisk przy widoku
  Składniki. `openpyxl` dla xlsx.
- **Eksport Word menu** (`apps/recipes/export_views.py`) — tabela dań z
  kosztem/porcję i FC%, dokument do pokazania klientowi (nie dane do
  analizy — stąd Word, nie kolejny arkusz). `python-docx`.
- **Znaleziony i naprawiony gap:** lokalne repo nie miało migracji
  `recipes.0002` (katalog migracji root-owned od kwietnia, bez sudo nie
  dało się dopisać pliku — ani tu, ani na `proxmox`). Odkryte dopiero przy
  próbie realnego testu funkcjonalnego eksportu (Recipe/Menu query wywala
  się bez tej migracji). Nie naprawione w lokalnym repo (brak sudo) —
  produkcja ma poprawny stan, opisane jako otwarty punkt w HANDOFF z
  dokładną ścieżką skąd wziąć plik jak ktoś zdobędzie sudo.

### Zadziałało
- **Realny test funkcjonalny przed wdrożeniem eksportu** — tymczasowy
  Postgres + kontener web (nie produkcja), seed danych testowych, wywołanie
  wszystkich trzech endpointów przez zalogowany `django.test.Client`,
  weryfikacja magic bytes ZIP dla xlsx/docx i treści CSV. To złapało brak
  migracji 0002 ZANIM dotknęło produkcji — `manage.py check` (użyty przy
  poprzednich zmianach) nie wykrywa problemów ze stanem bazy, bo nie łączy
  się z bazą.
- Wzorzec "dropdown z opcją + Utwórz nowy" (wprowadzony dla składników w
  poprzedniej sesji) przeniesiony 1:1 na dostawcę — spójne UX, mniej kodu
  do wymyślenia od zera.

### Nie zadziałało
- Pierwsza próba `docker compose up -d --build web` po wdrożeniu OCR z
  dostawcą dała chwilowy 502 (nginx złapał moment restartu kontenera) —
  samo się naprawiło w ~26s, fałszywy alarm.
- Curl z lokalnej maszyny do fc.sudomie.pl dawał losowe `000` — okazało się
  to problemem z IPv6 na tej sieci, nie z serwerem (`curl -4` stabilne
  200 z hosta `kelnerzy` i z lokalnej maszyny).

### Następne kroki
- Realny test OCR z Michałem na żywej fakturze — wciąż nie zrobiony.
- Zdobyć sudo na tej maszynie i naprawić `apps/*/migrations/` (chown),
  dograć `recipes.0002` do lokalnego repo — patrz HANDOFF pkt 8.
- Model monetyzacji OCR dla przyszłych klientów — wciąż nierozstrzygnięty.

---

## Sesja 2026-09-08 (2) — Port OCR faktur + wdrożenie na produkcję

Kontynuacja poprzedniej sesji (archiwizacja foodcost.sudomie.pl). User: "zacznij
port OCR. Ale to nie jest opcja którą chcemy dawać za darmo bo wymaga tokenów
[...] Najpierw wersja tylko dla Michała i Niedźwiadka."

### Zrobiono
- Port `ocr_service.py` (bez zmian — był już generyczny) i `invoice_views.py`
  (przepisany pod multi-tenant: `organization` scoping na Ingredient/Supplier/
  SupplierPrice) z `legacy-foodcost/` do `apps/ingredients/`.
- Gate na funkcję: reużyte istniejące pole `Organization.plan` (free/pro) —
  zero nowego modelu, zero systemu płatności. Dekorator `@pro_required` w
  `apps/accounts/decorators.py`, link w sidebarze warunkowy na `plan == 'pro'`.
- `Organization` pk=3 (`niedzwiadek-test`) → nazwa **"Hotel Niedźwiadek SPA &
  Natura"**, `plan='pro'`.
- Weryfikacja lokalna przed wdrożeniem: zbudowany obraz Dockera lokalnie,
  `manage.py check` (bez bazy) czysto, parsowanie wszystkich 3 szablonów
  (`base.html` + 2 nowe) przez `get_template()` czysto.
- Wdrożone na `kelnerzy` (`/opt/fc-sudomie-pl`): `git archive` → tar → scp →
  rozpakowanie → `docker compose up -d --build web`. Nowe zależności
  (`openai`, `PyMuPDF`) zainstalowane, migracje/collectstatic przeszły,
  gunicorn wstał, `curl https://fc.sudomie.pl/` → 200.

### Zadziałało
- Testowanie w lokalnie zbudowanym obrazie Dockera bez żywej bazy —
  `manage.py check` i `get_template()` nie potrzebują połączenia z Postgresem,
  więc dało się złapać błędy składni/importów/szablonów przed dotknięciem
  produkcji, mimo braku lokalnego środowiska dev z `.env`.
- Reużycie pola `plan` zamiast nowego `ocr_enabled` bool — organizacja i tak
  miała już rozróżnienie free/pro w modelu, więc gate kosztował zero migracji.

### Nie zadziałało / czekało na usera
- Pierwsza próba `scp` na `kelnerzy` zablokowana przez auto-mode classifier
  (akcja na produkcji) — wymagało jawnego "wdróż OCR" od usera zanim spróbować
  ponownie (druga próba przeszła bez problemu, to była kwestia potwierdzenia,
  nie techniczna blokada).

### Następne kroki
- **Brak `OPENAI_API_KEY` w `.env` na `kelnerzy`** — dodać klucz przed
  pokazaniem funkcji Michałowi, inaczej dostanie czytelny błąd zamiast wyniku.
- Migracja realnych danych Niedźwiadka z produkcji `foodcost.sudomie.pl`
  (MySQL) do fc.sudomie.pl (Postgres) — po stronie Michała potwierdzenie
  przejścia.
- Model monetyzacji OCR dla przyszłych klientów (nie-Niedźwiadek) — token-based
  czy abonament, nierozstrzygnięte.
- User rozważał migrację `fc.sudomie.pl` z `kelnerzy` na nowy ProxMox z powodu
  planowanego mailingu do CRM (43 osoby / 84 firmy) — ustalone, że to za mały
  wolumen żeby to uzasadniać (LXC ma dziś 13% RAM, 0% CPU); swap na `kelnerzy`
  zapchany w 87% niezależnie od tego wątku, warty sprawdzenia osobno.

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

## Sesja 2026-09-21
### Zrobiono
- Odświeżono landing z kalkulatorem i wspólne style aplikacji: jasna
  nawigacja, spokojniejsza hierarchia, bardziej czytelne formularze i tabele.
- Dodano widoczne logowanie na landing, czytelniejszy opis wyniku,
  walidację ceny i polski format PLN. FAQ korzysta z natywnego details.
- Naprawiono obsługę mobilnego menu: Bootstrap offcanvas, Escape,
  zamknięcie przyciskiem, zarządzanie fokusem. Dodano etykiety dla
  wyszukiwarek i ikon akcji na listach składników i przepisów.
### Zadziałało
- Lokalne testy przeglądarkowe na danych demo i Django check.
- Inspiracja lokalnymi podglądami Infinite Beauty; sama rozmowa niedostępna.
### Nie zadziałało
- Istniejące migracje nie odtwarzają aktualnych modeli; do testów użyto
  osobnej bazy SQLite z syncdb i ustawień w /tmp, bez zmian produkcyjnych.
- Sandbox blokował pobieranie zależności, serwer i Chromium; wykonano
  te operacje po zatwierdzeniu wymaganych uprawnień.
### Następne kroki
- Ocena lokalnego podglądu; wdrożenie na produkcję pozostaje osobnym krokiem.

### Wdrożenie wyglądu (2026-09-21)
- Na zlecenie użytkownika wdrożono sześć plików UI na kelnerzy; backup
  szablonów/CSS i tag starego obrazu zachowane przed zmianą.
- Przebudowano web, sprawdzono Django oraz publiczną stronę w Chromium:
  nowy wygląd, kalkulator, responsywność i ekran logowania działają.
- Następny temat: wybór nowszego modelu OCR zamiast gpt-4o; zidentyfikowano
  także limit odpowiedzi 2000 tokenów i problemy przeliczania/potwierdzania cen.

## Sesja 2026-09-21: tani OCR dla zdjęć i PDF
### Zrobiono
- Po wyborze użytkownika wdrożono GPT-4.1 mini, zamiast gpt-4o.
- Doprecyzowano nazwy, ilość zakupioną vs wielkość opakowania, ceny
  jednostkowe i netto/brutto; odpowiedź wymuszona schematem JSON.
- Naprawiono podwójne dzielenie ceny opakowania oraz zdublowane pola
  mobilne/desktop, które nadpisywały korekty na ekranie potwierdzenia.
### Zadziałało
- 9 testów regresyjnych i sprawdzenie formularza w Chromium 390/1440 px.
- Rzeczywiste API gpt-4.1-mini poprawnie odczytało syntetyczny PDF i PNG.
- Wdrożenie na kelnerzy z backupem, Django check i aktywny model potwierdzone.
### Nie zadziałało / ograniczenia
- Brak rzeczywistych problematycznych faktur do porównania dokładności.
### Następne kroki
- Sprawdzić ponowny odczyt faktur klienta z błędnymi nazwami i ilościami.

## Sesja 2026-09-21: udostępnienie bezpłatnej próby OCR
### Zrobiono
- Wdrożono 30 dni od pierwszego udanego OCR i 100 stron na lokal,
  licznik dni/stron, sprawdzanie pliku przed odczytem, obsługę wyczerpania.
- Rezerwacje pod blokadą wiersza, zwrot stron po błędzie, ochrona przed
  podwójnym wysłaniem i odzyskiwanie rezerwacji po awarii procesu.
- Dostęp Free do OCR, zachowanie Pro, zapis już odczytanych wyników po
  zakończeniu próby i niezmienione darmowe ręczne funkcje.
- Oferta próby na landing/rejestracji/dashboardzie, Open Graph dla Facebooka.
- Po informacji o braku konta spółki: odłożono płatności, dodano zgłoszenie
  zainteresowania dalszym OCR do panelu admina (bez zamówienia/opłat).
### Zadziałało
- 26 testów na osobnej bazie PostgreSQL, także rzeczywisty test współbieżności.
- Chromium: nowa rejestracja, konfiguracja lokalu, PDF preview, zwrot po
  błędzie, widoki telefonu/desktop. Sprawdzenie Free/Pro na produkcji.
- Backup bazy i kodu przed migracją oraz zachowany poprzedni obraz.
### Nie zadziałało
- Sudo wymaga hasła; zapis migracji umożliwiono przez zachowanie starych
  katalogów obok nowych kopii. Brakującą recipes.0002 pobrano z produkcji.
### Następne kroki
- Użytkownik może udostępnić fc.sudomie.pl; nie publikowano ani nie wysyłano
  niczego w jego imieniu. Obserwować zgłoszenia dalszego dostępu w adminie.
- Podłączyć sprzedaż pakietów po decyzji o obsłudze płatności spółki.

## Sesja 2026-09-21: zmniejszenie limitu OCR
### Zrobiono
- Limit próby zmieniony ze 100 na 30 stron łącznie przez 30 dni.
- Użytkownik potwierdził brak dziennego ograniczenia. Liczniki i początek
  istniejących prób zachowane, Pro bez zmian.
- Komunikaty i metadane udostępniania ujednolicone z nowym limitem.
### Zadziałało
- 26 testów na PostgreSQL, wdrożenie web i weryfikacja ustawień 30/30.
### Nie zadziałało
- Brak nowych problemów.
### Następne kroki
- Obserwować wykorzystanie okresów próbnych po udostępnieniu strony.

## Sesja 2026-10-04
### Zrobiono
- GA4 (`G-6DYFBNNH6X`) na fc.sudomie.pl za flagą `GA_MEASUREMENT_ID`, Consent Mode v2 + baner zgody; wdrożone na `kelnerzy`, tag zweryfikowany curl-em na `/`.
### Zadziałało
- Consent Mode default-denied zamiast blokowania tagu do zgody — ruch z UE liczony (modelowany) od pierwszego dnia.
### Nie zadziałało
- Cloudflare Web Analytics: ustawione „excluding EU” → zero danych z PL; user wybrał GA.
- Cloudflare Traffic pokazuje wszystkie requesty (boty, skanery), nie ludzi.
- foodcost.sudomie.pl → 301 na fc.sudomie.pl (Cloudflare Redirect Rule), zrzut MySQL do `legacy-foodcost/db-dump/`, integracja oferty→foodcost wyłączona.
- Redirect Rule: wildcard `https://…/*` łapał tylko HTTPS, `http*://` Cloudflare parsował jako host „http”; zadziałało wyrażenie `http.host eq` + target `concat(...)` (goły string jako target odrzucany przez walidację).
### Następne kroki
- Linki w nowej porcji maili z `utm_campaign`; po wysyłce sprawdzić GA Realtime/Pozyskanie.
- ~2026-11-04: usunąć aplikację foodcost z cPanel GoDaddy; monitor foodcost w uptime.sudomie.pl usunąć.


## Sesja 2026-10-04: oferty jako moduł FoodCost
### Zrobiono
- Zidentyfikowano grupy.sudomie.pl w oferty.sudomie.pl/oferty_grupowe.
- Użytkownik wybrał moduł ofert we wspólnym fc.sudomie.pl.
- Przygotowano apps.offers, migrację, formularze, listę/szczegóły,
  wydruk dla klienta, sidebar i wejście z dashboardu.
- Snapshot menu i kosztu, ceny negocjowane, pozycje noclegów/usług,
  wewnętrzny food cost, izolacja organizacji i ochrona edycji revision.
### Zadziałało
- 8 testów Django 5.2.14 na SQLite, check i kontrola migracji.
### Nie zadziałało / ograniczenia
- Instalacja osobnego środowiska z pip niedostępna przez DNS sandboxa;
  testy wykonano istniejącym Django 5.2 z zależnościami istniejącego venv.
- Brak testu UI w przeglądarce i testu współbieżności na PostgreSQL.
- Nowy moduł działa lokalnie; nie wdrożono go ani nie migrowano danych grupy.
### Następne kroki
- Wdrożenie z backupem i weryfikacją wersji kodu na kelnerzy.


## Sesja 2026-10-04: landing pakietu na osobę
### Zrobiono
- Nowy hero i kalkulator pakietu z dwiema zakładkami, 3 kroki, CTA, FAQ i meta.
- Wejście gastro_2026_10 otwiera poprzedni kalkulator dania i pasujący komunikat.
- CSS v20261004 i naprawa ukrywania banera zgody bez zmiany logiki/treści.
- Zrzuty 375/1280, raport i osobny zestaw do wdrożenia bez niewdrożonych Ofert.
### Zadziałało
- Node: wzory, przypadki negatywne i 24 kombinacje regresji dania.
- Django 5.2.17: render i linki/GA/KRS/meta; Chromium: oba kalkulatory,
  320/375/768/1280, błędy, klawiatura, focus, aria-live, noscript i brak requestów.
- Lighthouse lokalny: 97/100/96/100 (performance/accessibility/best practices/SEO).
### Nie zadziałało
- Sandbox wymagał eskalacji dla SSH, pobrania zależności i lokalnej przeglądarki.
- Chrome przez Claude-in-Chrome niedostępny; użyto Chromium przez Playwright.
- Rzeczywiste ogłaszanie czytnikiem ekranu nieprzetestowane.
- Content-gapy: brak realnych kwot strat, trendu cen, opinii i zgody na nazwę hotelu;
  użyto wyłącznie oznaczonego scenariusza. Brak danych lejka pierwszej kampanii.
### Następne kroki
- Akceptacja zrzutów, backup i wdrożenie wyłącznie plików z docs/landing-2026-10-04/deploy.
- Weryfikacja produkcji i ustawienie polecenia na done po deployu.
- Sprawdzić wejścia z maili, rejestracje i dodanie pierwszego pakietu/faktury.

## Sesja 2026-10-04: audyt pakietów (backend)
### Zrobiono
- Audyt kodu i testy 48 przypadków (SQLite + izolowany PostgreSQL 16) wg `prompty/polecenia/backend-audyt-pakietow.md`; raport `docs/audyt-pakietow-2026-10-04.md`.
- Porównanie sha256 z produkcją (`kelnerzy`): modele/widoki cen i faktur identyczne, `apps/offers` i nowy landing tylko lokalnie.
### Zadziałało
- Scenariusz referencyjny (4→5 zł, 6→7,50 zł/os., FC 10→12,5%, +120 zł) liczy się poprawnie; izolacja organizacji bez wycieku.
- Testy z `expectedFailure` dokumentują oczekiwanie biznesowe bez czerwonej gałęzi; testy leżą w `docs/`, nie w `apps/`.
### Nie zadziałało
- Pierwsze wersje 3 testów miały złe asercje (locale `0,0%`, UI już komunikuje koszt ręczny, kolizja nazwy składnika) — poprawione, kod aplikacji nietknięty.
- `manage.py test apps` zgłasza 2 błędy z katalogów `.migrations-backup-20260921` (artefakt, nie testy).
### Następne kroki
- Wiszą: usterki U1–U11 (nienaprawiane — audyt), decyzje produktowe do kontroli marży imprezy, walidacja z klientem. Kolejność prac w raporcie, sekcja 8.

## Sesja 2026-10-04: naprawa U1–U3 (przed wdrożeniem landingu)
### Zrobiono
- `Recipe.is_cost_complete` / `Menu.is_cost_complete` (niepuste menu, każdy składnik z ceną w przeliczalnej jednostce, ilość i yield > 0); FC% = brak przy niekompletnym koszcie; ostrzeżenia w widoku menu, przepisu i liście przepisów.
- Ceny w jednostce niezgodnej ze składnikiem: ignorowane w `get_best_price`, odrzucane w formularzu ceny (`SupplierPrice.clean`) i pomijane przy zatwierdzaniu faktury. Oferty używają definicji z Menu.
- 12 testów regresyjnych w `apps/recipes/tests.py`; testy audytu uzupełnione (usunięte 8 przestarzałych).
### Zadziałało
- Bez migracji (zmiany tylko w logice); wszystkie testy apps przechodzą (2 znane artefakty katalogów backupu).
### Nie zadziałało
- Nic. Nie wdrożono; nie sprawdzano produkcyjnych danych — po wdrożeniu część istniejących menu zmieni się na „niepełne” (zamierzone), a ceny w niezgodnej jednostce znikną z wyliczeń.
### Następne kroki
- Wiszą U4–U11 oraz wdrożenie razem z landingiem (przed deployem: zapytanie tylko-do-odczytu o ceny w niezgodnych jednostkach na produkcji).

## Sesja 2026-10-04: wdrożenie U1–U3
### Zrobiono
- Backup, wysyłka 9 plików, przebudowa `web`, weryfikacja (strony 200, logi czyste, nowe własności działają na danych produkcyjnych).
### Zadziałało
- Wcześniejszy pre-check (0 niezgodnych jednostek, 0 duplikatów) — wdrożenie bez niespodzianek.
### Nie zadziałało
- `docker compose restart web` nie załadował kodu (jest w obrazie) — dopiero `up -d --build web`. Przez chwilę host miał nowe pliki, a kontener stary kod (bez wpływu na użytkowników).
- Moje podsumowanie pre-checku „żadne menu się nie zmieni” było technicznie prawdziwe (liczyło tylko przejścia kompletne→niepełne), ale wszystkie 3 menu są niepełne — to dane niedokończone, nie skutek wdrożenia.
### Następne kroki
- Landing nadal czeka na akceptację zrzutów; U4–U11 niewdrożone/nienaprawione.

## Sesja 2026-10-04: zamknięcie części backendowej
### Zrobiono
- Dokumentacja backendu domknięta (HANDOFF: stan końcowy, ograniczenia dla landingu, otwarte usterki); landing przekazany agentowi frontendowemu.
- Na żądanie wykonano `docker compose restart web` (kod i tak już był w przebudowanym obrazie).
### Zadziałało
- Wdrożenie U1–U3 z backupem i weryfikacją na danych produkcyjnych; krok 3 landingu jest po nim zgodny z działaniem aplikacji.
### Nie zadziałało
- Nic nowego.
### Następne kroki
- Wiszą: U4–U11, decyzje produktowe do kontroli marży imprezy, walidacja z klientem, wdrożenie landingu (agent frontendowy). Szczegóły w raporcie audytu.



## Sesja 2026-10-04: wdrożenie landingu i zasady trackingu
### Zrobiono
- Po akceptacji użytkownika wdrożono 3 pliki landingu, backup ze strukturą katalogów:
  kelnerzy:/root/fc-backup-landing-20261004-1508/. Backend U1–U3 zachowany.
- Zachowano GA4 i Consent Mode; dodano obowiązkową kontrolę kodów Google do
  HANDOFF oraz docs/WDROZENIA.md (także zasada w HANDOFF sudomie.pl).
### Zadziałało
- Build web/collectstatic i Django check. HTTP 200 dla /, /register/, /regulamin/;
  GA4 G-6DYFBNNH6X i zgody obecne we wszystkich trzech stronach.
- Chromium na produkcji: kalkulatory, zmiana pól, zakładki klawiaturą,
  375/1280 px, wejście z maila i zachowanie decyzji/consent update.
### Nie zadziałało
- Cloudflare odrzucił odczyt urllib (403); odczyt curl i Chromium działał.
- Test przeglądarki blokował pingi GA, więc nie potwierdza odbioru zdarzeń
  w GA Realtime. Rzeczywisty tag zweryfikowano w HTML produkcyjnym.
- Content-gapy bez zmian: brak realnych kwot strat/opinii/zgody na nazwę hotelu;
  wzrost 10% pozostaje scenariuszem. U4–U11 audytu nie są objęte tym deployem.
### Następne kroki
- Obserwować wejścia z kampanii, konta i pierwszy pakiet/fakturę.


## Sesja 2026-10-04: ilustracja procesu na landing
### Zrobiono
- Wygenerowano infografikę faktura → przepis → pakiet (built-in image_gen),
  zapisano asset/prompt; dodano do lokalnego landingu i podglądu localhost:8766.
- Zrzuty telefonu i desktopu oraz pakiet 4 plików bez niewdrożonych Ofert.
### Zadziałało
- Render Django, regresja kalkulatorów, obraz/320/375/768/1280 bez overflow,
  routing z maila i obecność Google tagu.
### Nie zadziałało
- Nie użyto wspomnianego zdjęcia — nie było dostępne w tej rozmowie ani assetach.
- Produkcja bez zmian; nowa ilustracja czeka na ocenę podglądu.
### Następne kroki
- Akceptacja ilustracji, backup, deploy 4 plików visual/deploy, rebuild,
  obowiązkowa weryfikacja kodów Google. Content-gapy/opinie bez zmian.


## Sesja 2026-10-04: zdjęcie zespołu kuchni na landing
### Zrobiono
- Dodano zdjęcie dostarczone przez użytkownika przy hero; zachowano infografikę.
- WebP 1440×960 ~107 KB zamiast JPG 4,7 MB, oryginał zachowany, CSS v20261004-3.
### Zadziałało
- Django render i Chromium: zdjęcie/ilustracja, 320–1280 bez overflow,
  kalkulatory, wejście z maila i tag Google zachowane. Podgląd localhost:8766.
### Nie zadziałało
- Produkcja jeszcze bez obu grafik; czeka na ocenę ostatecznego układu.
### Następne kroki
- Akceptacja, backup i wdrożenie 5 plików visual/deploy; obowiązkowa kontrola GA.


## Sesja 2026-10-04: wdrożenie zdjęcia i infografiki
### Zrobiono
- Wdrożono zatwierdzone 5 plików visual/deploy, backup
  kelnerzy:/root/fc-backup-visual-20261004-1525/, rebuild web/collectstatic.
- Zdjęcie przy hero, infografika przy 3 krokach, CSS v20261004-3.
### Zadziałało
- HTTP /, /register/, /regulamin/ 200; GA4 G-6DYFBNNH6X i Consent Mode zachowane.
- Chromium: oba obrazy, 320–1280 bez overflow, kalkulatory, zmiana ceny,
  klawiatura, mail i obsługa zgody. Dowody w docs/landing-2026-10-04/visual/.
### Nie zadziałało
- Brak nowych problemów. GA Realtime nie sprawdzano; testowe pingi blokowane.
### Następne kroki
- Obserwować wejścia z kampanii i aktywację kont; content-gapy bez zmian.

## Sesja 2026-10-28 — podlinkowanie sudomie
### Zrobiono
- Przygotowano lokalnie blok Narzędzia sudomie w templates/core/landing.html i styl w static/css/app.css. Źródło linków: ../sudomie.pl/data/produkty.json.
### Zadziałało
- Generator 0/8 nieaktualnych; podgląd szablonu Django + Chromium 390/1440 px: stopka czytelna.
### Nie zadziałało / ograniczenia
- Nie wdrażano: istniejąca niewdrożona praca WIP, zgodnie z zakresem zadania.
### Następne kroki
- Publikacja wraz z najbliższym wydaniem, [474](https://projekty.sudomie.pl/work_packages/474). Zadanie źródłowe: [473](https://projekty.sudomie.pl/work_packages/473).

## Sesja 2026-10-28 (wyrównanie i demo)
### Zrobiono
- Porównanie git / lokalnie / produkcja plik po pliku (sha256): 32 pliki z produkcji poza gitem → commit `7a23a35`.
- Demo bez rejestracji, Oferty za flagą, stopka sudomie, `seed` bez hasła w kodzie → commit `af539fd`. Testy 54/54.
### Zadziałało
- Kopia produkcji przez rsync tylko do odczytu + porównanie skrótów: jasny podział na „wdrożone, niezacommitowane”,
  „tylko lokalnie” i „rozjechane” — rozjechane okazały się tylko Ofertami i stopką, bez konfliktów.
- Flaga Ofert przez dekorator na adresach (nie warunkowe `urlpatterns`) — testy mogą ją włączyć `override_settings`.
### Nie zadziałało
- Pierwsze sprzątanie piaskownicy: `ProtectedError` (PROTECT na RecipeIngredient/MenuItem blokuje kaskadę) — usuwane najpierw.
- Zapytanie tylko do odczytu o migracje i konto demo na serwerze zablokował tryb uprawnień — czeka na zgodę usera.
### Następne kroki
- Wdrożone 19:25 po awarii hosta: `/`, `/register/`, `/regulamin/` 200 z GA4 i Consent Mode, demo i stopka na żywo,
  `/offers/` 404 (flaga), kelnerzy 200, przeklikanie demo na produkcji 390/1280 px bez błędów JS.
- Awaria: build dobił przepełnioną pulę LVM-thin hosta `kawaleryjska` → ext4 tylko do odczytu → fc i kelnerzy 502 przez ~77 min.
  Naprawa przez Konrada na hoście (fsck, fstrim), sprzątanie build cache. Przyczyna u źródła (overcommit) — zadanie infrastruktury.
- Konto `demo@fc.sudomie.pl` z hasłem `demo12345` istnieje na produkcji — czeka na decyzję (#479).
