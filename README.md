# Vehicle Core Service

Serviço principal da plataforma de revenda de veículos: cadastro e edição do catálogo (marca,
modelo, ano, cor, preço). É a **fonte da verdade** dos dados cadastrais e possui banco de dados
próprio (`vehicle_core`), isolado do banco do `vehicle-sales-service`. Os dois serviços trocam
snapshots de catálogo e status comercial via HTTP.

## Sumário

- [Como foi implementado](#como-foi-implementado)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Comunicação com o vehicle-sales-service](#comunicação-com-o-vehicle-sales-service)
- [Como rodar localmente](#como-rodar-localmente)
- [Como testar](#como-testar)
- [CI/CD](#cicd)
- [Infraestrutura e deploy](#infraestrutura-e-deploy)

## Como foi implementado

Stack: **Python 3.13**, **FastAPI**, **Pydantic v2** / **pydantic-settings**, **SQLAlchemy 2.0**
(async) + **asyncpg**, **Alembic** para migrações, **PostgreSQL 17**, **loguru** para logging
estruturado e **uv** como único gerenciador de dependências.

A aplicação segue **Clean Architecture** com **Ports & Adapters**, organizada em quatro camadas
com dependências sempre apontando para o centro (domínio):

- **Domain** (`src/domain/`) — entidade `Vehicle` (pydantic, com regras de negócio como
  `update_details` e `apply_status`), exceções de domínio (`VehicleNotFoundError`,
  `VehicleNotEditableError`, `InvalidVehicleDataError`) e o Port de persistência
  `VehicleRepository` (`abc.ABC`). Não depende de nenhuma camada externa, exceto `pydantic`.
- **Application** (`src/application/`) — casos de uso (`RegisterVehicle`, `UpdateVehicle`,
  `GetVehicle`, `ApplyVehicleStatus`), DTOs de fronteira (`VehicleResponse`, `VehicleSnapshot`) e o
  Port de infraestrutura `SalesSync` (comunicação com o serviço de vendas).
- **Interface** (`src/interface/`) — controllers FastAPI (`v1/vehicle_controller.py`,
  `v1/internal_vehicle_controller.py`, `health_controller.py`), gateways/adapters concretos
  (`SQLAlchemyVehicleRepository`, `HttpSalesSync`) e presenters (schemas de request/erro).
- **Infrastructure** (`src/infrastructure/`) — engine/sessão async do SQLAlchemy, models ORM,
  cliente HTTP compartilhado, observabilidade (`loguru`) e migrações Alembic.

As exceções de domínio nunca carregam códigos HTTP; a tradução para respostas HTTP acontece
exclusivamente em `src/main.py`, via `@app.exception_handler`.

## Estrutura do projeto

```
service/
├── src/
│   ├── main.py                    # App factory FastAPI + lifespan + exception handlers
│   ├── environment.py             # Settings (pydantic-settings), lidas de variáveis de ambiente
│   ├── domain/
│   │   ├── entities/vehicle.py    # Entidade Vehicle (regras de negócio do catálogo)
│   │   ├── repositories/          # Port de persistência (VehicleRepository)
│   │   └── exceptions.py          # Exceções de domínio
│   ├── application/
│   │   ├── use_cases/             # RegisterVehicle, UpdateVehicle, GetVehicle, ApplyVehicleStatus
│   │   ├── ports/sales_sync.py    # Port de sincronização com o vehicle-sales-service
│   │   └── dtos/                  # VehicleResponse, VehicleSnapshot
│   ├── interface/
│   │   ├── controllers/           # Rotas FastAPI (v1 público + internal)
│   │   ├── gateways/              # Adapters: SQLAlchemyVehicleRepository, HttpSalesSync
│   │   └── presenters/            # Schemas de request e de erro
│   └── infrastructure/
│       ├── database/              # Engine async + session factory
│       ├── models/                # Models ORM (SQLAlchemy)
│       ├── http/                  # Cliente httpx compartilhado (lifespan)
│       ├── observability/         # Configuração do loguru
│       └── alembic/               # Migrações do banco
├── tests/                         # Espelha src/ (unit) + tests/integration/ (testcontainers)
├── scripts/seed.py                # Popula o catálogo com dados fixos de demonstração
├── Dockerfile                     # Multistage build
├── docker-compose.yml             # Stack local (postgres + migrations + seed + app)
├── Makefile                       # format / lint / typecheck / test / quality
├── alembic.ini
└── env.example
```

## Comunicação com o vehicle-sales-service

Os dois serviços têm bancos de dados isolados e trocam apenas snapshots via HTTP:

- **Core → Sales (push best-effort):** ao cadastrar (`POST /v1/vehicles`) ou editar
  (`PUT /v1/vehicles/{vehicle_id}`) um veículo, o Core agenda em background task o envio do
  snapshot de catálogo (`PUT /internal/v1/vehicles/{vehicle_id}` no Sales) via `SalesSync`
  (`HttpSalesSync`), com até 3 tentativas e backoff. Falhas de rede são logadas e absorvidas — a
  disponibilidade de escrita do catálogo não depende do serviço de vendas.
- **Sales → Core (mirror de status):** quando o Sales reserva ou vende um veículo, ele notifica o
  Core em `PATCH /internal/v1/vehicles/{vehicle_id}/status`, autenticado pelo header
  `X-Internal-Token` (comparado em tempo constante contra `INTERNAL_API_TOKEN`). O caso de uso
  `ApplyVehicleStatus` espelha o status (`AVAILABLE` / `RESERVED` / `SOLD`) no catálogo do Core, o
  que bloqueia futuras edições de veículos não disponíveis (`VehicleNotEditableError` → HTTP 409).

Rotas internas (`/internal/v1/...`) ficam fora do schema público do OpenAPI
(`include_in_schema=False`).

### Webhook de pagamento

O webhook de notificação de pagamento (`POST /webhooks/v1/payments`) não existe neste serviço —
por decisão deliberada, ele é hospedado no `vehicle-sales-service`, pois o ciclo de vida da venda e
a transição atômica venda/veículo pertencem ao banco de dados segregado do serviço de vendas.
Justificativa completa no ADR `docs/adr/0001-webhook-pagamento-no-servico-de-vendas.md` do
repositório `vehicle-sales-service`.

## Como rodar localmente

### Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) e Docker Compose
- [uv](https://docs.astral.sh/uv/) (para rodar fora de container) + Python 3.13

### Com Docker Compose (recomendado)

```bash
cd service
cp env.example .env
docker compose up --build
```

Isso sobe `postgres`, roda as migrações (`alembic upgrade head`), popula o catálogo de demonstração
(`seed`) e inicia a API em `http://localhost:8000` (health check em `/health`).

### Bare metal (sem Docker)

```bash
cd service
cp env.example .env
uv sync
# suba um PostgreSQL compatível com as variáveis DATABASE_* do .env
uv run alembic upgrade head
uv run uvicorn src.main:app --reload --port 8000
```

### Documentação interativa da API

Com o serviço no ar: `http://localhost:8000/docs` (Swagger) ou `http://localhost:8000/redoc`.

## Como testar

```bash
cd service
uv sync

# suíte de qualidade completa (equivalente ao Makefile)
make quality            # ruff format + ruff check --fix + ty check + pytest --cov

# comandos individuais
uv run ruff format src/ tests/
uv run ruff check --fix src/ tests/
uv run ty check src/
uv run pytest --cov=src --cov-report=term-missing -m "not integration"

# testes de integração (sobem um PostgreSQL efêmero via testcontainers)
uv run pytest -m integration
```

A CI exige **cobertura mínima de 80%** (`--cov-fail-under=80`) nos testes unitários. Os testes de
integração usam [testcontainers](https://testcontainers.com/) para subir um PostgreSQL descartável
— nunca o banco do `docker-compose.yml` local.

## CI/CD

Definido em `.github/workflows/`:

- **`ci.yml`** — roda em todo Pull Request: `ruff format --check`, `ruff check`, `ty check`,
  `pytest` (unitários com cobertura ≥ 80% + integração via testcontainers), build de imagem Docker
  (smoke test) e, se configurado, análise no SonarCloud.
- **`cd.yml`** — roda a cada push em `main`: repete o quality gate, publica a imagem no Amazon ECR
  e faz o deploy na instância EC2 via AWS Systems Manager (SSM Run Command).
- **`infra.yml`** — execução manual (`workflow_dispatch`) de `terraform apply`/`destroy` da infra
  em produção, protegida pelo ambiente `infra` do GitHub (aprovação obrigatória).

## Infraestrutura e deploy

Detalhes de infraestrutura provisionada, variáveis de ambiente/segredos e deploy em produção estão
documentados separadamente para não duplicar conteúdo:

- [`infra/README.md`](./infra/README.md) — infraestrutura AWS (Terraform Cloud), variáveis de
  ambiente/segredos completas e o fluxo de deploy.
- [`infra/local/README.md`](./infra/local/README.md) — como validar a infraestrutura localmente
  com o emulador [Floci](https://hub.docker.com/r/floci/floci).
