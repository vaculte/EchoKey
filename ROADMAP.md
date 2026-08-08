# EchoKey DevOps Roadmap

Self-hosted, local-cluster oriented. No managed-cloud services assumed.

## Containerization

- [ ] Write Dockerfile for backend API (FastAPI)
- [ ] Write Dockerfile for Celery worker
- [ ] Write docker-compose.yml for local stack (API, worker, Postgres, Redis)

## CI/CD

- [ ] Add GitHub Actions workflow: lint + test backend on pull request
- [ ] Add GitHub Actions workflow: build and push backend + worker images on merge to main
- [ ] Add GitHub Actions workflow: run client tests on pull request

## K8s

- [ ] Create namespace and base manifest structure
- [ ] Add Secret for database credentials and API settings
- [ ] Add ConfigMap for non-sensitive environment variables
- [ ] Add Deployment + Service + Ingress for backend API with health probes
- [ ] Add Deployment for Celery worker with init container to download Vosk model
- [ ] Add PostgreSQL StatefulSet + Redis Deployment with PVCs

## Monitoring

- [ ] Add /health and /ready endpoints to backend
- [ ] Add Prometheus metrics endpoint to backend
- [ ] Create Grafana dashboard for API latency, errors, and Celery queue depth
