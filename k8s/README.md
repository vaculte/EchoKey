# EchoKey on local Kubernetes

This directory contains the manually verified Kubernetes deployment used for
the EchoKey v0.1 local lab. It runs the backend inside a three-node kind
cluster while the microphone, global hotkey, and text-insertion client remain
native on the Linux host.

```text
native client -> HTTPS/Traefik -> API -> PostgreSQL
                                  |
                                  +-> Redis -> Celery worker -> Vosk
                                  |
                                  +-> shared uploads PVC <- worker
```

This is a single-host development environment, not a highly available
production deployment. The kind nodes are Docker containers, local-path
volumes belong to individual kind nodes, and the shared uploads volume depends
on an NFS service on the physical host.

## Verified versions

| Component | Version |
| --- | --- |
| Kubernetes node image | `kindest/node:v1.36.1` |
| Calico | `v3.32.1` |
| Traefik chart | `41.4.0` |
| Traefik application | `v3.7.12` |
| EchoKey image | `ghcr.io/vaculte/echokey:df1ff3ce2467cab6f6740b7cb704fa59de30d6fc` |

## Host prerequisites

Install Docker, kind, kubectl, Helm, mkcert, and the NFS client/server tools
required by the host OS. Configure the host-backed shared uploads directory
before applying its PV and PVC. The complete NFS configuration, verification,
recovery limits, and rollback procedure are documented in
[`platform/host-nfs/README.md`](platform/host-nfs/README.md).

The TLS certificate and Kubernetes Secrets are local state and are never
committed. The ignored file `manifests/01-secret.local.yaml` must provide the
following keys in Secret `echokey-dev/echokey-secrets`:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `REDIS_PASSWORD`
- `DATABASE_URL`
- `REDIS_URL`

## Cluster and platform components

Create the cluster:

```bash
kind create cluster \
  --name k8s-echokey \
  --config k8s/kind/create-cluster.yaml
```

Install Calico with the Pod CIDR and VXLAN settings tracked in this repository:

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

Install Traefik on the control-plane node. The values use `hostPort` rather
than a Traefik Service and redirect host port `8080` to trusted HTTPS on
`8443` through the mappings in the kind configuration.

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

## Application resources

Apply the namespace, local Secret, ConfigMap, data services, and storage in
order:

```bash
kubectl apply -f k8s/manifests/00-namespace.yaml
kubectl apply -f k8s/manifests/01-secret.local.yaml
kubectl apply -f k8s/manifests/02-configmap.yaml
kubectl apply -f k8s/manifests/10-postgres-pvc.yaml
kubectl apply -f k8s/manifests/11-postgres-services.yaml
kubectl apply -f k8s/manifests/12-postgres-statefulset.yaml
kubectl apply -f k8s/manifests/20-redis-pvc.yaml
kubectl apply -f k8s/manifests/21-redis-services.yaml
kubectl apply -f k8s/manifests/22-redis-deployment.yaml
kubectl apply -f k8s/manifests/30-uploads-pv.yaml
kubectl apply -f k8s/manifests/31-uploads-pvc.yaml
kubectl apply -f k8s/manifests/32-vosk-model-pvc.yaml
kubectl apply -f k8s/manifests/40-api-deployment.yaml
kubectl apply -f k8s/manifests/41-api-service.yaml
kubectl apply -f k8s/manifests/43-worker-deployment.yaml
```

The model PVC uses the local `standard` StorageClass with
`WaitForFirstConsumer`. It can remain Pending until the worker Pod is
scheduled on `k8s-echokey-worker2`. The worker init container then downloads
the Russian Vosk model only when it is absent from the PVC.

## Local TLS and Ingress

Create and trust a local CA once, then issue a certificate for the development
hostname:

```bash
mkcert -install
ECHOKEY_TLS_DIR=$(mktemp -d /tmp/echokey-tls.XXXXXX)
mkcert \
  -cert-file "$ECHOKEY_TLS_DIR/tls.crt" \
  -key-file "$ECHOKEY_TLS_DIR/tls.key" \
  echokey-dev.localhost
kubectl create secret tls api-tls \
  --namespace echokey-dev \
  --cert="$ECHOKEY_TLS_DIR/tls.crt" \
  --key="$ECHOKEY_TLS_DIR/tls.key"
kubectl apply -f k8s/manifests/42-api-ingress.yaml
```

Do not place the leaf private key or the mkcert root CA private key in Git.
Configure the ignored `client/.env` with the API URL and the public root CA
certificate used by Python/httpx:

```env
ECHOKEY_API_URL=https://echokey-dev.localhost:8443
ECHOKEY_CA_CERT=/absolute/path/from/mkcert-CAROOT/rootCA.pem
```

`mkcert -CAROOT` prints the directory containing `rootCA.pem`.

## Verification

Check the workloads and storage:

```bash
kubectl get pods,pvc -n echokey-dev -o wide
kubectl get pods -n traefik -o wide
```

Verify the HTTPS route and dependency readiness:

```bash
curl -i https://echokey-dev.localhost:8443/health
curl -i https://echokey-dev.localhost:8443/ready
curl -iL http://echokey-dev.localhost:8080/health
```

Inspect model initialization and follow Celery tasks:

```bash
kubectl logs -n echokey-dev deployment/worker -c download-vosk-model
kubectl logs -n echokey-dev deployment/worker -c worker --follow
```

The final v0.1 verification is a real recording from the native client. A
successful run creates the recording with HTTP 201, moves its state from
`pending` to `completed`, logs a successful Celery task, and pastes the
non-empty transcript into the focused field.

## Recovery boundary

If the kind Docker containers are stopped but still exist, start the three
known nodes and wait for Kubernetes to recover:

```bash
docker start \
  k8s-echokey-control-plane \
  k8s-echokey-worker \
  k8s-echokey-worker2
kubectl wait --for=condition=Ready nodes --all --timeout=180s
kubectl wait --for=condition=Ready pods --all --all-namespaces --timeout=240s
```

The Vosk model and local database volumes survived this node-container
stop/start in the verified environment. Recreating the kind cluster is a
different operation and can destroy local-path data. The host NFS upload data
has its own recovery rules documented in the host-NFS guide.

## Next checkpoints

The manual application deployment is verified end to end. The remaining
learning path continues with API probes, an EchoKey Helm chart, two-release
dev/prod isolation, NetworkPolicies, and recovery automation. The detailed
order and completion criteria live in the local `K8S_CHECKLIST.md`.
