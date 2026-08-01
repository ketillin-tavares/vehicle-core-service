# vehicle-core-service

Serviço principal da plataforma de revenda de veículos: cadastro e edição de veículos.
Possui banco de dados próprio (`vehicle_core`) e é consumido via HTTP pelo `vehicle-sales-service`.

## Stack local

| Componente | Porta host | Porta container |
|---|---|---|
| API | 8000 | 8000 |
| PostgreSQL | 5432 | 5432 |
| Floci (emulador AWS) | 4566 | 4566 |

## Como rodar

```bash
cp env.example .env
docker compose up --build
```

Health check: <http://localhost:8000/health>

## Qualidade

```bash
make quality   # format + lint + typecheck + testes com cobertura
```
