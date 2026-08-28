# EchoKey network flows

This document defines the traffic EchoKey needs before namespaced Calico
`NetworkPolicy` resources are enforced. A Kubernetes Service provides a
stable DNS name and virtual IP; policy ultimately permits traffic to the
selected destination Pods.

Do not apply a namespace-wide default-deny policy until the complete manual
stack is healthy and each flow below has a matching tested rule.

## Application request and task flow

1. The native Linux client uploads a WAV file to the FastAPI API through the
   future Ingress endpoint.
2. The API writes the WAV file to `/app/uploads`, creates its PostgreSQL row,
   and publishes a Celery task through Redis.
3. The Celery worker consumes the task from Redis, reads the same WAV file
   from `/app/uploads`, runs Vosk, and updates the PostgreSQL row.
4. The native client polls the API for the stored status and transcript.

The API does not open a direct connection to the worker. Redis carries the
task message, PostgreSQL carries recording state, and the shared filesystem
carries the WAV file.

## Pod network flows

| Source | Destination | Protocol / port | Purpose |
| --- | --- | --- | --- |
| Ingress controller Pods | FastAPI API Pods | TCP/8000 | Forward external HTTP requests selected by the API Service. |
| FastAPI API Pods | PostgreSQL Pods through `postgres` Service | TCP/5432 | Create and query recordings and health-check PostgreSQL. |
| FastAPI API Pods | Redis Pods through `redis` Service | TCP/6379 | Publish Celery tasks and health-check Redis. |
| Celery worker Pods | PostgreSQL Pods through `postgres` Service | TCP/5432 | Read and update recording status and transcripts. |
| Celery worker Pods | Redis Pods through `redis` Service | TCP/6379 | Consume Celery tasks and use the result backend. |
| FastAPI API Pods | CoreDNS Pods | UDP/53, TCP/53 | Resolve the `postgres` and `redis` Service names. |
| Celery worker and init-container Pods | CoreDNS Pods | UDP/53, TCP/53 | Resolve internal Services and the future Vosk model source. |
| Vosk init container | Chosen model host | TCP/443 | Download the model only when it is absent from the model volume. |

The exact Vosk model host has not been selected yet. Its HTTPS rule must be
scoped after the download source and init-container implementation are
verified; it must not become unrestricted permanent egress by accident.

## Host NFS storage flow

The shared upload volume is not served by a Kubernetes Pod or Service. The
physical Arch Linux host exports
`/srv/echokey/uploads/echokey-dev` through NFSv4.1. Static PV
`echokey-dev-uploads` represents that export, and PVC `echokey-dev/uploads`
binds application Pods to it.

For every Pod mount, kubelet on the selected worker node connects to the host:

```text
kubelet on kind worker node
        |
        | NFSv4.1, TCP/2049
        v
172.21.0.1:/
        |
        v
/srv/echokey/uploads/echokey-dev on the physical host
```

The kubelet then exposes the mounted filesystem inside the application
container at `/app/uploads`. The API and worker processes perform ordinary
file operations against that mount; they do not establish their own NFS
connections.

An ordinary namespaced Pod `NetworkPolicy` does not authorize or deny this
node-to-host mount traffic because it originates outside the application Pod
network namespace. Restrict it with the host `/etc/exports` client subnet and,
only if needed, a host firewall rule for TCP/2049. The verified local export is
limited to the kind Docker subnet `172.21.0.0/16`.

## Intentionally absent flows

- PostgreSQL and Redis are not exposed through Ingress or host port mappings.
- The Celery worker has no Service because it accepts no inbound application
  traffic.
- There is no direct FastAPI-to-worker connection.
- PostgreSQL and Redis do not initiate connections to API or worker Pods.
- There is no NFS Pod, Service, controller, or application-Pod NFS egress
  rule.
- The desktop client does not connect directly to API Pod IPs.

## End-to-end diagram

```text
Native EchoKey client
        |
        | HTTP to localhost:8080
        v
kind host-port mapping
        |
        v
Ingress controller -> API Service -> FastAPI API Pod
                                      |      |      |
                           TCP/5432   |      |      | TCP/6379
                                      v      |      v
                              PostgreSQL     |    Redis Service
                                Service      |      |
                                   |         |      v
                                   v         |    Redis Pod + RWO PVC
                           PostgreSQL Pod    |            ^
                               + RWO PVC     |            |
                                   ^         |            | TCP/6379
                                   |         |            |
                                   |         v            |
                                   +--- Celery worker Pod-+
                                      TCP/5432 |
                                               |
                                               v
                                        Vosk model volume

FastAPI API Pod ------ mounts ------+
                                     |
                                     v
                         /app/uploads through RWX PVC
                                     ^
                                     |
Celery worker Pod ---- mounts -------+

RWX PVC -> static NFS PV -> worker kubelet -> host NFS export

FastAPI API Pod -----------+
                           | DNS: UDP/TCP 53
Celery worker Pod ---------+
                           v
                        CoreDNS
```
