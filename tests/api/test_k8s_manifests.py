"""Tests for T10 — K8s Deployment manifests.

Covers structural validation of generated YAML files.
No cluster required — purely offline checks.
"""

from __future__ import annotations

import pathlib

import yaml

_MANIFEST_DIR = pathlib.Path(__file__).parent.parent.parent / "deploy" / "k8s"


_REQUIRED_FILES = [
    "namespace.yaml",
    "serviceaccount.yaml",
    "configmap.yaml",
    "secret.yaml",
    "deployment.yaml",
    "service.yaml",
    "ingress.yaml",
    "hpa.yaml",
    "networkpolicy.yaml",
    "kustomization.yaml",
]


def _load_manifest(name: str):
    path = _MANIFEST_DIR / name
    with path.open("r", encoding="utf-8") as f:
        return list(yaml.safe_load_all(f))


def test_all_manifests_exist():
    for name in _REQUIRED_FILES:
        assert (_MANIFEST_DIR / name).exists(), f"missing {name}"


def test_namespace_is_uar():
    docs = _load_manifest("namespace.yaml")
    assert any(d.get("metadata", {}).get("name") == "uar" for d in docs)


def test_deployment_has_probes():
    docs = _load_manifest("deployment.yaml")
    deploy = [d for d in docs if d.get("kind") == "Deployment"][0]
    container = deploy["spec"]["template"]["spec"]["containers"][0]
    assert "livenessProbe" in container
    assert "readinessProbe" in container
    live = container["livenessProbe"]["httpGet"]["path"]
    ready = container["readinessProbe"]["httpGet"]["path"]
    assert live == "/api/health/live"
    assert ready == "/api/health/ready"


def test_deployment_security_context():
    docs = _load_manifest("deployment.yaml")
    deploy = [d for d in docs if d.get("kind") == "Deployment"][0]
    pod_sec = deploy["spec"]["template"]["spec"]["securityContext"]
    assert pod_sec["runAsNonRoot"] is True
    assert pod_sec["runAsUser"] == 999


def test_deployment_resource_limits():
    docs = _load_manifest("deployment.yaml")
    deploy = [d for d in docs if d.get("kind") == "Deployment"][0]
    container = deploy["spec"]["template"]["spec"]["containers"][0]
    assert "resources" in container
    assert "requests" in container["resources"]
    assert "limits" in container["resources"]


def test_serviceaccount_no_auto_mount():
    docs = _load_manifest("serviceaccount.yaml")
    sa = [d for d in docs if d.get("kind") == "ServiceAccount"][0]
    assert sa.get("automountServiceAccountToken") is False


def test_hpa_has_cpu_and_memory():
    docs = _load_manifest("hpa.yaml")
    hpa = [d for d in docs if d.get("kind") == "HorizontalPodAutoscaler"][0]
    metrics = hpa["spec"]["metrics"]
    names = [m["resource"]["name"] for m in metrics]
    assert "cpu" in names
    assert "memory" in names


def test_networkpolicy_has_policy_types():
    docs = _load_manifest("networkpolicy.yaml")
    np = [d for d in docs if d.get("kind") == "NetworkPolicy"][0]
    assert "Ingress" in np["spec"]["policyTypes"]
    assert "Egress" in np["spec"]["policyTypes"]


def test_ingress_has_tls():
    docs = _load_manifest("ingress.yaml")
    ing = [d for d in docs if d.get("kind") == "Ingress"][0]
    assert "tls" in ing["spec"]
    assert ing["spec"]["tls"][0]["hosts"][0] == "uar.example.com"
