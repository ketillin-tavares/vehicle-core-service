# ADR-0001: Deploy do vehicle-core-service em AWS EC2

**Status:** Aceito
**Data:** 2026-08-01
**Autor:** Equipe de Arquitetura
**Contexto:** vehicle-core-service MVP (desafio estudantil)

---

## Contexto

O vehicle-core-service é um MVP em contexto acadêmico com prioridades explícitas: custo reduzido, time pequeno, iteração rápida. A decisão de arquitetura de infra e CI/CD deve minimizar custos sem comprometer a entrega de funcionalidade essencial. Alternativas avaliadas incluem orquestração em contêiner (EKS/ECS), persistência de dados em container, e registros de imagem.

---

## Decisão

Deploy em **instância única AWS EC2** (t3.micro, Amazon Linux 2023) executando `docker-compose`:

- **Compute:** Uma instância EC2 t3.micro com stack docker-compose (migrations + app). Sem SSH — acesso exclusivo via **AWS Systems Manager (SSM)**, sem chaves estáticas.
- **Banco de dados:** **RDS PostgreSQL** (db.t4g.micro, single-AZ, PostgreSQL 17) com senha gerenciada por **AWS Secrets Manager** (nunca em Terraform state); grupo de segurança aceita porta 5432 apenas da EC2.
- **Imagens:** **Amazon ECR** (Elastic Container Registry), sem credenciais de registry transmitidas — acesso via IAM da instância EC2.
- **Infraestrutura:** **Terraform via Terraform Cloud** (HCP Terraform, CLI-driven), validação local com **Floci** (`floci/floci:latest`, porta 4566).
- **Autenticação:**
  - GitHub Actions → AWS: **OIDC** (sem chaves AWS estáticas em secrets).
  - Terraform Cloud → AWS: **OIDC nativo** do TFC (sem workspace variables com chaves).

---

## Alternativas Consideradas e Rejeitadas

| Alternativa | Motivo da Rejeição |
|---|---|
| **EKS/ECS + ALB** | Complexidade e custo incompatíveis com MVP; mínimo 3–5× custo mensal. |
| **PostgreSQL em container (EC2)** | Durabilidade de dados: perda total da BD se a instância falhar; MVP sem backup automático. |
| **GHCR (GitHub Container Registry)** | Autenticação requer credenciais via SSM; ECR integra nativamente com IAM da instância sem secrets transit. |

---

## Consequências e Riscos Aceitos

### Consequências Operacionais

- **Tempo de entrega:** semanas, não meses; stack mínimo testável em dias.
- **Custo operacional:** ~US$ 8–15/mês (EC2 t3.micro + RDS db.t4g.micro com free-tier).
- **Escalabilidade:** não existe; instância única. MVP, sem high-availability.

### Riscos Aceitos (Security Review §11)

1. **Porta 8000 aberta ao mundo** com rotas internas protegidas por **token estático** (32+ bytes, comparação via `compare_digest`).
2. **HTTP sem TLS** (não HTTPS); MVP estudantil, não produção crítica.
3. **VPC default** (sem custom networking) — custo zero, sem isolamento adicional.
4. **Instância única** sem replicação — perda de dados RDS se a BD falhar (sem backup automático cross-AZ).
5. **`TF_API_TOKEN` longa duração**, escopado a um workspace com **rotação documentada** no repositório (README + bootstrap).

### Mitigações Documentadas

- Seed data **nunca em produção** (compose.prod.yml omite seed).
- EC2 com **IMDSv2 obrigatório** (`http_tokens = required`), EBS criptografado.
- Segurança de grupo RDS: 5432 apenas da EC2.
- OIDC: trust policy pin exato em `sub` (branch main) e `aud`.
- SSM SendCommand policy: mínimo (tag-constrained, sem admin).

---

## Implementação

- **Infrastructure:** `infra/stack/` (módulo TF), `infra/main/` (produção, TFC), `infra/local/` (Floci).
- **Deploy:** `deploy/docker-compose.prod.yml`, `deploy/deploy.sh` (executado via SSM).
- **CI/CD:** `.github/workflows/` — `ci.yml`, `cd.yml` (push to main), `infra.yml` (manual).

---

## Referências

- Plano: `docs/plans/core-cicd-infra.md` (decisões de arquitetura, security review binding).
- Security review outcomes: seção 11 (riscos aceitos), seção 8 (pinning de actions).
