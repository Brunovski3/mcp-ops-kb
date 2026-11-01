"""Servidor FastMCP enxuto: expõe ferramentas para RAG de Runbooks e Telemetria Komodo/Prometheus."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from mcp_ops_kb.rag import RunbookRAG
from mcp_ops_kb.telemetry import fetch_komodo_stack, fetch_prometheus_metrics, komodo_read

mcp = FastMCP(
    name="mcp-ops-kb",
    instructions="Servidor MCP de Operações: consulta Runbooks em Markdown (RAG) e telemetria Komodo/Prometheus.",
)

rag = RunbookRAG()


@mcp.tool()
def search_runbooks(query: str, service: str | None = None, top_k: int = 3) -> list[dict[str, Any]]:
    """Busca procedimentos em Runbooks Markdown usando RAG estruturado (YAML Frontmatter + BM25).

    Args:
        query: Sintoma, mensagem de erro ou palavra-chave (ex: 'OOMKilled 137', 'OIDC keys', '502').
        service: Filtro opcional por serviço ('komodo', 'n8n', 'traefik', 'mongodb').
        top_k: Quantidade máxima de seções retornadas.
    """
    return rag.search(query=query, service=service, top_k=top_k)


@mcp.tool()
async def komodo_read_api(rpc_type: str, params: dict[str, Any] | None = None) -> Any:
    """Executa qualquer operação de leitura (`POST /read`) da API oficial do Komodo Core.

    Compatível com 100% dos métodos `api::read` do Komodo:
    - Servidores/Host: `ListServers`, `GetServer`, `GetServerState`, `GetSystemStats`, `GetSystemInformation`
    - Stacks Compose: `ListStacks`, `GetStack`, `GetStackLog`, `SearchStackLog`
    - Containers Docker: `ListDockerContainers`, `InspectDockerContainer`, `GetContainerLog`
    - Alertas e Histórico: `ListAlerts`, `GetAlert`, `ListUpdates`, `GetUpdate`

    Args:
        rpc_type: Nome exato da operação RPC do Komodo (ex: 'ListServers', 'GetSystemStats', 'ListAlerts').
        params: Dicionário de parâmetros da operação (ex: `{"stack": "komodo-core"}` ou `{}`).
    """
    return await komodo_read(rpc_type=rpc_type, params=params)


@mcp.tool()
async def query_prometheus(promql: str) -> dict[str, Any]:
    """Executa uma query PromQL no Prometheus para obter telemetria de containers em tempo real.

    Args:
        promql: Expressão PromQL (ex: 'container_memory_working_set_bytes{name=~".*n8n.*"}').
    """
    return await fetch_prometheus_metrics(promql)


@mcp.tool()
async def diagnose_incident(service: str, symptom: str) -> dict[str, Any]:
    """Ferramenta completa de diagnóstico: cruza Komodo + Prometheus + Runbooks RAG em uma única chamada.

    Args:
        service: Nome do serviço afetado (ex: 'n8n', 'komodo', 'traefik').
        symptom: Descrição do problema ou erro observado (ex: 'container reiniciando com erro 137').
    """
    komodo_data = await fetch_komodo_stack(service)
    prom_data = await fetch_prometheus_metrics(f'container_memory_working_set_bytes{{name=~".*{service}.*"}}')

    # Enriquece a busca no RAG juntando o sintoma informado + os logs reais coletados no Komodo
    logs_text = " ".join(komodo_data.get("logs", []))
    runbook_matches = rag.search(query=f"{service} {symptom} {logs_text}", top_k=2)

    return {
        "service": service,
        "symptom": symptom,
        "komodo_telemetry": komodo_data,
        "prometheus_telemetry": prom_data,
        "recommended_runbooks": runbook_matches,
    }


def main() -> None:
    """Inicia o servidor MCP via stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
