"""Clientes HTTP enxutos para Telemetria em Tempo Real (Komodo Core RPC API + Prometheus)."""

from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

KOMODO_URL = os.getenv("KOMODO_URL", "https://komodo.ccm.local").rstrip("/")
KOMODO_KEY = os.getenv("KOMODO_API_KEY", "")
KOMODO_SECRET = os.getenv("KOMODO_API_SECRET", "")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus.ccm.local:9090").rstrip("/")
DEMO_MODE = os.getenv("OPS_KB_DEMO_MODE", "true").lower() == "true"

# Dados simulados realistas para demonstração/testes quando fora da VPN ou sem credenciais
DEMO_STACKS: dict[str, dict[str, Any]] = {
    "n8n": {
        "stack": "n8n-automation",
        "server": "CCM-RP-OPSINTERNO-CORE (10.14.218.109)",
        "state": "Restarting (ExitCode 137 - OOMKilled)",
        "limits": {"mem_limit": "512m", "cpus": "0.50"},
        "logs": [
            "ERROR n8n-worker: FATAL ERROR: Reached heap limit Allocation failed - JavaScript heap out of memory",
            "SYSTEM docker: Container n8n-worker killed by cgroup OOM killer (exit_code=137)",
        ],
        "prometheus": {"memory_mb": 511.8, "memory_limit_mb": 512.0, "oom_kills": 4, "cpu_throttling_pct": 64.0},
    },
    "komodo": {
        "stack": "komodo-core",
        "server": "CCM-RP-OPSINTERNO-CORE (10.14.218.109)",
        "state": "Running (Warning: OIDC & Periphery Worker02)",
        "limits": {"komodo-core": "1g", "komodo-mongo": "768m"},
        "logs": [
            "WARN komodo_core::oidc: OIDC initialization failed: missing field 'keys' in JWKS from auth.ccm.local",
            "WARN komodo_core::monitor: Server CCM-RP-APPS-WORKER02 status is NOT OK (Unknown IP on port 8120)",
        ],
        "prometheus": {"mongo_memory_mb": 685.0, "mongo_limit_mb": 768.0, "worker02_up": 0},
    },
    "traefik": {
        "stack": "traefik-interno",
        "server": "CCM-RP-OPSINTERNO-CORE (10.14.218.109)",
        "state": "Running (HTTP 502 spikes)",
        "limits": {"mem_limit": "512m", "cpus": "0.50"},
        "logs": [
            "ERR traefik: 502 Bad Gateway error='dial tcp 172.19.0.14:5678: connect: connection refused' router=n8n@docker",
            "WRN traefik: container n8n-worker is not on network 'proxy'",
        ],
        "prometheus": {"memory_mb": 148.0, "http_502_req_per_sec": 4.85},
    },
}


async def komodo_read(rpc_type: str, params: dict[str, Any] | None = None) -> Any:
    """Cliente RPC universal para a API `/read` do Komodo Core.

    Como toda a API de leitura do Komodo usa um único endpoint (`POST /read` com
    `{"type": "<Operação>", "params": {...}}`), esta função é 100% compatível com
    qualquer operação do `komodo_client::api::read` (ex: `ListServers`, `GetSystemStats`,
    `ListStacks`, `GetStack`, `GetStackLog`, `ListDockerContainers`, `InspectDockerContainer`,
    `GetContainerLog`, `ListDeployments`, `ListAlerts`, `ListUpdates`).
    """
    if KOMODO_KEY and KOMODO_SECRET:
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": KOMODO_KEY,
            "X-Api-Secret": KOMODO_SECRET,
        }
        try:
            async with httpx.AsyncClient(verify=False, timeout=8.0) as client:
                resp = await client.post(
                    f"{KOMODO_URL}/read",
                    headers=headers,
                    json={"type": rpc_type, "params": params or {}},
                )
                resp.raise_for_status()
                return {"source": "komodo_live_api", "type": rpc_type, "data": resp.json()}
        except Exception as exc:
            if not DEMO_MODE:
                raise RuntimeError(f"Erro no Komodo RPC ({rpc_type}): {exc}") from exc

    # Fallback para Modo Demo
    if rpc_type == "ListServers":
        return {
            "source": "demo_mode",
            "type": rpc_type,
            "data": [
                {"name": "CCM-RP-OPSINTERNO-CORE", "address": "10.14.218.109:8120", "status": "OK"},
                {"name": "CCM-RP-APPS-WORKER02", "address": "10.14.218.115:8120", "status": "NOT OK"},
            ],
        }
    if rpc_type == "ListStacks":
        return {"source": "demo_mode", "type": rpc_type, "data": list(DEMO_STACKS.values())}

    target = str((params or {}).get("stack") or (params or {}).get("server") or "komodo").lower()
    key = next((k for k in DEMO_STACKS if k in target), "komodo")
    return {"source": "demo_mode", "type": rpc_type, **DEMO_STACKS[key]}


async def fetch_komodo_stack(stack_name: str) -> dict[str, Any]:
    """Atalho prático que combina `GetStack` + `GetStackLog` para diagnóstico rápido."""
    if KOMODO_KEY and KOMODO_SECRET:
        stack_info = await komodo_read("GetStack", {"stack": stack_name})
        stack_logs = await komodo_read("GetStackLog", {"stack": stack_name, "tail": 30})
        if stack_info.get("source") == "komodo_live_api":
            return {
                "source": "komodo_live_api",
                "stack": stack_info["data"],
                "logs": stack_logs.get("data", []),
            }

    key = next((k for k in DEMO_STACKS if k in stack_name.lower()), "komodo")
    return {"source": "demo_mode", **DEMO_STACKS[key]}


async def fetch_prometheus_metrics(promql: str) -> dict[str, Any]:
    """Executa uma consulta PromQL instantânea na HTTP API do Prometheus (`GET /api/v1/query`)."""
    try:
        async with httpx.AsyncClient(verify=False, timeout=8.0) as client:
            resp = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": promql})
            resp.raise_for_status()
            return {"source": "prometheus_live_api", "promql": promql, "data": resp.json().get("data", {})}
    except Exception as exc:
        if not DEMO_MODE:
            raise RuntimeError(f"Erro ao consultar Prometheus API: {exc}") from exc

    key = next((k for k in DEMO_STACKS if k in promql.lower()), "n8n")
    return {"source": "demo_mode", "promql": promql, "metrics": DEMO_STACKS[key]["prometheus"]}
