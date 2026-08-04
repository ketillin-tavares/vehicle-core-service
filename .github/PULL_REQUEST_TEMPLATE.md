<!-- Título sugerido: tipo(escopo): resumo curto — ex.: "feat(vehicle): permite editar cor do veículo" -->

## Descrição

<!-- O que muda e por quê. Referencie a issue/tarefa quando existir. -->

## Tipo de mudança

- [ ] Feature
- [ ] Bugfix
- [ ] Refactor (sem mudança de comportamento)
- [ ] Infra / CI-CD
- [ ] Documentação

## Como foi testado

<!-- Passos objetivos para o revisor validar (rotas chamadas, cenários cobertos, etc.). -->

## Checklist

Itens abaixo são os mesmos verificados pela pipeline (`.github/workflows/ci.yml`) — rode
`make quality` em `service/` antes de abrir o PR para confirmar tudo de uma vez:

- [ ] `ruff format --check` e `ruff check` sem apontamentos (`uv run ruff format --check src/ tests/` / `uv run ruff check src/ tests/`)
- [ ] `ty check src/` sem erros de tipagem
- [ ] Testes unitários (`pytest -m "not integration"`) cobrindo o cenário AAA, com cobertura ≥ 80% (gate da CI: `--cov-fail-under=80`)
- [ ] Testes de integração (`pytest -m integration`) atualizados/rodados quando a mudança afeta gateways ou infraestrutura
- [ ] Migração Alembic criada e testada, se o schema do banco mudou
- [ ] Sem segredos, `.env` ou credenciais no diff
- [ ] Clean Architecture respeitada (domínio sem dependência de application/interface/infrastructure)
- [ ] Docs atualizadas quando aplicável (`README.md`, `infra/README.md`, `infra/local/README.md`, ADRs em `docs/adr/`)

> **Atenção:** merge em `main` dispara deploy automático em produção (`cd.yml`: build da imagem,
> push para o ECR e rollout na EC2 via SSM). Confirme que os itens acima passaram antes de
> aprovar/mergear.
