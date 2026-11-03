---
id: RB-DATABASE-004
title: Runbook — Saturação de Memória e Conexões em MongoDB e Redis
service: mongodb
severity: high
tags:
  - mongodb
  - redis
  - wiredtiger
  - cache
  - connections
  - latency
komodo_stacks:
  - komodo-core
  - glpi-itsm
prometheus_metrics:
  - container_memory_working_set_bytes{name=~".*mongo.*|.*redis.*"}
symptoms:
  - "HighMemoryUsage em komodo-mongo (>85% do limite de 768MB)"
  - "Redis OOM command not allowed when used memory > 'maxmemory'"
  - "Lentidão em queries ou timeout de conexão ao banco"
---

# Runbook — Operação de Emergência MongoDB & Redis em Containers

Procedimentos para contenção de pressão de memória no WiredTiger (`komodo-mongo`) e desalocação de chaves no Redis (`glpi-redis`).

---

## Contenção de Memória no `komodo-mongo` (WiredTiger Cache)

O container `komodo-mongo` opera com limite de `768m` e flag `--wiredTigerCacheSizeGB 0.25`. Conexões acumuladas e cursores abertos consomem RAM adicional fora do cache do WiredTiger.

```bash
docker exec komodo-mongo sh -c 'mongosh --quiet \
  --username "$MONGO_INITDB_ROOT_USERNAME" \
  --password "$MONGO_INITDB_ROOT_PASSWORD" \
  --authenticationDatabase admin \
  --eval "db.serverStatus().mem; db.serverStatus().connections"'
```

Para expurgar logs antigos de `Update` mantendo apenas os últimos 14 dias (após realizar `mongodump`):

```bash
docker exec komodo-mongo sh -c 'mongosh --quiet \
  --username "$MONGO_INITDB_ROOT_USERNAME" \
  --password "$MONGO_INITDB_ROOT_PASSWORD" \
  --authenticationDatabase admin \
  --eval "const cutoff = Date.now() - (14 * 86400 * 1000); db.getSiblingDB(\"komodo\").Update.deleteMany({start_ts: {\$lt: cutoff}})"'
```

---

## Diagnóstico de Memória e Eviction no Redis (`glpi-redis`)

Verifique o uso de memória, fragmentação e política de eviction (`maxmemory-policy`) no container Redis:

```bash
docker exec glpi-redis redis-cli info memory
docker exec glpi-redis redis-cli info stats | grep -E "evicted_keys|rejected_connections"
```
