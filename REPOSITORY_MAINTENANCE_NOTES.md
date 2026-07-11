# Repository Maintenance Notes

## Active production code

According to `docker-compose.yml` and `DEPLOYMENT_BASELINE.md`, production builds only these application contexts:

- scraper: `./arena-dashboard/scraper`
- web: `./arena-dashboard/web`

The production SQLite path remains:

```text
/data/app.db
```

mounted from the named volume:

```text
pifpaf-data:/data
```

## Legacy root-level files

The following root-level files are not referenced by the production `docker-compose.yml` build contexts and should be treated as legacy until separately reviewed:

- `Dockerfile`
- `main.py`
- `page.tsx`
- `requirements.txt`
- `package-lock.json`
- `SubmitButton.tsx`

They were not removed in this stage because the request explicitly requires avoiding deletion until production usage is confirmed. Future cleanup should either delete them in a dedicated change or move any still-useful content into the active `arena-dashboard/scraper` or `arena-dashboard/web` trees.

## Runtime files

Runtime SQLite files, WAL/SHM sidecars, `.env*` files except `.env.example`, Python bytecode and TypeScript build info must not be tracked.

CI enforces this with:

```bash
python tools/ci_repo_guard.py --hygiene
```
