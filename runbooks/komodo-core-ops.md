---
id: RB-KOMODO-001
title: Runbook Operacional — Komodo Core, Periphery e MongoDB
service: komodo
severity: critical
tags:
  - komodo
  - gitops
  - oidc
  - authentik
  - periphery
  - mongodb
  - ca-certificates
  - bootstrap
komodo_stacks:
  - komodo-core
prometheus_metrics:
  - container_memory_working_set_bytes{name="komodo-mongo"}
  - up{job="komodo-periphery"}
symptoms:
  - "OIDC não inicializa — missing field 'keys'"
  - "Um servidor aparece como NOT OK / Unknown IP"
  - "Erro de certificado TLS x509 ao falar com serviço interno *.ccm.local"
  - "Bloqueio por rate limit no login do Komodo"
  - "Crescimento excessivo do banco komodo-mongo (Updates collection)"
---

# Runbook — Komodo Core & Periphery

Procedimentos operacionais da stack **Komodo** (`CCM-RP-OPSINTERNO-CORE` - `10.14.218.109`), aplicada em `/opt/docker/komodo`.

---

## Aplicar mudança e validar Compose

Sempre validar o arquivo de compose antes de recriar containers no CORE para evitar perder `name: komodo-core`, variáveis do `.env` ou o bind mount auto-referente (`/opt/docker/komodo/compose.yaml`).

```bash
cd /opt/docker/komodo
git pull
docker compose config
docker compose up -d
docker compose ps
```

> **Atenção:** Nunca execute `Stop` ou `Down` na stack do Komodo pelo próprio painel web do Komodo (Bootstrap Paradox). Caso ocorra, recupere via SSH no CORE com `cd /opt/docker/komodo && docker compose up -d`.

---

## OIDC não inicializa — `missing field 'keys'`

Quando o login via SSO OIDC falha ou o log do `komodo-core` reporta `missing field 'keys'`, o endpoint JWKS do Authentik retornou `{"keys":[]}` porque o OAuth2 Provider está sem **Signing Key** associada.

```bash
curl -k https://auth.ccm.local/application/o/komodo/jwks/
docker logs komodo-core --tail 50 | grep -i oidc
```

**Mitigação:** Acesse o painel do Authentik (`auth.ccm.local`), edite o Provider do Komodo e selecione uma **Signing Key RSA** válida. Em seguida, reinicie o `komodo-core`:

```bash
cd /opt/docker/komodo && docker compose restart core
```

---

## Servidor aparece como `NOT OK` / `Unknown IP`

Indica que o agente `komodo-periphery` do host remoto está inacessível na porta `8120` (host caído, daemon Docker parado ou firewall bloqueando). O painel e os demais servidores seguem operando normalmente.

```bash
ansible <host> -m ping
ansible <host> -m shell -a "systemctl status docker; docker ps | grep periphery" --become
```

Se o container `komodo-periphery` estiver parado no host destino:

```bash
ansible <host> -m shell -a "cd /opt/docker/periphery && docker compose up -d" --become
```

---

## Erro de certificado TLS ao falar com serviço interno (`*.ccm.local`)

A CA interna privada precisa estar montada em `/data/services/komodo/core/ca/ccm-ca.crt` no host e mapeada em `/usr/local/share/ca-certificates/ccm-ca.crt`. Nunca defina `SSL_CERT_FILE` manualmente para não sobrescrever o bundle público (quebraria conexões HTTPS com o GitHub).

```bash
docker logs komodo-core 2>&1 | head -20
```

Confirme a presença da linha `1 added, 0 removed` no boot do container.

---

## Bloqueio por Rate Limit de Autenticação

Após múltiplas tentativas de login com falha, o IP/usuário entra na janela de bloqueio (`KOMODO_AUTH_RATE_LIMIT_MAX_ATTEMPTS`). Para limpar o estado em memória imediatamente:

```bash
docker restart komodo-core
```

Aguarde ~20 segundos após o restart e realize uma única tentativa de autenticação.

---

## Backup, Restore e Crescimento do MongoDB (`komodo-mongo`)

O MongoDB (`komodo-mongo`, limite de `768m` e `--wiredTigerCacheSizeGB 0.25`) armazena todo o estado do Komodo e a collection `Updates` (sem retenção automática).

```bash
docker exec komodo-mongo sh -c 'mongosh --quiet \
  --username "$MONGO_INITDB_ROOT_USERNAME" \
  --password "$MONGO_INITDB_ROOT_PASSWORD" \
  --authenticationDatabase admin \
  --eval "db.getSiblingDB(\"komodo\").stats().dataSize"'
```

Para executar backup lógico a quente antes de manutenções ou limpeza:

```bash
docker exec komodo-mongo sh -c 'mongodump \
  --username "$MONGO_INITDB_ROOT_USERNAME" \
  --password "$MONGO_INITDB_ROOT_PASSWORD" \
  --authenticationDatabase admin \
  --archive' > /root/komodo-mongo-$(date +%Y%m%d).archive
ls -lh /root/komodo-mongo-*.archive
```
