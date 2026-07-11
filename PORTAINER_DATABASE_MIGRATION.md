# Portainer Database Migration

Ta instrukcja zaklada, ze pracujesz w Portainerze na kontenerze pomocniczym z zamontowanym tym samym wolumenem `pifpaf-data` jako `/data`.

Najwazniejsze sciezki:

```text
Baza SQLite: /data/app.db
Katalog backupow: /data/backups
```

Nie trzeba znac sciezki na hoscie. Wystarczy, ze kontener pomocniczy ma zamontowany rzeczywisty wolumen produkcyjny jako `/data`.

PORTAINER: brak zmian konfiguracji stacka. Migracja wymaga tylko rebuild/redeploy obrazu oraz kontrolowanego uruchomienia komend na istniejacym wolumenie.

## 1. Zatrzymaj uslugi zapisujace do SQLite

W Portainerze:

1. `Environments`
2. wybierz srodowisko produkcyjne
3. `Stacks`
4. otworz stack aplikacji
5. zatrzymaj `scraper` / `arena-scraper`
6. zatrzymaj `web` / `arena-web`

Nie musisz zatrzymywac:

- `vpn` / `gluetun`
- `cloudflared` / `cloudflare-tunnel`

DO WERYFIKACJI W PORTAINERZE: nazwa produkcyjnego stacka.

## 2. Sprawdz nazwe wolumenu

W Portainerze:

1. wejdz w `Containers`
2. otworz `arena-scraper` albo `arena-web`
3. wejdz w `Inspect`
4. znajdz `Mounts`
5. odszukaj wpis z:

```text
Destination: /data
```

Zapamietaj wartosc `Name`. To jest rzeczywista nazwa wolumenu Dockera odpowiadajaca `pifpaf-data`.

DO WERYFIKACJI W PORTAINERZE: rzeczywista nazwa wolumenu, zwykle podobna do `<stack>_pifpaf-data`.

## 3. Utworz kontener pomocniczy

W Portainerze:

1. wejdz w `Containers`
2. wybierz `Add container`
3. uzyj aktualnego, przebudowanego obrazu uslugi `scraper`
4. zamontuj rzeczywisty wolumen `pifpaf-data` jako `/data`
5. nie publikuj portow
6. nadpisz domyslna komende startowa, zeby nie uruchamiac `python main.py`
7. siec nie jest potrzebna do backupu ani migracji

Ustaw komende kontenera pomocniczego na:

```bash
sleep 3600
```

Jezeli Portainer ma osobne pola `Command` i `Entrypoint`, uzyj jednej z tych bezpiecznych konfiguracji:

```text
Command: sleep 3600
Entrypoint: zostaw puste
```

albo:

```text
Command: 3600
Entrypoint: sleep
```

Nie uruchamiaj kontenera pomocniczego z domyslna komenda obrazu, bo wtedy wystartuje `main.py` i scraper/scheduler zamiast narzedzi backupu.

DO WERYFIKACJI W PORTAINERZE: dokladna nazwa obrazu uzywanego przez `arena-scraper`.

Jezeli log kontenera pomocniczego pokazuje:

```text
Traceback ... File "/app/main.py"
```

to znaczy, ze kontener wystartowal z domyslna komenda. Usun go i utworz ponownie z komenda `sleep 3600`.

Jezeli komenda backupu zwraca:

```text
python: can't open file '/app/backup_db.py': [Errno 2] No such file or directory
```

to znaczy, ze kontener pomocniczy zostal uruchomiony ze starego obrazu albo z niewlasciwego obrazu. W takim przypadku:

1. usun kontener pomocniczy,
2. wykonaj rebuild/redeploy stacka tak, aby obraz `scraper` zawieral aktualny kod,
3. zatrzymaj ponownie `scraper` i `web`,
4. utworz nowy kontener pomocniczy z aktualnego obrazu `scraper`,
5. zamontuj ten sam wolumen jako `/data`.

Jezeli Portainer po rebuildzie automatycznie uruchomi `arena-scraper` przed migracja, scraper powinien zalogowac:

```text
Database schema requires a controlled migration
```

To jest oczekiwane zabezpieczenie. Zatrzymaj wtedy ponownie `scraper` i upewnij sie, ze `web` tez jest zatrzymany.

## 4. Sprawdz, czy kontener ma aktualne skrypty

Uruchom w kontenerze pomocniczym:

```bash
ls -l /app/backup_db.py /app/check_db.py /app/migrate_db.py /app/restore_db.py
```

Pozytywny wynik: widzisz cztery pliki.

Maksymalny punkt przerwania: jezeli ktoregokolwiek pliku brakuje, nie wykonuj backupu ani migracji w tym kontenerze. Uzywasz starego albo zlego obrazu.

## 5. Backup - komenda do skopiowania

Uruchom te komende w kontenerze pomocniczym:

```bash
python /app/backup_db.py --source /data/app.db --dest-dir /data/backups
```

Pozytywny wynik:

```text
Backup created: /data/backups/app-YYYYMMDD-HHMMSS.db
integrity_check: ok
Metadata written: /data/backups/app-YYYYMMDD-HHMMSS.db.metadata.json
```

Maksymalny punkt przerwania: jezeli nie widzisz `integrity_check: ok`, przerwij operacje i nie uruchamiaj migracji.

## 6. Sprawdz najnowszy backup - komenda do skopiowania

Uruchom:

```bash
python /app/check_db.py --database /data/backups/NAZWA_BACKUPU.db
```

Zamien `NAZWA_BACKUPU.db` na nazwe pliku pokazana w poprzednim kroku, na przyklad:

```bash
python /app/check_db.py --database /data/backups/app-20260711-120000.db
```

Pozytywny wynik:

```text
Database checked: /data/backups/app-YYYYMMDD-HHMMSS.db
integrity_check: ok
foreign_key_check: [...]
```

## 7. Dry-run migracji - komenda do skopiowania

Uruchom:

```bash
python /app/migrate_db.py --database /data/app.db --dry-run
```

Oczekiwany wynik:

```text
Migration plan: /data/app.db
schema_kind: legacy_scraper
schema_version: 4
migrations: 001_create_canonical_schema, 002_migrate_legacy_scraper_schema, 003_migrate_legacy_web_schema, 004_add_constraints_indexes_status
```

`schema_kind` moze byc tez:

- `legacy_web`
- `partial`
- `empty`
- `canonical`

Maksymalny punkt przerwania: jezeli dry-run zwraca `Unsupported SQLite schema`, blad integralnosci, brak `/data/app.db` albo wyglada jak praca na zlym wolumenie, przerwij operacje.

## 8. Migracja - komenda do skopiowania

Po poprawnym backupie i dry-run uruchom:

```bash
python /app/migrate_db.py --database /data/app.db
```

Pozytywny wynik:

```text
Migration completed: /data/app.db
schema_version: 4
integrity_check: ok
foreign_key_issues: 0
```

## 9. Sprawdz baze po migracji - komenda do skopiowania

Uruchom:

```bash
python /app/check_db.py --database /data/app.db --expect-schema-version 4
```

Pozytywny wynik:

```text
Database checked: /data/app.db
integrity_check: ok
foreign_key_check: []
schema_version: 4
```

Maksymalny punkt przerwania: jezeli wynik nie jest `ok`, `foreign_key_check` nie jest `[]` albo `schema_version` nie jest `4`, nie uruchamiaj aplikacji. Wykonaj rollback.

## 10. Uruchom uslugi

W Portainerze:

1. zatrzymaj/usun kontener pomocniczy
2. uruchom `web` / `arena-web`
3. poczekaj na `healthy`, jezeli Portainer pokazuje healthcheck
4. uruchom `scraper` / `arena-scraper`
5. sprawdz logi `arena-web`
6. sprawdz logi `arena-scraper`

Pozytywne wyniki:

- dashboard sie laduje
- szczegoly wydarzenia pokazuja historie
- `arena-web` nie pokazuje `schema version`, `no such table`, `foreign key constraint failed`
- `arena-scraper` startuje scheduler
- pierwszy run scrapera konczy sie podsumowaniem `found`, `valid`, `rejected`, `created`, `updated`

DO WERYFIKACJI W PORTAINERZE: publiczny adres dashboardu, bo konfiguracja ingress Cloudflare Tunnel nie jest w repozytorium.

## 11. Rollback bazy - komendy do skopiowania

Rollback wykonuj tylko przy zatrzymanych:

- `scraper` / `arena-scraper`
- `web` / `arena-web`

Najpierw sprawdz backup:

```bash
python /app/check_db.py --database /data/backups/NAZWA_BACKUPU.db
```

Potem odtworz wybrany backup:

```bash
python /app/restore_db.py --backup /data/backups/NAZWA_BACKUPU.db --database /data/app.db --emergency-dir /data/backups
```

Po rollbacku uruchom:

1. `web` / `arena-web`
2. `scraper` / `arena-scraper`

## Czego nie wolno robic

- Nie uruchamiaj migracji bez backupu.
- Nie uruchamiaj migracji, gdy `scraper` albo `web` dziala.
- Nie zmieniaj nazwy wolumenu.
- Nie zmieniaj `/data/app.db`.
- Nie zmieniaj `docker-compose.yml` dla samej migracji.
- Nie uzywaj `docker-compose.test.yml` przeciw produkcyjnemu wolumenowi.
- Nie kopiuj aktywnej bazy zwyklym `cp`.
- Nie ignoruj `Unsupported SQLite schema`.
- Nie usuwaj tabel `*_legacy_before_migration` recznie podczas tego etapu.
