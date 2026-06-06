# UAR Kubernetes Deployment

T10 — Production-ready K8s manifests for the Universal Agent Runtime.

## Quick Start

```bash
# Edit secret values first!
vim secret.yaml

# Deploy everything
kubectl apply -k deploy/k8s/

# Or with kustomize directly
kustomize build deploy/k8s/ | kubectl apply -f -
```

## Components

| Resource           | Purpose                                      |
|--------------------|----------------------------------------------|
| `namespace.yaml`   | Isolates UAR workloads                       |
| `serviceaccount.yaml` | Least-privilege identity (no auto-mount token) |
| `configmap.yaml`   | Non-sensitive env vars (pool mode, metrics, audit) |
| `secret.yaml`      | Encryption key, API keys, DB/Redis URLs        |
| `deployment.yaml`  | UAR API with rolling updates, probes, topology spread |
| `service.yaml`     | ClusterIP for internal routing                 |
| `ingress.yaml`     | TLS + nginx ingress (customize host)           |
| `hpa.yaml`         | CPU/memory autoscaling (2–10 replicas)         |
| `networkpolicy.yaml` | Default-deny + explicit allow rules          |

## Required Changes Before Deploying

1. **Image** — Update `kustomization.yaml` `images.newName` to your registry.
2. **Secrets** — Replace placeholder values in `secret.yaml`.
3. **Ingress host** — Change `uar.example.com` in `ingress.yaml`.
4. **TLS issuer** — Update `cert-manager.io/cluster-issuer` annotation.

## Security Defaults

- Runs as non-root user (`uar`, UID 999)
- `readOnlyRootFilesystem: false` (required for `/app/runs` emptyDir)
- Drops all Linux capabilities
- `automountServiceAccountToken: false`
- NetworkPolicy blocks intra-cluster CIDR egress by default
