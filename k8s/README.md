# EchoKey on local Kubernetes

EchoKey is deployed in this local v0.1 lab as two isolated Helm releases:
`echokey-dev` in `echokey-dev` and `echokey-prod` in `echokey-prod`. The
microphone, global hotkey, and text-insertion client remain native on the
Linux host.

```text
native client -> HTTPS/Traefik -> API -> PostgreSQL
                                  |
                                  +-> Redis -> Celery worker -> Vosk
                                  |
                                  +-> environment-specific NFS uploads PVC
```

This is a single-host development environment, not a highly available
production deployment. The kind nodes are Docker containers, local-path
volumes belong to individual kind nodes, and shared uploads depend on NFS on
the physical host.

## Verified versions

| Component | Version |
| --- | --- |
| Kubernetes node image | `kindest/node:v1.36.1` |
| Calico | `v3.32.1` |
| Traefik chart | `41.4.0` |
| Traefik application | `v3.7.12` |
| EchoKey image | `ghcr.io/vaculte/echokey:5739ae9e99c71074499de3322359b5de1db7d4d8` |

## Host and cluster prerequisites

Install Docker, kind, kubectl, Helm, mkcert, and the NFS client/server tools
required by the host OS. Configure host-backed uploads before applying their
static PVs and PVCs. The complete NFS layout, export, verification, and
limitations are in [`platform/host-nfs/README.md`](platform/host-nfs/README.md).

The chart intentionally does not create any of the following environment
prerequisites:

- the namespace;
- `echokey-secrets` with database and Redis credentials;
- the `api-tls` TLS Secret; or
- the static NFS PV and its namespaced `uploads` PVC.

They contain host-specific or secret state and must exist before Helm is run.
The tracked manifests create the two namespaces and static uploads storage;
credentials and TLS material stay local and out of Git. Each
`echokey-secrets` Secret must provide `POSTGRES_DB`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `DATABASE_URL`, and `REDIS_URL`.

## Cluster platform

Create the cluster:

```bash
kind create cluster \
  --name k8s-echokey \
  --config k8s/kind/create-cluster.yaml
```

Install Calico:

```bash
helm repo add projectcalico https://docs.tigera.io/calico/charts
helm upgrade --install calico projectcalico/tigera-operator \
  --version v3.32.1 \
  --namespace tigera-operator \
  --create-namespace \
  --values k8s/platform/calico/values.yaml \
  --wait \
  --timeout 5m
```

Install Traefik on the control-plane node. The tracked values use `hostPort`
instead of a Traefik Service and redirect host port `8080` to HTTPS on `8443`
through the kind port mappings.

```bash
helm repo add traefik https://traefik.github.io/charts
helm upgrade --install traefik traefik/traefik \
  --version 41.4.0 \
  --namespace traefik \
  --create-namespace \
  --values k8s/platform/traefik/values.yaml \
  --skip-crds \
  --wait \
  --timeout 5m
```

## Create external environment resources

Apply each namespace and its dedicated uploads PV/PVC pair. The two PVs mount
different NFSv4 paths, so development and production recordings cannot mix.

```bash
kubectl apply -f k8s/manifests/00-namespace-dev.yaml
kubectl apply -f k8s/manifests/30-uploads-dev-pv.yaml
kubectl apply -f k8s/manifests/31-uploads-dev-pvc.yaml

kubectl apply -f k8s/manifests/00-namespace-prod.yaml
kubectl apply -f k8s/manifests/33-uploads-prod-pv.yaml
kubectl apply -f k8s/manifests/34-uploads-prod-pvc.yaml
```

Create `echokey-secrets` in both namespaces from local, untracked credential
files. Create and trust a local CA once, then create a TLS Secret in each
namespace. This single certificate covers both local environment hostnames:

```bash
mkcert -install
ECHOKEY_TLS_DIR=$(mktemp -d /tmp/echokey-tls.XXXXXX)
mkcert \
  -cert-file "$ECHOKEY_TLS_DIR/tls.crt" \
  -key-file "$ECHOKEY_TLS_DIR/tls.key" \
  echokey-dev.localhost echokey-prod.localhost

for namespace in echokey-dev echokey-prod; do
  kubectl -n "$namespace" create secret tls api-tls \
    --cert="$ECHOKEY_TLS_DIR/tls.crt" \
    --key="$ECHOKEY_TLS_DIR/tls.key" \
    --dry-run=client -o yaml | kubectl apply -f -
done
```

The native client must trust the mkcert root CA and use the matching HTTPS URL.

```env
ECHOKEY_API_URL=https://echokey-dev.localhost:8443
ECHOKEY_CA_CERT=/absolute/path/from/mkcert-CAROOT/rootCA.pem
```

`mkcert -CAROOT` prints the directory containing `rootCA.pem`. Set
`ECHOKEY_API_URL=https://echokey-prod.localhost:8443` to use production.

## Install or update EchoKey

The chart owns the application workloads, ConfigMap, Ingress, and local
PostgreSQL, Redis, and Vosk PVCs. `values.yaml` is the shared local baseline;
the environment overlays currently differ only in Ingress hostname.

```bash
helm upgrade --install echokey-dev charts/echokey \
  --namespace echokey-dev \
  --values charts/echokey/values-dev.yaml \
  --wait \
  --timeout 10m

helm upgrade --install echokey-prod charts/echokey \
  --namespace echokey-prod \
  --values charts/echokey/values-prod.yaml \
  --wait \
  --timeout 10m
```

Do not use `--take-ownership` to convert manually created application
resources. The verified dev migration deliberately rebuilt chart-owned
resources while retaining the external namespace, NFS uploads PVC/PV,
credentials Secret, and TLS Secret.

## Verification

```bash
helm list --all-namespaces
kubectl get pods,pvc -n echokey-dev
kubectl get pods,pvc -n echokey-prod

curl -fsS https://echokey-dev.localhost:8443/ready
curl -fsS https://echokey-prod.localhost:8443/ready
```

Both readiness responses should be:

```json
{"status":"ok","database":true,"redis":true}
```

Then run the native client with the matching `ECHOKEY_API_URL`. A successful
recording returns HTTP 201, is polled from `pending` to `completed`, and pastes
the non-empty transcript into the focused field.

Fresh installations can restart the API while PostgreSQL first opens port
`5432`; Kubernetes then restarts it and the release becomes healthy. This is
an observed cold-start limitation of the current lab, not an alternate
deployment path.

## Uninstall boundary

`helm uninstall` removes chart-owned application resources, including the
local PostgreSQL, Redis, and Vosk PVC objects. It does not remove the external
NFS uploads PV/PVC, the host files, credentials, or TLS Secrets. Preserve or
remove those external resources separately and deliberately.
