---
id: RB-TRAEFIK-003
title: Runbook — Traefik Reverse Proxy (HTTP 502 Bad Gateway, 504 Timeout e Rede Proxy)
service: traefik
severity: high
tags:
  - traefik
  - 502-bad-gateway
  - 504-gateway-timeout
  - reverse-proxy
  - tls
  - docker-network
komodo_stacks:
  - traefik-interno
  - traefik-ext
prometheus_metrics:
  - traefik_service_requests_total{code=~"5.."}
  - traefik_Backend_server_up
symptoms:
  - "502 Bad Gateway dial tcp connect: connection refused"
  - "container is not on network 'proxy'"
  - "504 Gateway Timeout em rotas *.ccm.local"
  - "TraefikHighHttp5xxRate firing no Prometheus"
---

# Runbook — Traefik Reverse Proxy (`traefik-interno` / `traefik-ext`)

Procedimento para resolução de erros HTTP `502 Bad Gateway`, `504 Gateway Timeout` e falhas de descoberta de containers na rede externa `proxy`.

---

## Diagnóstico de HTTP 502 Bad Gateway (`connection refused`)

O erro `502 Bad Gateway` no Traefik ocorre por três causas principais:
1. O container de backend está em loop de restart / OOMKilled (ex.: `n8n`, `glpi`);
2. A label `traefik.http.services.<svc>.loadbalancer.server.port` aponta para uma porta incorreta;
3. O container de backend não está conectado à rede Docker externa `proxy`.

```bash
docker logs traefik --tail 100 | grep -E "502|ERR|WRN"
docker network inspect proxy --format '{{range .Containers}}{{.Name}}: {{.IPv4Address}}{{"\n"}}{{end}}'
```

---

## Corrigir Container Fora da Rede `proxy`

Todo serviço exposto via Traefik precisa declarar `networks: [proxy]` como `external: true` e a label `traefik.docker.network: "proxy"` quando possuir mais de uma rede (ex.: `komodo-net` + `proxy`).

```bash
docker network connect proxy <container_name>
docker restart traefik
```

Para correção definitiva, garanta no `compose.yaml` da stack:
- Label `traefik.docker.network: "proxy"` no serviço web;
- Bloco `networks.proxy.external: true` no final do compose.
