# Portainer Database Migration

Ta instrukcja dotyczy kontrolowanej migracji SQLite do kanonicznego schematu aplikacji `pifpafDashboard`. Nie zmienia `docker-compose.yml`, nazw usług, portów, sieci, wolumenów ani ścieżki `/data/app.db`.

## Przygotowanie backupu

1. Otwórz Portainer.
2. Wejdź w `Environments`.
3. Wybierz środowisko produkcyjne.
4. Wejdź w `Stacks`.
5. Otwórz stack aplikacji.

DO WERYFIKACJI W PORTAINERZE: nazwa produkcyjnego stacka.

Zatrzymaj usługi zapisujące do SQLite:

1. Zatrzymaj `scraper` / kontener `arena-scraper`.
2. Zatrzymaj `web` / kontener `arena-web`.

`vpn` / `gluetun` oraz `cloudflared` / `cloudflare-tunnel` nie korzystają z SQLite i nie muszą być zatrzymywane do samego backupu bazy.

Wykonaj backup zgodnie z `PORTAINER_BACKUP_AND_ROLLBACK.md`. Preferowana metoda to SQLite Backup API:

```bash
python tools/sqlite_backup.py --source /JAWNA/SCIEZKA/app.db --dest /JAWNA/SCIEZKA/backups/app-YYYYMMDD-HHMMSS.db
```

Jeżeli backup robisz przez kopiowanie plików, wolno kopiować `app.db`, `app.db-wal` i `app.db-shm` tylko po zatrzymaniu `scraper` i `web`.

## Sprawdzenie backupu

Uruchom:

```bash
sqlite3 /JAWNA/SCIEZKA/backups/app-YYYYMMDD-HHMMSS.db "PRAGMA integrity_check;"
```

Pozytywny wynik:

```text
ok
```

Jeżeli `sqlite3` nie jest dostępne, użyj Pythona:

```bash
python -c "import sqlite3; db='/JAWNA/SCIEZKA/backups/app-YYYYMMDD-HHMMSS.db'; print(sqlite3.connect(db).execute('PRAGMA integrity_check').fetchone()[0])"
```

Maksymalny punkt przerwania: jeżeli backup nie istnieje albo `integrity_check` nie zwraca `ok`, przerwij operację i nie uruchamiaj migracji.

## Identyfikacja właściwego wolumenu

1. W Portainerze wejdź w `Volumes`.
2. Odszukaj wolumen odpowiadający deklaracji Compose `pifpaf-data`.
3. Sprawdź nazwę rzeczywistego wolumenu Dockera.

DO WERYFIKACJI W PORTAINERZE: rzeczywista nazwa wolumenu, zwykle podobna do `<stack>_pifpaf-data`.

Nie zgaduj nazwy wolumenu. Migrację wolno uruchomić tylko na wolumenie, który zawiera produkcyjny plik `/data/app.db` używany przez `scraper` i `web`.

## Uruchomienie migracji

Wymagany obraz: aktualny obraz usługi `scraper` po rebuildzie, zawierający plik `/app/migrate_db.py`.

DO WERYFIKACJI W PORTAINERZE: dokładna nazwa obrazu używanego przez kontener `arena-scraper` po aktualizacji stacka.

Jeżeli Portainer po rebuildzie automatycznie uruchomi `arena-scraper` przed migracją, scraper powinien zalogować komunikat `Database schema requires a controlled migration` i nie uruchomić schedulera. Zatrzymaj wtedy ponownie `scraper` oraz upewnij się, że `web` jest zatrzymany przed wykonaniem migracji.

Opcja A, jednorazowy kontener pomocniczy w Portainerze:

1. Wejdź w `Containers`.
2. Wybierz `Add container`.
3. Użyj tego samego obrazu, którego używa `arena-scraper`.
4. Zamontuj rzeczywisty wolumen odpowiadający `pifpaf-data` jako `/data`.
5. Nie publikuj portów.
6. Sieć nie jest potrzebna do migracji bazy.
7. Ustaw komendę dry-run:

```bash
python /app/migrate_db.py --database /data/app.db --dry-run
```

Oczekiwany output dry-run:

```text
Migration plan: /data/app.db
schema_kind: legacy_scraper
schema_version: 4
migrations: 001_create_canonical_schema, 002_migrate_legacy_scraper_schema, 003_migrate_legacy_web_schema, 004_add_constraints_indexes_status
```

`schema_kind` może być też `legacy_web`, `partial`, `empty` albo `canonical`, zależnie od rzeczywistej bazy.

Maksymalny punkt przerwania: jeżeli dry-run zwraca `Unsupported SQLite schema`, błąd integralności, błędny wolumen albo brak `/data/app.db`, przerwij operację i nie uruchamiaj migracji zapisującej.

Po poprawnym dry-run uruchom migrację:

```bash
python /app/migrate_db.py --database /data/app.db
```

Pozytywny wynik:

```text
Migration completed: /data/app.db
schema_kind: legacy_scraper
schema_version: 4
integrity_check: ok
foreign_key_issues: 0
```

## Sprawdzenie integralności po migracji

W tym samym kontenerze pomocniczym albo innym kontrolowanym środowisku uruchom:

```bash
python -c "import sqlite3; db='/data/app.db'; c=sqlite3.connect(db); c.execute('PRAGMA foreign_keys=ON'); print(c.execute('PRAGMA integrity_check').fetchone()[0]); print(c.execute('PRAGMA foreign_key_check').fetchall())"
```

Pozytywny wynik:

```text
ok
[]
```

Maksymalny punkt przerwania: jeżeli wynik nie jest `ok` albo lista `foreign_key_check` nie jest pusta, nie uruchamiaj usług aplikacji. Przejdź do rollbacku bazy.

## Uruchomienie usług

1. Usuń albo zatrzymaj jednorazowy kontener pomocniczy, jeżeli nadal istnieje.
2. W Portainerze otwórz produkcyjny stack.
3. Uruchom `web` / `arena-web`.
4. Poczekaj na `healthy`, jeżeli Portainer pokazuje healthcheck.
5. Uruchom `scraper` / `arena-scraper`.
6. Sprawdź logi `arena-web`.
7. Sprawdź logi `arena-scraper`.

Pozytywne wyniki:

- dashboard ładuje listę wydarzeń;
- logi `arena-web` nie zawierają błędów `schema version`, `no such table`, `foreign key constraint failed`;
- logi `arena-scraper` pokazują start schedulera;
- pierwszy run scrapera kończy się podsumowaniem `found`, `valid`, `rejected`, `created`, `updated`;
- brak błędów `database is locked`.

## Test aplikacji

1. Otwórz dashboard przez aktualny adres produkcyjny.
2. Wejdź w szczegóły istniejącego wydarzenia.
3. Sprawdź, czy historia dostępności ładuje wykres.
4. Zaloguj się jako administrator.
5. Wejdź w `Panel Admina`.
6. Sprawdź listę źródeł i listę wydarzeń.
7. Nie wykonuj testowych zmian produkcyjnych, jeżeli nie są potrzebne.

DO WERYFIKACJI W PORTAINERZE: rzeczywisty publiczny adres dashboardu, ponieważ repozytorium nie zawiera konfiguracji ingress Cloudflare Tunnel.

## Rollback

Rollback bazy:

1. Zatrzymaj `scraper` / `arena-scraper`.
2. Zatrzymaj `web` / `arena-web`.
3. Zachowaj awaryjną kopię aktualnych plików `app.db*` po nieudanej migracji.
4. Sprawdź backup docelowy komendą `PRAGMA integrity_check`; wynik musi być `ok`.
5. Odtwórz backup jako `/data/app.db` w tym samym wolumenie `pifpaf-data`.
6. Usuń `/data/app.db-wal` i `/data/app.db-shm` tylko przy zatrzymanych `scraper` i `web`.
7. Przywróć poprzednią wersję kodu/obrazu stacka, jeżeli nowy kod wymaga kanonicznego schematu.
8. Uruchom `web`.
9. Uruchom `scraper`.

Rollback kodu:

1. Nie zmieniaj nazw usług, portów, wolumenów ani sieci.
2. W Portainerze przywróć poprzedni commit/tag albo poprzednią zawartość stacka zgodnie z aktualnym sposobem wdrażania.
3. Wykonaj rebuild/redeploy istniejącego stacka.

DO WERYFIKACJI W PORTAINERZE: czy produkcyjny stack jest utrzymywany z Git, Web editor, czy uploadu Compose.

## Czego nie wolno robić

- Nie uruchamiaj migracji bez zweryfikowanego backupu.
- Nie uruchamiaj migracji, gdy `scraper` albo `web` nadal działa.
- Nie zmieniaj nazwy wolumenu `pifpaf-data`.
- Nie zmieniaj ścieżki `/data/app.db`.
- Nie zmieniaj `docker-compose.yml` tylko po to, aby wykonać migrację.
- Nie używaj `docker-compose.test.yml` przeciw produkcyjnemu wolumenowi.
- Nie kopiuj aktywnej bazy zwykłym `cp`.
- Nie ignoruj `Unsupported SQLite schema`.
- Nie usuwaj tabel `*_legacy_before_migration` ręcznie podczas tego etapu.

PORTAINER: brak zmian konfiguracji. Migrację należy wykonać kontrolowaną komendą na istniejącym obrazie i istniejącym wolumenie po backupie.
