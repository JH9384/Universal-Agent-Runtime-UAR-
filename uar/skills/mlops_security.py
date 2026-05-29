"""MLOps and security skills for UAR.

Implements security auditing, penetration testing, OSINT reconnaissance,
and MLOps pipeline skills (MLflow, Kubeflow).
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from uar.core.contracts import PipelineContext
from uar.core.registry import register_skill
from uar.core.skill_utils import require_package, skill_guard


@register_skill("security_audit")
@skill_guard("Security Audit")
def security_audit(ctx: PipelineContext) -> Dict[str, Any]:
    """Run security audits with bandit and safety.

    Metadata:
        audit_target:   path to code directory or file (default '.')
        audit_tools:    list of tools: ['bandit', 'safety'] (default both)
        audit_format:   output format: 'json', 'text' (default 'json')
    """
    meta = ctx.goal.metadata or {}
    target = meta.get("audit_target", ".")
    tools = meta.get("audit_tools", ["bandit", "safety"])
    fmt = meta.get("audit_format", "json")

    results: Dict[str, Any] = {}

    if "bandit" in tools:
        bandit_err = require_package("bandit")
        if bandit_err:
            results["bandit"] = bandit_err
        else:
            try:
                cmd = [
                    "bandit", "-r", target,
                    "-f", "json" if fmt == "json" else "txt",
                ]
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=120,
                )
                issues: List[Dict[str, Any]] = []
                if fmt == "json" and proc.stdout:
                    try:
                        parsed = json.loads(proc.stdout)
                        issues = parsed.get("results", [])
                    except json.JSONDecodeError:
                        issues = [{"raw": proc.stdout}]
                else:
                    issues = [{"raw": proc.stdout or proc.stderr}]
                results["bandit"] = {
                    "status": "completed",
                    "issues_count": len(issues),
                    "issues": issues[:50],  # cap output
                    "returncode": proc.returncode,
                }
            except Exception as exc:
                results["bandit"] = {"status": "error", "error": str(exc)}

    if "safety" in tools:
        safety_err = require_package("safety")
        if safety_err:
            results["safety"] = safety_err
        else:
            try:
                req_file = meta.get("requirements_file", "requirements.txt")
                cmd = ["safety", "check", "--file", req_file]
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=120,
                )
                results["safety"] = {
                    "status": "completed",
                    "returncode": proc.returncode,
                    "output": proc.stdout[:5000] if proc.stdout else "",
                    "issues": proc.returncode != 0,
                }
            except Exception as exc:
                results["safety"] = {"status": "error", "error": str(exc)}

    any_error = any(
        isinstance(v, dict) and v.get("status") == "error"
        for v in results.values()
    )
    return {
        "status": "error" if any_error else "completed",
        "tools_run": list(results.keys()),
        "results": results,
    }


@register_skill("pentest_scan")
@skill_guard("Pentest Scan")
def pentest_scan(ctx: PipelineContext) -> Dict[str, Any]:
    """Network penetration testing scan with python-nmap.

    Metadata:
        scan_target:    IP or hostname to scan (default '127.0.0.1')
        scan_ports:     port range string (default '1-1024')
        scan_args:      additional nmap arguments (default '-sV')
    """
    err = require_package("nmap")
    if err:
        return err

    import nmap

    meta = ctx.goal.metadata or {}
    target = meta.get("scan_target", "127.0.0.1")
    ports = meta.get("scan_ports", "1-1024")
    args = meta.get("scan_args", "-sV")

    try:
        scanner = nmap.PortScanner()
        scanner.scan(target, ports, arguments=args)

        hosts: List[Dict[str, Any]] = []
        for host in scanner.all_hosts():
            host_info = {
                "host": host,
                "state": scanner[host].state(),
                "protocols": {},
            }
            for proto in scanner[host].all_protocols():
                ports_info = {}
                for port in scanner[host][proto].keys():
                    p = scanner[host][proto][port]
                    ports_info[port] = {
                        "state": p.get("state"),
                        "name": p.get("name"),
                        "product": p.get("product"),
                        "version": p.get("version"),
                    }
                host_info["protocols"][proto] = ports_info
            hosts.append(host_info)

        return {
            "status": "completed",
            "target": target,
            "hosts_scanned": len(hosts),
            "hosts": hosts,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@register_skill("osint_recon")
@skill_guard("OSINT Recon")
def osint_recon(ctx: PipelineContext) -> Dict[str, Any]:
    """Open-source intelligence reconnaissance.

    Metadata:
        recon_target:   domain or IP to investigate
        recon_tools:    ['whois', 'shodan', 'dns'] (default all)
    """
    meta = ctx.goal.metadata or {}
    target = meta.get("recon_target", "")
    tools = meta.get("recon_tools", ["whois", "dns"])

    if not target:
        return {"status": "failed", "error": "No recon target provided"}

    results: Dict[str, Any] = {}

    if "whois" in tools:
        whois_err = require_package("whois")
        if whois_err:
            # Fallback to socket-based domain info
            try:
                import socket
                ip = socket.gethostbyname(target)
                results["whois"] = {
                    "status": "completed",
                    "domain": target,
                    "ip": ip,
                    "source": "dns_fallback",
                }
            except Exception as exc:
                results["whois"] = {"status": "error", "error": str(exc)}
        else:
            try:
                import whois
                w = whois.whois(target)
                results["whois"] = {
                    "status": "completed",
                    "registrar": w.registrar,
                    "creation_date": str(w.creation_date),
                    "expiration_date": str(w.expiration_date),
                    "name_servers": w.name_servers,
                }
            except Exception as exc:
                results["whois"] = {"status": "error", "error": str(exc)}

    if "dns" in tools:
        try:
            import socket
            ip = socket.gethostbyname(target)
            results["dns"] = {
                "status": "completed",
                "domain": target,
                "ip": ip,
            }
        except Exception as exc:
            results["dns"] = {"status": "error", "error": str(exc)}

    if "shodan" in tools:
        import os
        key = os.environ.get("SHODAN_API_KEY")
        if not key:
            results["shodan"] = {
                "status": "completed",
                "info": "SHODAN_API_KEY not set, skipping",
            }
        else:
            shodan_err = require_package("shodan")
            if shodan_err:
                results["shodan"] = shodan_err
            else:
                try:
                    import shodan
                    api = shodan.Shodan(key)
                    host = api.host(target)
                    results["shodan"] = {
                        "status": "completed",
                        "ip": host.get("ip_str"),
                        "org": host.get("org"),
                        "os": host.get("os"),
                        "ports": host.get("ports", []),
                    }
                except Exception as exc:
                    results["shodan"] = {
                        "status": "error", "error": str(exc),
                    }

    return {
        "status": "completed",
        "target": target,
        "results": results,
    }


@register_skill("mlflow_track")
@skill_guard("MLflow Track")
def mlflow_track(ctx: PipelineContext) -> Dict[str, Any]:
    """Log params, metrics, and artifacts to MLflow.

    Metadata:
        mlflow_experiment: experiment name
        mlflow_run_name:   run name (optional)
        mlflow_params:     dict of parameters
        mlflow_metrics:    dict of metrics
        mlflow_artifact:   path to artifact file (optional)
    """
    err = require_package("mlflow")
    if err:
        return err

    import mlflow

    meta = ctx.goal.metadata or {}
    experiment = meta.get("mlflow_experiment", "default")
    run_name = meta.get("mlflow_run_name")
    params = meta.get("mlflow_params", {})
    metrics = meta.get("mlflow_metrics", {})
    artifact = meta.get("mlflow_artifact")

    try:
        mlflow.set_experiment(experiment)
        with mlflow.start_run(run_name=run_name):
            if params:
                mlflow.log_params(params)
            if metrics:
                mlflow.log_metrics(metrics)
            if artifact and Path(artifact).exists():
                mlflow.log_artifact(artifact)
            run_id = mlflow.active_run().info.run_id
        return {
            "status": "completed",
            "experiment": experiment,
            "run_id": run_id,
            "params_logged": list(params.keys()),
            "metrics_logged": list(metrics.keys()),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@register_skill("mlflow_deploy")
@skill_guard("MLflow Deploy")
def mlflow_deploy(ctx: PipelineContext) -> Dict[str, Any]:
    """Load a model from MLflow registry and return deployment info.

    Metadata:
        mlflow_model_name: registered model name
        mlflow_model_version: version string or 'latest'
        mlflow_stage:      model stage (Staging, Production, etc.)
    """
    err = require_package("mlflow")
    if err:
        return err

    import mlflow

    meta = ctx.goal.metadata or {}
    model_name = meta.get("mlflow_model_name", "")
    version = meta.get("mlflow_model_version", "latest")
    stage = meta.get("mlflow_stage")

    if not model_name:
        return {"status": "failed", "error": "mlflow_model_name required"}

    try:
        if version == "latest":
            client = mlflow.tracking.MlflowClient()
            mv = client.get_latest_versions(
                model_name, stages=[stage] if stage else None,
            )[0]
            model_uri = f"models:/{model_name}/{mv.version}"
            version = mv.version
        else:
            model_uri = f"models:/{model_name}/{version}"

        model = mlflow.pyfunc.load_model(model_uri)
        return {
            "status": "completed",
            "model_name": model_name,
            "version": version,
            "stage": stage,
            "model_uri": model_uri,
            "model_type": str(type(model)),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@register_skill("model_reg")
@skill_guard("Model Reg")
def model_reg(ctx: PipelineContext) -> Dict[str, Any]:
    """Register and stage a model in MLflow Model Registry.

    Metadata:
        mlflow_model_name:    name for the registered model
        mlflow_run_id:        run ID containing the model
        mlflow_artifact_path: artifact path within the run (default 'model')
        mlflow_stage:         target stage (None, Staging,
                                Production, Archived)
    """
    err = require_package("mlflow")
    if err:
        return err

    import mlflow

    meta = ctx.goal.metadata or {}
    model_name = meta.get("mlflow_model_name", "")
    run_id = meta.get("mlflow_run_id", "")
    artifact_path = meta.get("mlflow_artifact_path", "model")
    stage = meta.get("mlflow_stage")

    if not model_name or not run_id:
        return {
            "status": "failed",
            "error": "mlflow_model_name and mlflow_run_id required",
        }

    try:
        model_uri = f"runs:/{run_id}/{artifact_path}"
        result = mlflow.register_model(model_uri, model_name)
        version = result.version

        if stage:
            client = mlflow.tracking.MlflowClient()
            client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage=stage,
            )

        return {
            "status": "completed",
            "model_name": model_name,
            "version": version,
            "stage": stage,
            "model_uri": model_uri,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@register_skill("kubeflow_pipe")
@skill_guard("Kubeflow Pipe")
def kubeflow_pipe(ctx: PipelineContext) -> Dict[str, Any]:
    """Create a Kubeflow pipeline from a Python function.

    Metadata:
        kfp_func_name:    name for the pipeline function
        kfp_output_path:  path to write compiled YAML (default 'pipeline.yaml')
        kfp_steps:        list of step dicts with 'name' and 'image'
    """
    err = require_package("kfp")
    if err:
        return err

    from kfp import dsl
    from kfp.compiler import Compiler

    meta = ctx.goal.metadata or {}
    func_name = meta.get("kfp_func_name", "my_pipeline")
    output_path = meta.get("kfp_output_path", "pipeline.yaml")
    steps = meta.get("kfp_steps", [{"name": "step1", "image": "python:3.9"}])

    try:
        # Dynamically build a pipeline function
        @dsl.pipeline(name=func_name)
        def dynamic_pipeline():
            for step in steps:
                dsl.ContainerOp(
                    name=step["name"],
                    image=step.get("image", "python:3.9"),
                    command=step.get("command", ["echo", "done"]),
                )

        Compiler().compile(dynamic_pipeline, output_path)
        return {
            "status": "completed",
            "pipeline_name": func_name,
            "output_path": output_path,
            "steps": [s["name"] for s in steps],
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
