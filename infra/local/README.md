# Infraestrutura local (Floci) — vehicle-core-service

Como validar a stack Terraform de infraestrutura (`infra/stack`) localmente, **sem tocar a AWS
real**, usando o emulador [Floci](https://hub.docker.com/r/floci/floci). Este README cobre apenas a
validação da infraestrutura; para rodar a aplicação localmente veja o
[README raiz](../../README.md), e para o significado de cada recurso provisionado e o deploy em
produção veja [`infra/README.md`](../README.md).

## O que é esta raiz

`infra/local/` é uma raiz Terraform separada de `infra/main/` (produção), mas que reutiliza o
**mesmo módulo** `infra/stack/` — nenhum recurso é reescrito para a emulação. As únicas diferenças
em relação a produção são variáveis do módulo:

- `aws_endpoint_url = "http://localhost:4566"` — aponta o provider AWS para o Floci em vez da AWS
  real.
- `create_github_oidc = false` — o Floci não implementa `CreateOpenIDConnectProvider`; esta raiz
  pula a criação do provider OIDC e da role de deploy (o único gap de emulação conhecido).
- Backend **local** (sem `cloud {}`), state descartável — nunca é uma fonte de verdade.

Tudo o mais (EC2, Security Groups, Elastic IP, RDS com senha gerenciada em Secrets Manager, ECR,
IAM roles/instance profile, KMS CMK, parâmetros SSM) é aplicado de verdade contra o emulador.

## Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) (o Floci precisa do socket do Docker do host para
  emular EC2/RDS com containers reais)
- [Terraform](https://developer.hashicorp.com/terraform/downloads) `>= 1.6.0`
- Bash (o script `floci-validate.sh` é um script shell)

## Como rodar

O script `floci-validate.sh` cuida de subir o Floci (se ainda não estiver rodando), rodar o
Terraform e limpar tudo ao final:

```bash
cd infra/local
./floci-validate.sh          # terraform fmt -check + init + validate + plan
./floci-validate.sh --apply  # o mesmo, + apply completo + terraform state list + destroy
```

O script:

1. Roda `terraform fmt -check -recursive` na árvore de `infra/`.
2. Verifica se algo já está escutando em `:4566`; se não, sobe o container
   `floci/floci:latest` publicando a porta `4566` **com o socket do Docker do host montado**
   (`-v /var/run/docker.sock:/var/run/docker.sock` — obrigatório: sem ele, instâncias EC2 vão para
   `pending → terminated` e chamadas ao RDS falham com `SocketException`).
3. Usa credenciais AWS fictícias (`AWS_ACCESS_KEY_ID=test`, `AWS_SECRET_ACCESS_KEY=test`,
   `AWS_DEFAULT_REGION=us-east-1`) — o Floci não as valida.
4. Roda `terraform init` (backend local) + `validate` + `plan`.
5. Com `--apply`: roda `terraform apply -auto-approve`, lista os recursos criados
   (`terraform state list`) e em seguida `terraform destroy -auto-approve`.
6. Ao sair (sucesso ou erro), remove `terraform.tfstate`/`terraform.tfstate.backup` locais, para o
   container do Floci (se foi este script que o iniciou) e remove, best-effort, quaisquer
   containers residuais criados pelo Floci para emular EC2/RDS/ECR
   (`floci-ec2-*`, `floci-rds-*`, `floci-ecr-*`).

> **Importante:** a imagem correta é sempre `floci/floci:latest` — **nunca** `latest-compat`.

## Variáveis de ambiente

Não há `.env` nesta raiz: as credenciais fictícias são exportadas pelo próprio
`floci-validate.sh`. A única configuração é feita via variáveis do módulo Terraform, já fixadas em
`infra/local/main.tf`:

| Variável do módulo | Valor local | Equivalente em produção |
|---|---|---|
| `aws_region` | `us-east-1` | `us-east-1` (padrão, configurável) |
| `github_org` | `floci-local` | organização/usuário real do GitHub (`github_org` do workspace) |
| `aws_endpoint_url` | `http://localhost:4566` | `null` (usa a AWS real) |
| `create_github_oidc` | `false` | `true` (padrão) |

## Diferenças conhecidas em relação à AWS real

| Achado | Tratamento |
|---|---|
| O Floci sustenta instâncias EC2 e bancos RDS com containers Docker reais, usando o socket do host | `floci-validate.sh` sobe o Floci com o socket montado — **obrigatório**; sem isso o EC2 vai para `pending→terminated` e o RDS falha com `SocketException` |
| `CreateOpenIDConnectProvider` retorna `UnsupportedOperation` | `create_github_oidc = false` é definido **somente** em `infra/local` — pula o provider OIDC, a role e a política de deploy apenas localmente |
| Todo o resto (EC2, SG, EIP, RDS incluindo master password gerenciada/Secrets Manager, ECR + política de ciclo de vida, roles/instance profiles/políticas IAM, KMS CMK + alias + rotação + SSM `SecureString` via CMK, parâmetros SSM, data sources de VPC default e AMI AL2023) | Aplicado de verdade contra o emulador — `apply`/`destroy` completos no script |

## Fluxo recomendado

1. Após qualquer alteração em `infra/stack/`, rode `./floci-validate.sh --apply` localmente antes
   de abrir o Pull Request — valida `fmt`, `plan` e um ciclo completo de `apply`/`destroy` sem
   custo e sem risco para a conta AWS real.
2. Só depois disso, o workflow `infra.yml` (`workflow_dispatch`, ambiente `infra` no GitHub) aplica
   a mesma mudança em produção via `infra/main`, contra a AWS real através da Terraform Cloud. Veja
   [`infra/README.md`](../README.md) para o fluxo completo de produção.
