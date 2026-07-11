# Portainer Backup And Rollback

Ta instrukcja dotyczy obecnego modelu wdrożenia z `docker-compose.yml`. Nie wymaga zmiany konfiguracji stacka w Portainerze.

## Które usługi należy zatrzymać

Na czas kontrolowanego backupu przez kopiowanie plików albo przed odtworzeniem bazy należy zatrzymać usługi korzystające z SQLite:

1. `scraper` / kontener `arena-scraper`
2. `web` / kontener `arena-web`

Usługa `vpn` / `gluetun` nie korzysta z bazy. Usługa `cloudflared` / `cloudflare-tunnel` nie korzysta z bazy.

Jeżeli backup jest wykonywany przez SQLite Backup API z aktywnej bazy, zatrzymanie usług nie jest technicznie wymagane, ale nadal jest najprostsze operacyjnie przed wdrożeniem lub rollbackiem.

## W jakiej kolejności

Backup kontrolowany:

1. Zatrzymaj `scraper` / `arena-scraper`, aby zatrzymać zapisy cykliczne.
2. Zatrzymaj `web` / `arena-web`, aby zatrzymać odczyty i ewentualne zapisy sesji/użytkowników.
3. Wykonaj backup i integralność kopii.
4. Uruchom `web` / `arena-web`.
5. Uruchom `scraper` / `arena-scraper`.

Rollback bazy:

1. Zatrzymaj `scraper` / `arena-scraper`.
2. Zatrzymaj `web` / `arena-web`.
3. Zachowaj aktualny stan bazy jako backup awaryjny.
4. Odtwórz wybraną kopię jako `/data/app.db`.
5. Usuń stare pliki `/data/app.db-wal` i `/data/app.db-shm` tylko wtedy, gdy wszystkie procesy korzystające z bazy są zatrzymane.
6. Uruchom `web` / `arena-web`.
7. Uruchom `scraper` / `arena-scraper`.

## Gdzie w Portainerze wejść

1. Otwórz Portainer.
2. Wejdź w `Environments`.
3. Wybierz środowisko, na którym działa produkcja.
4. Wejdź w `Stacks`.
5. Otwórz stack aplikacji.

DO WERYFIKACJI W PORTAINERZE: nazwa stacka produkcyjnego.

W widoku stacka użyj zakładki/listy usług lub kontenerów, aby zatrzymać i uruchomić `arena-scraper` oraz `arena-web`.

## Jak sprawdzić nazwę wolumenu

1. W Portainerze wejdź w wybrane środowisko.
2. Otwórz `Volumes`.
3. Odszukaj wolumen odpowiadający deklaracji Compose `pifpaf-data`.
4. Sprawdź etykiety albo nazwę powiązaną ze stackiem.

Oczekiwany wolumen logiczny z Compose: `pifpaf-data`.

DO WERYFIKACJI W PORTAINERZE: rzeczywista nazwa wolumenu Dockera, zwykle w formacie podobnym do `<stack>_pifpaf-data`.

Nie należy zgadywać tej nazwy przy montowaniu wolumenu do kontenera pomocniczego albo przy użyciu `docker run`.

## Jak wykonać backup

Preferowana metoda A: SQLite Backup API.

1. Upewnij się, że znasz rzeczywistą ścieżkę do pliku bazy widzianą przez proces wykonujący backup.
2. W repozytorium dostępny jest skrypt:

```bash
python tools/sqlite_backup.py --source /JAWNA/SCIEZKA/app.db --dest /JAWNA/SCIEZKA/backups/app-YYYYMMDD-HHMMSS.db
```

3. Skrypt wymaga jawnego `--source` i `--dest`.
4. Skrypt nie nadpisze istniejącego backupu. Przy istniejącym pliku zakończy się odmową.
5. Skrypt używa SQLite Backup API i wykonuje `PRAGMA integrity_check` na kopii.

Pozytywny wynik:

```text
Backup created: ...
integrity_check: ok
Metadata written: ...
```

Metoda B: kontrolowane zatrzymanie usług i kopiowanie plików.

1. Zatrzymaj `scraper` / `arena-scraper`.
2. Zatrzymaj `web` / `arena-web`.
3. Zweryfikuj, że oba kontenery są zatrzymane.
4. Skopiuj komplet plików bazy z wolumenu:

```text
app.db
app.db-wal
app.db-shm
```

5. Jeżeli po zatrzymaniu usług istnieje tylko `app.db`, skopiuj `app.db`.
6. Zachowaj także użyty plik Compose oraz wartości zmiennych środowiskowych stacka z Portainera.

DO WERYFIKACJI W PORTAINERZE: lokalizacja katalogu backupów na hoście albo sposób pobrania backupu z kontenera pomocniczego.

## Jak sprawdzić integralność

Dla pliku backupu uruchom:

```bash
sqlite3 /JAWNA/SCIEZKA/backups/app-YYYYMMDD-HHMMSS.db "PRAGMA integrity_check;"
```

Pozytywny wynik:

```text
ok
```

Jeżeli `sqlite3` nie jest dostępne na hoście, można użyć Pythona:

```bash
python -c "import sqlite3; db='/JAWNA/SCIEZKA/backups/app-YYYYMMDD-HHMMSS.db'; print(sqlite3.connect(db).execute('PRAGMA integrity_check').fetchone()[0])"
```

Pozytywny wynik:

```text
ok
```

Testowe odtworzenie kopii:

1. Utwórz osobny katalog testowy poza produkcyjnym wolumenem.
2. Skopiuj backup jako testowe `app.db`.
3. Uruchom na nim `PRAGMA integrity_check`.
4. Opcjonalnie uruchom osobny stack testowy z `docker-compose.test.yml` dopiero po zweryfikowaniu i poprawieniu rzeczywistej nazwy wolumenu produkcyjnego.

DO WERYFIKACJI W PORTAINERZE: czy środowisko testowe ma używać `docker-compose.test.yml`, innego stacka Portainer, czy ręcznego kontenera pomocniczego.

## Jak ponownie uruchomić stack

Po backupie:

1. W Portainerze otwórz produkcyjny stack.
2. Uruchom `web` / `arena-web`.
3. Poczekaj na pozytywny healthcheck `web`, jeżeli Portainer go pokazuje.
4. Uruchom `scraper` / `arena-scraper`.
5. Sprawdź logi `arena-web`.
6. Sprawdź logi `arena-scraper`.

Pozytywne wyniki:

- `web` odpowiada na dashboardzie.
- healthcheck `web` jest `healthy`, jeśli widoczny.
- logi `scraper` pokazują start schedulera i brak błędów połączenia z bazą.
- logi nie zawierają błędów `database is locked`, `no such table`, `unable to open database file`.

DO WERYFIKACJI W PORTAINERZE: czy Portainer pokazuje healthcheck dla kontenera `arena-web` w używanej wersji UI.

## Jak wykonać rollback

Rollback kodu/stacka:

1. Nie zmieniaj nazw usług, wolumenów, portów ani zmiennych środowiskowych.
2. W Portainerze wróć do poprzedniej wersji stacka zgodnie z aktualnym sposobem wdrażania.
3. Jeżeli stack jest z Git, wybierz poprzedni commit/tag albo przywróć poprzednią zawartość pliku Compose.
4. Jeżeli stack jest z Web editor, wklej poprzednią zachowaną konfigurację.
5. Wdróż stack ponownie.

DO WERYFIKACJI W PORTAINERZE: czy produkcyjny stack jest utrzymywany z Git, Web editor, czy uploadu Compose.

Rollback bazy SQLite:

1. Zatrzymaj `scraper` / `arena-scraper`.
2. Zatrzymaj `web` / `arena-web`.
3. Zrób awaryjną kopię aktualnych plików `app.db*` z wolumenu przed nadpisaniem.
4. Zweryfikuj backup docelowy komendą `PRAGMA integrity_check`; wynik musi być `ok`.
5. Umieść wybrany backup jako `/data/app.db` w wolumenie `pifpaf-data`.
6. Usuń `/data/app.db-wal` i `/data/app.db-shm` tylko przy zatrzymanych `scraper` i `web`.
7. Uruchom `web` / `arena-web`.
8. Uruchom `scraper` / `arena-scraper`.
9. Sprawdź dashboard i logi obu usług.

Pozytywne wyniki:

- `PRAGMA integrity_check` zwraca `ok`.
- dashboard ładuje dane.
- `arena-web` nie zgłasza błędu otwarcia SQLite.
- `arena-scraper` startuje scheduler i wykonuje cykl bez błędów bazy.

## Zachowanie plików konfiguracyjnych

Przed wdrożeniem albo rollbackiem zachowaj:

- aktualny `docker-compose.yml` używany przez Portainer
- wartości zmiennych środowiskowych stacka
- nazwę rzeczywistego wolumenu produkcyjnego
- informację o sposobie wdrażania stacka
- token/konfigurację Cloudflare tylko zgodnie z zasadami bezpieczeństwa używanymi przez operatora

DO WERYFIKACJI W PORTAINERZE: gdzie Portainer przechowuje wartości zmiennych i czy można je wyeksportować bez ujawniania sekretów.

## Czego nie wolno robić

- Nie zmieniaj nazw usług Compose.
- Nie zmieniaj `container_name`.
- Nie zmieniaj named volumes.
- Nie zmieniaj montowania `pifpaf-data:/data`.
- Nie zmieniaj produkcyjnej ścieżki bazy `/data/app.db`.
- Nie przenoś mapowania portu z `vpn` na `web`.
- Nie usuwaj `network_mode: "service:vpn"` z `scraper` ani `web`.
- Nie zmieniaj konfiguracji Gluetun bez osobnego planu.
- Nie zmieniaj konfiguracji Cloudflare Tunnel bez osobnego planu.
- Nie kopiuj aktywnego samego `app.db` jako backupu.
- Nie kopiuj aktywnych `app.db`, `app.db-wal` i `app.db-shm` zwykłym `cp`, jeżeli `scraper` albo `web` nadal działają.
- Nie używaj `docker-compose.test.yml` do kopiowania produkcyjnego wolumenu bez wcześniejszej weryfikacji nazwy wolumenu i spójności bazy.
- Nie nadpisuj produkcyjnej bazy bez awaryjnej kopii aktualnego stanu.

PORTAINER: na tym etapie nie są wymagane żadne zmiany konfiguracji stacka.
