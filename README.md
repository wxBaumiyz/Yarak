<!-- SPDX-License-Identifier: MIT -->
# yarak — reservations-v4 Backend (biletado)

Repo der Gruppe **yarak as rest api kubernetes**: Python-3.12/FastAPI-Backend fuer die
REST-API `biletado/reservations-v4` — inkl. Containerfile, Kustomize-Overlay, CI und lokalem
kind-Setup. Lizenz: MIT (siehe `LICENSE`).

## Aufbau

| Pfad | Inhalt |
|---|---|
| `reservations/` | Der Service selbst (FastAPI + Uvicorn, SQLAlchemy/asyncpg, JWT via Keycloak-JWKS). API, Config, Lockfiles, Tests, Logging: siehe [`reservations/README.md`](reservations/README.md) |
| `kustomization/` | Kustomize-Overlay fuer das Deployment: patcht das `reservations`-Deployment der beltado-Umgebung auf das CI-Image `ghcr.io/wxbaumiyz/yarak` |
| `localbuild/` | Alles fuer lokales Bauen & Deployen in kind (podman): Anleitung `build-commands.md`, reine Commands `build-commands.txt`, `kind-config.yaml`, lokales `kustomization.yaml` |
| `.github/workflows/ci.yml` | CI: `lint` (ruff) + `test` (pytest) aus dem hash-gepinnten Lockfile, `build` (podman -> ghcr.io) |
| `.github/workflows/renovate.yml` | Self-hosted Renovate (Fallback; alternativ die Renovate-GitHub-App installieren) |
| `renovate.json` | Renovate-Config: pyproject + Lockfiles (via `uv pip compile --universal --generate-hashes`) + Docker-Basisimage auf sha256-Digest gepinnt |
| `biletado/` | Referenz-Submodule: `apidocs` (OpenAPI-Specs + offizielle httpyac-Tests), `kustomize` (biletado-Umgebung) |

## Quickstart (lokal)

```powershell
git submodule update --init                 # beltado/apidocs + beltado/kustomize
cd reservations
python -m venv .venv
.\.venv\Scripts\pip.exe install --require-hashes -r requirements-dev.txt
.\.venv\Scripts\pip.exe install --no-deps -e .
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\python.exe -m pytest -q
```

Lokales kind-Deployment inkl. httpyac-Integrationstests (alles im Container, kein npm):
siehe [`localbuild/build-commands.md`](localbuild/build-commands.md).

## CI/CD & Images

- Jeder Push/PR triggert `.github/workflows/ci.yml`: **lint -> test -> build**. Das Image landet als `ghcr.io/wxbaumiyz/yarak:<commit-sha>` und `:latest`.
- **Renovate** (`renovate.json`) eroeftnet PRs fuer Dependency-Updates (pyproject + Lockfiles via `uv pip compile --universal --generate-hashes`, Docker-Basisimage auf Digest); patch/minor werden nach gruener CI automatisch gemergt, major bleibt PR zur Review.
- Deployen im Cluster: `kubectl apply -k kustomization/ -n beltado` (CI-Image) bzw. lokal `kubectl apply -k localbuild/ -n beltado` (lokal gebautes Image).

## Lizenz

MIT — siehe `LICENSE`. Jede Quell-/Config-Datei traegt ausserdem einen SPDX-Header
(`SPDX-License-Identifier: MIT`).
