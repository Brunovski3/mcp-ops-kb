"""Testes diretos e fáceis de explicar para o mcp-ops-kb."""

from __future__ import annotations

import pytest

from mcp_ops_kb.rag import RunbookRAG
from mcp_ops_kb.server import diagnose_incident, search_runbooks
from mcp_ops_kb.telemetry import fetch_komodo_stack, fetch_prometheus_metrics


def test_rag_busca_secao_correta_por_sintoma() -> None:
    rag = RunbookRAG()
    resultados = rag.search("OIDC missing field keys")
    assert len(resultados) > 0
    assert resultados[0]["runbook_id"] == "RB-KOMODO-001"
    assert "OIDC" in resultados[0]["section"]


def test_rag_busca_oom_killed_137() -> None:
    fn = search_runbooks.fn if hasattr(search_runbooks, "fn") else search_runbooks
    resultados = fn(query="OOMKilled Exit Code 137 JavaScript heap", service="n8n")
    assert len(resultados) > 0
    assert resultados[0]["runbook_id"] == "RB-CONTAINER-002"


@pytest.mark.asyncio
async def test_telemetria_komodo_e_prometheus() -> None:
    komodo = await fetch_komodo_stack("n8n")
    assert komodo["stack"] == "n8n-automation"
    assert any("heap out of memory" in log for log in komodo["logs"])

    prom = await fetch_prometheus_metrics('container_memory_working_set_bytes{name="n8n"}')
    assert "metrics" in prom or "data" in prom


@pytest.mark.asyncio
async def test_diagnose_incident_correlaciona_tudo() -> None:
    fn = diagnose_incident.fn if hasattr(diagnose_incident, "fn") else diagnose_incident
    relatorio = await fn(service="n8n", symptom="container reiniciando com erro 137")
    assert relatorio["komodo_telemetry"]["stack"] == "n8n-automation"
    assert len(relatorio["recommended_runbooks"]) > 0
    assert relatorio["recommended_runbooks"][0]["runbook_id"] == "RB-CONTAINER-002"
