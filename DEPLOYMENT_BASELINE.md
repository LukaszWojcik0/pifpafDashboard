# Deployment Baseline

Ten dokument opisuje aktualny kontrakt wdrożeniowy aplikacji `pifpafDashboard` wynikający z plików w repozytorium. Jego celem jest ochrona działającego wdrożenia Docker/Portainer przed przypadkowymi zmianami podczas kolejnych etapów prac.

## Zakres analizy

Przeanalizowane pliki:

- `docker-compose.yml`
- `docker-compose.test.yml`
- `Dockerfile`
- `arena-dashboard/web/Dockerfile`
- `arena-dashboard/scraper/Dockerfile`
- `.dockerignore`
- `arena-dashboard/web/.dockerignore`
- `arena-dashboard/scraper/.dockerignore`
- `README.md`
- kod inicjalizacji bazy w `arena-dashboard/scraper/db.py` i `arena-dashboard/web/app/db.ts`

W repozytorium nie znaleziono pliku `.env.example` ani osobnego dokumentu opisującego wszystkie zmienne środowiskowe poza `README.md` i deklaracjami w Compose.

## Model wdrożenia produkcyjnego

Produkcja jest opisana przez `docker-compose.yml`.

Usługi:

- `vpn`
  - obraz: `qmcgaw/gluetun`
  - `container_name`: `gluetun`
  - restart: `always`
  - posiada `NET_ADMIN` i urządzenie `/dev/net/tun:/dev/net/tun`
  - publikuje port hosta `${WEB_PORT:-8088}` na port `3000/tcp` w przestrzeni sieciowej VPN
  - montuje named volume `gluetun-data` jako `/gluetun`

- `scraper`
  - build z `./arena-dashboard/scraper/Dockerfile`
  - `container_name`: `arena-scraper`
  - restart: `unless-stopped`
  - montuje named volume `pifpaf-data` jako `/data`
  - używa `DATABASE_PATH=/data/app.db`
  - działa z `network_mode: "service:vpn"`
  - `depends_on: [vpn]`

- `web`
  - build z `./arena-dashboard/web/Dockerfile`
  - `container_name`: `arena-web`
  - restart: `unless-stopped`
  - montuje named volume `pifpaf-data` jako `/data`
  - używa `DATABASE_PATH=/data/app.db`
  - używa `HOSTNAME=0.0.0.0`
  - działa z `network_mode: "service:vpn"`
  - `depends_on: [vpn]`
  - healthcheck sprawdza `http://127.0.0.1:3000/api/ready` z wnętrza współdzielonej przestrzeni sieciowej

- `cloudflared`
  - obraz: `cloudflare/cloudflared:latest`
  - `container_name`: `cloudflare-tunnel`
  - restart: `unless-stopped`
  - komenda: `tunnel run`
  - używa `TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}`

## Wolumeny i baza danych

W `docker-compose.yml` zadeklarowane są named volumes:

- `pifpaf-data`
- `gluetun-data`

Kontrakt bazy produkcyjnej:

- kontenerowa ścieżka bazy: `/data/app.db`
- zmienna: `DATABASE_PATH=/data/app.db`
- wolumen z bazą: `pifpaf-data`
- usługi korzystające z tej samej bazy: `scraper` i `web`

Rzeczywista nazwa wolumenu w Dockerze/Portainerze może mieć prefiks projektu albo stacka, np. w formacie `<stack>_pifpaf-data`. Repozytorium nie przesądza tej nazwy dla produkcji.

DO WERYFIKACJI W PORTAINERZE: rzeczywista nazwa wolumenu odpowiadającego deklaracji `pifpaf-data`.

SQLite:

- `web` otwiera bazę przez `better-sqlite3` i ustawia `PRAGMA journal_mode = WAL`.
- `scraper` używa standardowego modułu `sqlite3`.
- aktywna baza może mieć pliki pomocnicze `app.db-wal` i `app.db-shm`.
- backup aktywnej bazy nie powinien polegać na zwykłym kopiowaniu samego `app.db`.

## Sieć i komunikacja usług

`scraper` i `web` używają:

```yaml
network_mode: "service:vpn"
```

To oznacza, że współdzielą przestrzeń sieciową kontenera `vpn` (`gluetun`). Port dashboardu jest wystawiany przez usługę `vpn`, a nie bezpośrednio przez `web`.

Istotne elementy Gluetun:

- `VPN_SERVICE_PROVIDER=privatevpn`
- `VPN_TYPE=openvpn`
- `OPENVPN_USER=${VPN_USER}`
- `OPENVPN_PASSWORD=${VPN_PASSWORD}`
- `SERVER_COUNTRIES=Poland`
- `OPENVPN_PROTOCOL=udp`
- `OPENVPN_ENDPOINT_PORT=1194`
- `FIREWALL_VPN_INPUT_PORTS=3000`
- `FIREWALL_OUTBOUND_SUBNETS=172.16.0.0/12,192.168.0.0/16,10.0.0.0/8`
- `TZ=Europe/Warsaw`

Nie należy przypadkowo zmieniać sposobu komunikacji przez Gluetun ani przenosić mapowania portu z `vpn` na `web`.

## Porty

Produkcja:

- host: `${WEB_PORT:-8088}`
- kontener/przestrzeń Gluetun: `3000/tcp`
- aplikacja Next.js: `3000`

Healthcheck `web` używa `http://127.0.0.1:3000/api/ready`.

Test:

- `vpn-test` mapuje `"8099:3000/tcp"`

## Cloudflare Tunnel

W repozytorium usługa `cloudflared` uruchamia:

```yaml
command: tunnel run
```

i pobiera token z:

```yaml
TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}
```

Repozytorium nie zawiera konfiguracji ingress tunelu, nazwy tunelu ani reguł routingu po stronie Cloudflare.

DO WERYFIKACJI W PORTAINERZE: czy zmienna `CLOUDFLARE_TUNNEL_TOKEN` jest ustawiona w stacku.

DO WERYFIKACJI W PORTAINERZE: jaki hostname i jaki service/URL docelowy są skonfigurowane po stronie Cloudflare Tunnel.

## Budowanie obrazów

Produkcja buduje dwa lokalne obrazy:

- `scraper`
  - context: `./arena-dashboard/scraper`
  - Dockerfile: `Dockerfile`
  - base image: `python:3.11-slim`
  - instaluje `requirements.txt`
  - uruchamia `python main.py`

- `web`
  - context: `./arena-dashboard/web`
  - Dockerfile: `Dockerfile`
  - build stage: `node:20-alpine`
  - runner stage: `node:20-alpine`
  - instaluje zależności przez `npm install`
  - buduje `npm run build`
  - uruchamia `node server.js`
  - `EXPOSE 3000`

Root `Dockerfile` istnieje, ale nie jest wskazany przez `docker-compose.yml`. Nie należy zakładać, że bierze udział w aktualnym wdrożeniu Portainer, jeśli stack używa pliku Compose z repozytorium.

## Zmienne środowiskowe

Zmienne użyte przez produkcyjny Compose:

- `WEB_PORT`, domyślnie `8088`
- `VPN_USER`, wymagane przez Gluetun
- `VPN_PASSWORD`, wymagane przez Gluetun
- `SCRAPE_INTERVAL_MINUTES`, domyślnie `10`
- `NTFY_URL`
- `ALERT_ON_FIRST_RUN`, domyślnie `false`
- `CLOUDFLARE_TUNNEL_TOKEN`

Zmienne ustawiane bezpośrednio w Compose:

- `DATABASE_PATH=/data/app.db`
- `HOSTNAME=0.0.0.0`
- `TZ=Europe/Warsaw`
- zmienne Gluetun wymienione w sekcji sieci

DO WERYFIKACJI W PORTAINERZE: wartości zmiennych stacka oraz miejsce ich utrzymywania w Portainerze.

## Konfiguracja testowa

`docker-compose.test.yml` definiuje osobny model testowy:

- wolumeny `pifpaf-test-data` i `gluetun-test-data`
- `pifpaf-prod-data` jako wolumen zewnętrzny o nazwie `pifpaf-dashboard_pifpaf-data`
- `db-seed` montuje wolumen produkcyjny jako read-only pod `/prod` i kopiuje `/prod/app.db*` do wolumenu testowego
- `vpn-test`, `scraper-test`, `web-test`
- port testowy `8099:3000/tcp`

Uwaga: komentarz w `docker-compose.test.yml` mówi, że nazwę wolumenu produkcyjnego trzeba zmienić na rzeczywistą nazwę z Portainera. Ten plik nie powinien być używany przeciw aktywnej produkcji bez wcześniejszego zapewnienia spójnego backupu albo zatrzymania usług korzystających z bazy.

## Aktualizacja stacka

README opisuje aktualizację przez:

```bash
docker-compose up -d --build
```

W Portainerze odpowiednikiem jest ponowne wdrożenie/aktualizacja stacka z przebudową obrazów zgodnie z aktualnym sposobem obsługi stacka. Repozytorium nie zawiera eksportu konfiguracji Portainera.

DO WERYFIKACJI W PORTAINERZE: czy stack jest wdrażany z repozytorium Git, z Web editor, czy przez upload pliku Compose.

DO WERYFIKACJI W PORTAINERZE: czy Portainer przy aktualizacji wykonuje pull/build automatycznie, czy wymaga ręcznego przycisku aktualizacji.

## Elementy niezmienne dla kolejnych zmian

Kolejne etapy nie powinny przypadkowo zmieniać:

- nazw usług: `vpn`, `scraper`, `web`, `cloudflared`
- nazw kontenerów: `gluetun`, `arena-scraper`, `arena-web`, `cloudflare-tunnel`
- named volumes: `pifpaf-data`, `gluetun-data`
- montowania `pifpaf-data:/data` w `scraper` i `web`
- ścieżki produkcyjnej bazy: `/data/app.db`
- zmiennej `DATABASE_PATH=/data/app.db`
- `network_mode: "service:vpn"` dla `scraper` i `web`
- publikowania portu dashboardu przez `vpn`
- mapowania `${WEB_PORT:-8088}:3000/tcp`
- `FIREWALL_VPN_INPUT_PORTS=3000`
- konfiguracji Gluetun i PrivateVPN
- sposobu uruchamiania Cloudflare Tunnel przez `cloudflared` i `TUNNEL_TOKEN`
- `depends_on` na `vpn`
- restart policies
- build contexts i Dockerfile dla `scraper` oraz `web`
- aktualnego sposobu wdrażania stacka w Portainerze

## Ryzyka operacyjne

- Kopiowanie aktywnej bazy SQLite w trybie WAL przez zwykłe `cp app.db` może dać niespójną kopię.
- Kopiowanie `app.db`, `app.db-wal` i `app.db-shm` zwykłym `cp` jest dopuszczalne tylko po zatrzymaniu wszystkich procesów korzystających z bazy.
- `web` może zapisywać do bazy, ponieważ inicjalizuje tabele użytkowników/sesji i ustawia WAL.
- `docker-compose.test.yml` zawiera mechanizm kopiowania `/prod/app.db*`; nie należy używać go jako backupu aktywnej produkcji.
- Rzeczywista nazwa wolumenu produkcyjnego nie wynika jednoznacznie z repozytorium i musi być sprawdzona w Portainerze.
- Konfiguracja Cloudflare Tunnel poza tokenem nie jest w repozytorium.
