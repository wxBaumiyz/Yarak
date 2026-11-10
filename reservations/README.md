<!-- SPDX-License-Identifier: MIT -->
# biletado-reservations-v4 (yarak as rest api kubernetes)

Backend für die REST-Schnittstelle **biletado/reservations-v4**
(OpenAPI-Spec: `../reservations-v4.yaml`, Upstream: gitlab.com/biletado/apidocs `specs/v4/reservations-v4.yaml`).

- **Sprache/Framework:** Python 3.12, FastAPI + Uvicorn
- **Datenbank:** SQLAlchemy (ORM, parametrisierte Statements) + asyncpg gegen Postgres; lokal/tests auch sqlite möglich
- **Auth:** JWT-Signaturprüfung via JWKS des Keycloak-Realms (`KEYCLOAK_HOST`/`KEYCLOAK_REALM`)
- **Lizenz:** MIT (siehe `../LICENSE`)

## API

Basis-Pfad: `/api/v4/reservations`

| Endpunkt | Auth | Beschreibung |
|---|---|---|
| `GET /status` | nein | Autoren + implementierte API-Version |
| `GET /status/auth` | ja | HTTP 204 bei gültigem JWT, sonst 401 |
| `GET /health`, `/health/live`, `/health/ready` | nein | ready inkl. DB + assets-`health/live` |
| `GET /public-reservations` (`room_id`, `before`, `after`) | nein | nie gelöschte Reservierungen |
| `POST /public-reservations` | nein | anlegen (409 bei Overlap, 400 bei ungültig/unbekanntem Raum) |
| `GET /public-reservations/{id}` | nein | 404 wenn nicht vorhanden/gelöscht |
| `GET /reservations` (`include_deleted`, `room_id`, `before`, `after`) | ja | Liste inkl. gelöschter |
| `POST /reservations` | ja | anlegen, 201 + `Location` + `ETag` |
| `GET /reservations/{id}` | ja | 200 + `ETag` (auch gelöschte mit `deleted_at`) |
| `PUT /reservations/{id}` | ja | ersetzen/anlegen (201)/wiederherstellen (`deleted_at: null`); `If-Match` → 412 bei Abweichung; 409 bei Overlap oder gelöscht ohne Restore |
| `DELETE /reservations/{id}` (`permanent`, `If-Match`) | ja | soft delete (204), `permanent=true` löscht endgültig, 404 wenn (schon) gelöscht |

Fehlerantworten entsprechen dem `ErrorContainer`-Schema (`errors[].code`, `trace`).
`from` muss strikt vor `to` liegen (400 `invalid_date_range`); die Existenz des Raums wird
über die assets-API geprüft (`GET {ASSETS_API_HOST}/api/v3/assets/rooms/{id}` → 400 `room_not_found`).
Überlappende Reservierungen desselben Raums werden mit 409 `overlapping_reservation` abgelehnt
(angrenzende mit `to == from` sind erlaubt).

## Konfiguration (Umgebungsvariablen)

| Variable | Default | Bedeutung |
|---|---|---|
| `PORT` | `9000` | HTTP-Port des Service |
| `DATABASE_URL` | – | komplette SQLAlchemy-URL; überschreibt die POSTGRES_*-Variablen (z.B. `sqlite+aiosqlite:///...` lokal) |
| `POSTGRES_RESERVATIONS_HOST` | `localhost` | DB-Host (im Cluster: `postgres`) |
| `POSTGRES_RESERVATIONS_PORT` | `5432` | DB-Port |
| `POSTGRES_RESERVATIONS_USER` | `postgres` | DB-User |
| `POSTGRES_RESERVATIONS_PASSWORD` | `postgres` | DB-Passwort |
| `POSTGRES_RESERVATIONS_DBNAME` | `reservations_v4` | DB-Name |
| `ASSETS_API_HOST` | `http://assets` | Basis-URL des assets-Service (Raum-Check + health/live) |
| `ASSETS_API_PREFIX` | `/api/v3/assets` | Pfad-Präfix der assets-API |
| `ASSETS_TIMEOUT_SECONDS` | `5` | Timeout für assets-Requests |
| `KEYCLOAK_SCHEME` / `KEYCLOAK_HOST` / `KEYCLOAK_REALM` | `http` / `keycloak` / `biletado` | JWKS liegen unter `{scheme}://{host}{KEYCLOAK_PATH_PREFIX}/realms/{realm}/protocol/openid-connect/certs` |
| `KEYCLOAK_PATH_PREFIX` | `/auth` | Pfad-Präfix des Keycloak in der Umgebung (KC_HTTP_RELATIVE_PATH) |
| `JWT_JWKS_URL` | – | überschreibt die JWKS-URL komplett |
| `JWT_JWKS_JSON` | – | inline-JWKS (z.B. für Tests), hat Vorrang vor der URL |
| `JWT_ISSUER` | – | optional: `iss`-Claim zusätzlich prüfen |
| `LOG_LEVEL` | `INFO` | Loglevel |
| `LOG_FORMAT` | `text` | `text` oder `json` |
| `CORS_ALLOW_ORIGINS` | `*` | komma-getrennte Origins |
| `API_VERSION` | `4.1.1` | in `/status` reported |
| `AUTHORS` | Gruppenmitglieder | komma-getrennt, in `/status` reported |

## Abhaengigkeiten (Lockfiles & Renovate)

- Deklariert werden die Abhaengigkeiten in `pyproject.toml` (`project.dependencies` = Runtime,
  `project.optional-dependencies.dev` = Tests/Lint).
- Daraus generated sind die **Lockfiles** `requirements.txt` (Runtime) und `requirements-dev.txt`
  (Runtime + Dev) via `uv pip compile --universal --generate-hashes`: jede Version ist exakt gepinnt (`==`) und
  mit **sha256-Hashes** aller Release-Artefakte versehen (universell: inkl. Linux-only-Paketen wie
  `uvloop` mit Platform-Markern). Installiert wird hash-verifiziert mit
  `pip install --require-hashes -r requirements-dev.txt`. Das Container-Image installiert die
  Runtime-Deps ebenfalls hash-verifiziert aus `requirements.txt` (siehe `Containerfile`).
- Regenerieren nach Aenderung an `pyproject.toml`:
  `uv pip compile --universal --generate-hashes --python-version 3.12 pyproject.toml -o requirements.txt` bzw.
  `uv pip compile --universal --generate-hashes --python-version 3.12 --extra dev pyproject.toml -o requirements-dev.txt`

  (immer `--universal`! Ohne Marker fehlen z. B. Linux-only-Dependencies wie `uvloop` im Lock und
  `pip install --require-hashes` schlaegt dann auf Linux/CI fehl)
- **Renovate** (`../renovate.json` im Repo-Root) aktualisiert Upstream-Dependencies automatisch
  (pyproject.toml + Lockfiles, Docker-Basisimage wird auf Digest gepinnt) und oeffnet dafuer PRs.

## Lokal starten

```sh
python -m venv .venv
# Lockfile mit sha256-Hashes installieren (dev = Runtime + pytest/ruff), dann das Projekt selbst:
.venv/bin/pip install --require-hashes -r requirements-dev.txt   # bzw. Scripts\pip.exe auf Windows
.venv/bin/pip install --no-deps -e .
DATABASE_URL="sqlite+aiosqlite:///./dev.db" \
ASSETS_API_HOST="http://localhost:9090" \
uvicorn app.main:app --port 9000
```

## Tests

```sh
python -m pytest        # public API, Auth/JWT, Schreibzugriffe, ETag (If-Match/412 + If-None-Match/304), Audit-Logging, Health
ruff check .            # Linting (laeuft auch in der CI)
```

Zusaetzlich laufen die offiziellen httpyac-Integrationstests aus `../biletado/apidocs/httpyac`
(`400`–`560_*_v4.http`) gegen ein lokales kind-Cluster; die Antworten werden dabei zur
Laufzeit gegen die OpenAPI-Spec validiert:

```sh
podman run --rm --network host registry.gitlab.com/biletado/apidocs/httpyac:latest \
  send '400_ReadReservationsPublic-v4.http' '500_WriteReservationsPublic-v4.http' \
       '510_CreateReservationsPublic-v4.http' '550_ReadWriteReservationsAuth-v4.http' \
       '560_ReadWriteReservationsETag-v4.http' --all
# in CI: siehe .github/workflows/ci.yml (Jobs lint/test/build im GitHub-Repo)
```

Hinweise zur Spec-Konformitaet:

- 404-Antworten nutzen den Error-Code `deleted_reservation` (das ErrorContainer-Enum der
  Spec kennt keinen `not_found`-Code).
- `include_deleted`/`permanent` werden als String gelesen: nur exakt `true` aktiviert,
  jeder andere Wert (z. B. `maybe`) ist false bzw. Soft-Delete.
- Der ETag ist ein schwacher Validator (`W/"..."`), damit er die gzip-Kompression des
  Envoy-Ingress der biletado-Umgebung ueberlebt. Er wird bei GET/POST/PUT als `ETag`-Header
  geliefert; `If-Match` auf PUT/DELETE liefert bei Abweichung 412, `If-None-Match` auf GET bei
  Gleichstand 304 (Not Modified).

## Container-Image

Die GitHub Actions CI (`.github/workflows/ci.yml` im Repo-Root, Jobs `lint` / `test` / `build`)
baut das Image mit podman und pusht es nach `ghcr.io/wxbaumiyz/yarak` (Tags: Commit-SHA und
`latest`). Lokal:

```sh
podman build -t ghcr.io/wxbaumiyz/yarak:latest -f Containerfile .
# ins kind-Cluster laden:
podman save ghcr.io/wxbaumiyz/yarak:latest --format oci-archive -o reservations.tar
kind load image-archive reservations.tar -n kind-cluster
```

Deployment im Cluster: siehe `../kustomization/kustomization.yaml` (patcht das `reservations`-Deployment
aus `biletado/kustomize/overlays/kind` auf dieses Image).
**Lokal builden + in kind deployen** (kind-Cluster, lokales Image, alles in einem Ordner):
siehe `../localbuild/build-commands.md` bzw. nur die Commands in `../localbuild/build-commands.txt`.

## Logging

Neben den Uvicorn-Access-Logs schreibt der Service eigene, nachvollziehbare Logs
(`LOG_LEVEL`, `LOG_FORMAT=text|json`; bei JSON eine Zeile pro Eintrag inkl. aller Extra-Felder):

- **Audit-Log** (`app.audit`): jede nicht-lesende Operation (create/replace/delete) wird mit
  Operation, Objekttyp, Objekt-Id, User-Id (`sub` aus dem JWT, sonst `anonymous`) und **Details**
  geloggt - also was der User konkret gemacht hat (beim Anlegen Name/Raum/Zeitraum, beim
  Ersetzen die geaenderten Felder als `{feld: [alt, neu]}`, beim Loeschen das `permanent`-Flag).
  Abgelehnte Schreibzugriffe (z. B. 412 `etag_mismatch`, 409 `overlapping_reservation`) werden
  als WARNING mit Methode, Pfad, Status, Error-Code und User-Id protokolliert.
- **Request-Id**: pro HTTP-Request wird eine `X-Request-ID` vergeben (eine vorhandene wird
  uebernommen) und in jedem Logeintrag als Feld `request_id` mitgefuehrt, sodass sich alle
  Eintraege einem Request zuordnen lassen. Die Id steht auch im Response-Header.
