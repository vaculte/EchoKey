# Host NFS storage for EchoKey uploads

EchoKey uses an NFS export from the physical Linux host as shared upload
storage for the local multi-node kind cluster. The API writes WAV files and
the Celery worker reads the same files even when their Pods run on different
kind workers.

Kubernetes does not install, configure, monitor, resize, replicate, back up,
or remove this host NFS data. This is a local lab design, not highly available
storage.

## Final layout and ownership

```text
/srv/echokey/uploads                 NFSv4 root (fsid=0)
├── echokey-dev                      -> echokey-dev-uploads PV -> echokey-dev/uploads PVC
└── echokey-prod                     -> echokey-prod-uploads PV -> echokey-prod/uploads PVC
```

The API and worker each receive only their environment's mounted directory at
`/app/uploads`; they never see the parent export or the sibling environment.
The kubelet on each kind node performs the NFS mount, so application
containers do not themselves connect to TCP/2049.

| Setting | Value |
| --- | --- |
| Host OS | Arch Linux |
| Host package | `nfs-utils` |
| NFS service | `nfs-server.service` |
| NFS export root | `/srv/echokey/uploads` |
| Environment directories | `echokey-dev`, `echokey-prod`, each `1000:0`, mode `0700` |
| Application UID | `1000` |
| kind Docker IPv4 subnet | `172.21.0.0/16` |
| Host gateway seen by kind nodes | `172.21.0.1` |
| NFS protocol | NFSv4.1 over TCP/2049 |

The gateway and subnet are properties of Docker's `kind` network. Check them
again after recreating that network or the cluster.

## Host setup

Install the NFS utilities on the Arch Linux host:

```bash
sudo pacman -S nfs-utils
```

Create one private directory for each Helm environment:

```bash
sudo install -d -o 1000 -g 0 -m 0700 /srv/echokey/uploads/echokey-dev
sudo install -d -o 1000 -g 0 -m 0700 /srv/echokey/uploads/echokey-prod
```

Determine the current kind network rather than assuming the recorded address:

```bash
docker network inspect kind \
  --format '{{range .IPAM.Config}}{{.Subnet}} gateway={{.Gateway}}{{println}}{{end}}'
```

Export the parent directory to the verified Docker subnet in `/etc/exports`:

```exports
/srv/echokey/uploads 172.21.0.0/16(rw,sync,root_squash,no_subtree_check,fsid=0)
```

`fsid=0` makes the parent the NFSv4 root. Therefore the dev and prod PVs use
`/echokey-dev` and `/echokey-prod`, not physical host paths. Keep the export
restricted to the kind Docker subnet; do not use `*` or `no_root_squash`.

Reload the export and enable the service:

```bash
sudo exportfs -rav
sudo systemctl enable --now nfs-server.service
```

## Kubernetes boundary

The static storage objects are external Helm prerequisites:

- [`30-uploads-dev-pv.yaml`](../../manifests/30-uploads-dev-pv.yaml) and
  [`31-uploads-dev-pvc.yaml`](../../manifests/31-uploads-dev-pvc.yaml);
- [`33-uploads-prod-pv.yaml`](../../manifests/33-uploads-prod-pv.yaml) and
  [`34-uploads-prod-pvc.yaml`](../../manifests/34-uploads-prod-pvc.yaml).

Each PV is `ReadWriteMany`, has an empty storage class, and uses reclaim policy
`Retain`. Each namespaced PVC explicitly binds through `volumeName`. The
declared `2Gi` is a binding value, not a quota on the host filesystem.

```bash
kubectl get pv echokey-dev-uploads echokey-prod-uploads
kubectl get pvc uploads -n echokey-dev
kubectl get pvc uploads -n echokey-prod
```

All four resources must be `Bound`. This proves binding, not usable I/O; the
two Helm releases and a native-client transcription are the end-to-end check.

## Failure and recovery limits

- If `nfs-server.service` is unavailable, new Pods can remain in
  `ContainerCreating` with mount errors. Restore the service and inspect Pod
  Events before recreating workloads.
- Restarting an API or worker Pod does not remove uploads.
- Deleting a `Retain` PV or PVC does not remove the host directory; rebinding
  and cleanup remain manual responsibilities.
- Recreating the kind network can change the subnet or gateway. Update both
  `/etc/exports` and the static PVs only after rechecking those values.
- The host is a single failure domain with no replication, automatic backup,
  or enforced 2 GiB quota.

Before destructive storage changes, stop the API and worker, preserve required
files, and keep the two environment directories separate.
