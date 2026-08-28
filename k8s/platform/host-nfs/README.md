# Host NFS storage for EchoKey uploads

EchoKey uses an NFS export from the physical Linux host as the shared upload
filesystem for the local multi-node kind cluster. The FastAPI API writes WAV
files to this share and the Celery worker reads the same files, even when the
two Pods run on different kind worker nodes.

This is a local lab design, not a production or highly available storage
service. Kubernetes does not install, configure, monitor, resize, replicate,
back up, or remove the host NFS data.

## Storage path

```text
FastAPI Pod on worker 1 ----+
                            | PVC uploads (RWX)
Celery Pod on worker 2 -----+
                            |
                            v
                  PV echokey-dev-uploads
                            |
                            | NFSv4.1 to 172.21.0.1:/
                            v
          /srv/echokey/uploads/echokey-dev on the host
```

The kubelet on each kind worker node performs the NFS mount. The application
containers receive an already-mounted directory at `/app/uploads`; they do
not connect to TCP/2049 themselves.

## Verified local configuration

| Setting | Value |
| --- | --- |
| Host OS | Arch Linux |
| Host package | `nfs-utils 2.9.2-1` |
| NFS service | `nfs-server.service`, enabled and active |
| Host directory | `/srv/echokey/uploads/echokey-dev` |
| Application UID | `1000` |
| kind Docker IPv4 subnet | `172.21.0.0/16` |
| Host gateway seen by kind nodes | `172.21.0.1` |
| NFS protocol | NFSv4.1 over TCP/2049 |
| Kubernetes PV | `echokey-dev-uploads` |
| Kubernetes PVC | `echokey-dev/uploads` |

The gateway and subnet survived ordinary kind node container stops and
starts. They are properties of the Docker `kind` network and must be checked
again if that network or the kind cluster is recreated.

## Host setup

Install the NFS utilities manually on the Arch Linux host:

```bash
sudo pacman -S nfs-utils
```

Create a dedicated directory owned by the non-root user from the shared
backend/worker image:

```bash
sudo install -d -o 1000 -g 0 -m 0700 /srv/echokey/uploads/echokey-dev
```

Both application containers use UID 1000, so the setup relies on user
ownership rather than a shared group. The NFS export uses `root_squash`; a
client process with GID 0 can therefore create files whose group is mapped to
`nobody`, while UID 1000 remains the file owner.

Determine the current kind network instead of assuming that the recorded
addresses are still correct:

```bash
docker network inspect kind \
  --format '{{range .IPAM.Config}}{{.Subnet}} gateway={{.Gateway}}{{println}}{{end}}'
```

Add this single export to `/etc/exports` for the verified IPv4 subnet:

```exports
/srv/echokey/uploads/echokey-dev 172.21.0.0/16(rw,sync,root_squash,no_subtree_check,fsid=0)
```

The export is deliberately restricted to the kind Docker subnet. Do not
replace it with `*`, the Kubernetes Pod CIDR, or `no_root_squash` without a
demonstrated requirement.

Reload the exports and enable the NFS service:

```bash
sudo exportfs -rav
sudo systemctl enable --now nfs-server.service
```

`fsid=0` makes this directory the NFSv4 export root. For that reason the
Kubernetes PV uses `path: /`, not the physical host path.

## Host verification

Check the active export, service state, and listener:

```bash
sudo exportfs -v
systemctl is-enabled nfs-server.service
systemctl is-active nfs-server.service
sudo ss -ltn 'sport = :2049'
```

Both kind workers must be able to reach the host listener:

```bash
for node in k8s-echokey-worker k8s-echokey-worker2; do
  docker exec "$node" \
    bash -c 'timeout 3 bash -c "echo > /dev/tcp/172.21.0.1/2049" && echo NFS-reachable'
done
```

Each worker also needs an NFS mount helper. The current kind nodes provide
`/usr/sbin/mount.nfs` through `nfs-utils 2.8.3`:

```bash
for node in k8s-echokey-worker k8s-echokey-worker2; do
  printf '%s: ' "$node"
  docker exec "$node" sh -c 'command -v mount.nfs || command -v mount.nfs4'
done
```

Change the host firewall only when a connectivity test proves that it blocks
the required worker-node-to-host TCP/2049 path. Pod `NetworkPolicy` resources
do not control this mount traffic because it originates from the node's
kubelet, outside the application Pod network namespace.

## Kubernetes resources and verification

The static storage objects are defined in:

- [`30-uploads-pv.yaml`](../../manifests/30-uploads-pv.yaml)
- [`31-uploads-pvc.yaml`](../../manifests/31-uploads-pvc.yaml)

The PV has `ReadWriteMany`, an empty storage class, and reclaim policy
`Retain`. The PVC explicitly binds to it through
`volumeName: echokey-dev-uploads`. The declared `2Gi` capacity participates in
PV/PVC binding but does not enforce a quota on the host filesystem.

Verify the binding:

```bash
kubectl get pv echokey-dev-uploads
kubectl get pvc uploads -n echokey-dev
```

Both resources must report `Bound`. This proves only Kubernetes binding, not
that an NFS mount works.

The mount was verified with temporary non-root Pods using UID 1000:

1. A Pod pinned to `k8s-echokey-worker` wrote a file through the `uploads`
   PVC.
2. The file appeared under the physical host export directory.
3. A Pod pinned to `k8s-echokey-worker2` read and appended to the same file.
4. The data remained after the temporary Pods were deleted.
5. After the kind node containers were stopped and started, the PV/PVC stayed
   `Bound` and new client Pods mounted the share and completed another
   cross-node write/read/modify test. The earlier test file had been removed
   manually, so that run did not test persistence of one specific file across
   the node-container stop/start.

Temporary verification manifests live only under the ignored `k8s/tmp/`
directory and must not be deployed as application workloads.

## Failure and recovery boundaries

- If `nfs-server.service` is unavailable, new Pods can remain in
  `ContainerCreating` with mount errors. Restore the host service and inspect
  Pod Events before recreating workloads.
- Stopping or recreating an API or worker Pod does not remove upload files.
- Deleting the PVC or the `Retain` PV does not delete the host directory.
  Rebinding and eventual host cleanup are manual responsibilities.
- Recreating the kind Docker network can change the subnet or gateway. Update
  `/etc/exports` and the static PV only after discovering and verifying the
  new values.
- The physical host is the single failure domain. The share has no NFS server
  redundancy, storage replication, automatic backup, or enforced 2 GiB quota.
- Use separate host directories and static PV/PVC pairs for development and
  production-like Helm releases. They must not share upload data accidentally.

## Rollback

Before rollback, stop workloads that use the `uploads` PVC and preserve any
files that are still required.

1. Remove the EchoKey export line from `/etc/exports`.
2. Reload the export table with `sudo exportfs -rav`.
3. Disable the service only if the host has no other NFS consumers or exports:

   ```bash
   sudo systemctl disable --now nfs-server.service
   ```

4. Remove `nfs-utils` only if no other host workload needs it:

   ```bash
   sudo pacman -Rns nfs-utils
   ```

The rollback intentionally does not delete
`/srv/echokey/uploads/echokey-dev`. Data removal is a separate, explicit, and
potentially destructive operation.
