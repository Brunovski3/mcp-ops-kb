---
id: RB-CONTAINER-002
title: Runbook — Containers em CrashLoop, OOMKilled (Exit Code 137) e CPU Throttling
service: n8n
severity: critical
tags:
  - oom
  - oomkilled
  - exit-137
  - memory
  - cpu-throttling
  - cadvisor
  - docker
  - n8n
komodo_stacks:
  - n8n-automation
  - glpi-itsm
prometheus_metrics:
  - container_memory_working_set_bytes
  - container_spec_memory_limit_bytes
  - container_oom_events_total
  - container_cpu_cfs_throttled_periods_total
symptoms:
  - "Container reiniciando com Exit Code 137 (OOMKilled)"
  - "FATAL ERROR: Reached heap limit Allocation failed - JavaScript heap out of memory"
  - "Lentidão severa por CPU CFS Throttling acima de 50%"
  - "Alerta ContainerOOMKilled ou ContainerRestarting disparado no Prometheus/Komodo"
---

# Runbook — Diagnóstico e Mitigação de OOMKilled (Exit 137) e Saturação de CPU

Procedimento padrão para diagnóstico rápido quando containers Docker gerenciados pelo Komodo entram em estado `Restarting (137)` ou sofrem estrangulamento de CPU (CFS Throttling).

---

## Confirmar OOMKill (Exit Code 137) no Host Docker

Quando um container atinge o `mem_limit` definido no `compose.yaml`, o cgroup OOM Killer do kernel Linux encerra o processo com sinal `SIGKILL (9)`, resultando em `ExitCode: 137`.

```bash
docker inspect <container_name> --format '{{json .State}}' | jq '{Status, ExitCode, OOMKilled, FinishedAt}'
dmesg -T | grep -i -E 'oom|killed process' | tail -20
```

---

## Mitigação para Workers Node.js / n8n (`JavaScript heap out of memory`)

Em stacks baseadas em Node.js (como `n8n-main` e `n8n-worker`), o V8 precisa ter `--max-old-space-size` alinhado abaixo do `mem_limit` do container (ex.: 75% do limite do container), além de dimensionamento adequado para workflows pesados em lote.

1. Verifique o consumo atual e limites no `compose.yaml` da stack:

```bash
docker stats --no-stream <container_name>
```

2. Ajuste temporário/emergencial de limite de memória ou atualização via GitOps (`infra-core`):
   - Elevar `mem_limit` de `512m` para `1024m` no `n8n-worker`;
   - Definir `NODE_OPTIONS=--max-old-space-size=768` no `.env` da stack;
   - Reaplicar stack pelo Komodo ou CLI:

```bash
cd /opt/docker/stacks/n8n
docker compose config
docker compose up -d
```

---

## Diagnóstico de CPU CFS Throttling elevado

Se a métrica `container_cpu_cfs_throttled_periods_total` indicar mais de 30% de períodos com throttling, o container possui cota `cpus` subdimensionada para picos síncronos.

```bash
docker inspect <container_name> --format 'NanoCPUs={{.HostConfig.NanoCpus}} Memory={{.HostConfig.Memory}}'
```

Ajuste a diretiva `cpus` no `compose.yaml` (ex.: de `"0.50"` para `"1.00"`) e execute redeploy via Komodo.
