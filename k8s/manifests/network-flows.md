# EchoKey network flows

## Required flows

| Source | Destination | Protocol / port | Purpose |
| --- | --- | --- | --- |
| Ingress controller | API Pods | TCP/8000 | Route external HTTP requests to the FastAPI application. |
| API Pods | PostgreSQL Service / Pods | TCP/5432 | Store recordings and transcription results. |
| API Pods | Redis Service / Pods | TCP/6379 | Health check and Celery broker/result backend access. |
| Celery worker Pods | PostgreSQL Service / Pods | TCP/5432 | Read and update recording status and transcripts. |
| Celery worker Pods | Redis Service / Pods | TCP/6379 | Consume Celery tasks and use the result backend. |
| API Pods | CoreDNS | UDP/53, TCP/53 | Resolve PostgreSQL and Redis Service DNS names. |
| Celery worker Pods | CoreDNS | UDP/53, TCP/53 | Resolve PostgreSQL and Redis Service DNS names. |

## Flows that are intentionally absent

- PostgreSQL is not exposed through Ingress.
- Redis is not exposed through Ingress.
- Celery worker has no Service because it accepts no inbound HTTP traffic.

## Pending NFS storage flow

The API and Celery worker must mount the same `/app/uploads` directory so the
worker can read WAV files saved by the API. This will use NFS-backed
`ReadWriteMany` storage. At the application level, both components use file
paths; underneath, NFS storage traffic crosses the network between Kubernetes
nodes and the future NFS server.

The NFS endpoint, protocol version, required ports, and resulting
`NetworkPolicy` rules remain undecided until the NFS design is implemented.

## Pending model-download flow

The future Vosk initContainer needs outbound HTTPS access only while the model
is missing from its volume. The model source must be chosen before this flow is
enforced with NetworkPolicy.

```
Native EchoKey client
        |
        | HTTP
        v
host localhost:8080
        |
        | kind port mapping
        v
Ingress controller
        |
        | Ingress rule
        v
API Service
        |
        v
FastAPI API Pod                              Celery worker Pod
   |        |                                |
   |        | TCP/5432                       | TCP/5432
   |        v                                |
   |  PostgreSQL Service                     |
   |        |                                |
   |        v                                |
   |  PostgreSQL Pod + PVC                   |
   |                                         | TCP/6379
   v                                         |
Redis Service <--------------------------+
   |
   v
Redis Pod + PVC

FastAPI API Pod ------- mounts -------+
                                      |
                                      v
                    /app/uploads (future NFS-backed RWX storage)
                                      ^
                                      |
Celery worker Pod ----- mounts --------+
   |
   | Vosk model volume
   v
Vosk initContainer
(downloads model if absent)

FastAPI API Pod -----------+
                           | DNS: UDP/TCP 53
Celery worker Pod ---------+
                           v
                        CoreDNS
```
