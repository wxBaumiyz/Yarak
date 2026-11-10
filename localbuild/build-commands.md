<!-- SPDX-License-Identifier: MIT -->
# biletado lokal builden & deployen (kind + podman) — alles in diesem Ordner

Alles in **PowerShell** aus dem Repo-Root ausfuehren.
Nur die reinen Commands ohne Erklaerung: `build-commands.txt` im selben Ordner.

> **Wichtig:** In PowerShell sind `podman.exe` / `kind.exe` Windows-Programme → nur Windows-Pfade nutzen (`$env:TEMP`, `.\...`), nie `/tmp/...` (das ging nur aus der Git Bash, weil MSYS Pfade konvertiert).

Inhalt dieses Ordners:

| Datei | Zweck |
|---|---|
| `build-commands.md` | diese Anleitung |
| `build-commands.txt` | nur die Commands |
| `kind-config.yaml` | kind-Cluster-Config (Host-Port 9090 → Node 80) |
| `kustomization.yaml` | lokales Overlay: beltado-Basis + `localhost/yarak-reservations:v4` mit `imagePullPolicy: Never` |

## 0) venv, Lint, Tests (vor dem Build)

```powershell
cd reservations
python -m venv .venv
.\.venv\Scripts\pip.exe install --require-hashes -r requirements-dev.txt   # Lockfile, hash-verifiziert
.\.venv\Scripts\pip.exe install --no-deps -e .                              # das Projekt selbst
.\.venv\Scripts\ruff.exe check .                                            # Lint
.\.venv\Scripts\python.exe -m pytest -q                                    # Tests
cd ..
```

## 1) Cluster anlegen / pruefen

```powershell
$env:KIND_EXPERIMENTAL_PROVIDER = "podman"   # nur falls nicht auto-erkannt
kind create cluster --name kind-cluster --config localbuild/kind-config.yaml
kind get clusters
kubectl config current-context                 # erwartet: kind-kind-cluster
```

## 2) reservations-Image bauen

Das Image installiert die Dependencies hash-verifiziert aus dem Lockfile
(`uv pip compile --universal --generate-hashes`, siehe `reservations/Containerfile`):

```powershell
podman build -t localhost/yarak-reservations:v4 -f reservations/Containerfile reservations/
podman images                                  # Image muss gelistet sein
```

## 3) Image in den kind-Node laden

`kind load docker-image` schlaegt mit podman-Provider fehl ("not present locally", root-vs-rootless-Store) → immer der save/image-archive-Workaround (steht auch in `biletado/kustomize/Readme.md`):

```powershell
podman save localhost/yarak-reservations:v4 --format oci-archive -o "$env:TEMP\res-v4.tar"
kind load image-archive "$env:TEMP\res-v4.tar" --name kind-cluster
# Check, ob es im Node angekommen ist:
podman exec kind-cluster-control-plane ctr -n k8s.io images ls | Select-String yarak
```

## 4) Kustomize deployen (lokales Image)

`localbuild/kustomization.yaml` zieht die beltado-Basis (`overlays/kind`, remote) und patcht das
`reservations`-Deployment auf `localhost/yarak-reservations:v4` mit `imagePullPolicy: Never`
(Image kommt aus dem Node, nicht aus einer Registry):

```powershell
kubectl create namespace beltado
kubectl apply -k localbuild/ -n beltado
kubectl get pods -n beltado -w                 # 7 Pods: postgres, keycloak, assets, reservations, jwt-pong, frontend, zudoku
```

**Registry-Variante** (CI-Image `ghcr.io/wxbaumiyz/yarak:latest` statt lokalem Build):
`kubectl apply -k kustomization/ -n beltado` (siehe `kustomization/kustomization.yaml` im Repo-Root).

## 5) API testen

Direkt ohne Ingress (port-forward auf den Service):

```powershell
kubectl port-forward svc/reservations -n beltado 9000:80
curl http://localhost:9000/api/v4/reservations/health
curl http://localhost:9000/api/v4/reservations/health/ready
curl http://localhost:9000/api/v4/reservations/status
curl http://localhost:9000/openapi.json
```

Ueber Ingress auf `http://localhost:9090` (Host-Port-Mapping aus `kind-config.yaml`; Routing laeuft ueber den Pfad, Ingress-Host ist `*`). Der ingress-nginx-Controller ist **nicht** im Repo — einmalig installieren:

```powershell
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
curl http://localhost:9090/api/v4/reservations/health
```

## 6) Rebuild nach Code-Aenderung

Gleicher Tag `v4` + `imagePullPolicy: Never` → `rollout restart` noetig, sonst merkt der Cluster das neue Image nicht:

```powershell
podman build -t localhost/yarak-reservations:v4 -f reservations/Containerfile reservations/
podman save localhost/yarak-reservations:v4 --format oci-archive -o "$env:TEMP\res-v4.tar"
kind load image-archive "$env:TEMP\res-v4.tar" --name kind-cluster
kubectl rollout restart deployment/reservations -n beltado
kubectl get pods -n beltado -w
```

## 7) Logs / Debug

```powershell
kubectl logs -n beltado deployment/reservations -f
kubectl describe pod -n beltado -l app.kubernetes.io/name=reservations
# Pods sind NICHT in "podman ps" sichtbar (da sieht man nur den kind-Node-Container) —
# in den Node reinschauen:
podman exec kind-cluster-control-plane crictl ps
```

## 8) Aufraeumen

```powershell
kubectl delete -k localbuild/ -n beltado     # alle Ressourcen aus dem Namespace entfernen
kind delete cluster --name kind-cluster        # Cluster komplett loeschen
```
