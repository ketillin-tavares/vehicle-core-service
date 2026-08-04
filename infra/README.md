# Infraestrutura (Terraform) — vehicle-core-service

Documentação da infraestrutura AWS **de produção** provisionada via Terraform: como está
estruturada, como configurar o backend remoto, quais variáveis/segredos são necessários e como
aplicar e fazer deploy. Para desenvolvimento local do serviço, veja o
[README raiz](../README.md); para validar esta infraestrutura localmente com um emulador AWS, veja
[`infra/local/README.md`](./local/README.md).

## Visão geral da arquitetura

Instância única **EC2** (`t3.micro`, Amazon Linux 2023) rodando a aplicação via `docker compose`,
banco **RDS PostgreSQL**, imagens no **ECR**. Decisão registrada em
[`docs/adr/0001-deploy-aws-ec2.md`](../docs/adr/0001-deploy-aws-ec2.md) (MVP acadêmico: custo
mínimo, sem alta disponibilidade).

## Layout

```
infra/
├── stack/    # módulo compartilhado: TODOS os recursos (SG, EC2, EIP, RDS, ECR, IAM, OIDC, KMS, SSM)
├── main/     # raiz de produção — Terraform Cloud (bloco cloud), executada por .github/workflows/infra.yml
└── local/    # raiz de teste local — mesmo módulo apontado para o Floci, estado local
deploy/
├── docker-compose.prod.yml   # compose autocontido de produção (apenas migrations + app)
└── deploy.sh                 # executado na EC2 via SSM Run Command
```

Princípio de design: **a stack de produção nunca é modificada para emulação** — a raiz `local/`
apenas alterna variáveis do módulo (`aws_endpoint_url`, `create_github_oidc`). Ver detalhes de uso
local em [`infra/local/README.md`](./local/README.md).

## Recursos provisionados (módulo `stack`)

- **Security Group da aplicação:** entrada liberada apenas na porta `8000/tcp` (sem SSH — acesso
  via SSM), saída livre.
- **EC2 `t3.micro` + Elastic IP:** IMDSv2 obrigatório (hop limit 1), disco `gp3` criptografado;
  `user_data` instala Docker + plugin de compose fixado por versão, verificado via
  `sha256sum -c` contra o `checksums.txt` oficial do release.
- **RDS PostgreSQL 17** (`db.t4g.micro`, single-AZ, 20 GB `gp3` criptografado, sem acesso público);
  Security Group dedicado aceitando a porta 5432 **apenas do SG da aplicação**; senha master
  gerenciada pelo **Secrets Manager** (nunca aparece no state do Terraform); sem proteção contra
  exclusão nem snapshot final (MVP estudantil — o `destroy` precisa funcionar).
- **Repositório ECR** `vehicle-core-service`: scan automático no push, tags mutáveis (permite mover
  `latest`), `force_delete`, política de ciclo de vida mantendo as últimas 10 imagens.
- **Instance profile IAM:** `AmazonSSMManagedInstanceCore` + leitura do segredo master do RDS +
  pull no repositório ECR da aplicação (nenhuma credencial de registry em lugar nenhum).
- **Provider OIDC do GitHub + role de deploy** (`vehicle-core-service-deploy`): trust fixado em
  `repo:<org>/vehicle-core-service:ref:refs/heads/main` (`aud`/`sub` exatos, sem wildcard);
  política permite `ssm:SendCommand` (documento `AWS-RunShellScript`, instância filtrada por tag),
  `ssm:GetCommandInvocation`, `ec2:DescribeInstances` e autenticação/push no único repositório ECR.
- **KMS CMKs dedicadas** (rotação habilitada, ~US$ 1/mês cada):
  - `alias/vehicle-core-service-ssm`: cifra os parâmetros `SecureString` do SSM deste serviço em
    vez da chave padrão da conta (`alias/aws/ssm`). A política da chave concede `kms:Decrypt`
    apenas à role da instância (via SSM, na região) + delegação de administração para a conta
    root. A decriptação é transparente para o `deploy.sh` (`--with-decryption` sem alteração).
  - `alias/vehicle-core-service-rds`: cifra o storage do RDS **e** o segredo da senha master no
    Secrets Manager, referenciada explicitamente (`kms_key_id` /
    `master_user_secret_kms_key_id`). Sem chave explícita o RDS usaria as chaves gerenciadas
    `aws/rds` e `aws/secretsmanager`, inacessíveis à TFC run role de menor privilégio (todas as
    ações KMS dela são restritas a chaves com a tag `Service`) — o apply real falhava com
    `KMSKeyNotAccessibleFault`. A role da instância recebe `kms:Decrypt` via Secrets Manager para
    o `deploy.sh` ler a senha.

  Ambas as chaves recebem `tags` **explícitas** (não apenas via `default_tags`), porque as
  permissões KMS da run role são condicionadas por tag.

  > **Por que as ações de *uso* do KMS são condicionadas por `kms:ViaService`, e não por tag.**
  > A autorização por tag (ABAC) no KMS não é imediata: mudanças em tags e aliases
  > [podem levar até 5 minutos para afetar a autorização](https://docs.aws.amazon.com/kms/latest/developerguide/troubleshooting-tags-aliases.html).
  > No mesmo apply, o Terraform cria a chave e segundos depois o RDS chama `DescribeKey` sobre
  > ela em nome da run role — a tag ainda não vale para autorização e o apply falha com
  > `KMSKeyNotAccessibleFault` (confirmado via CloudTrail: `DescribeKey` negado com
  > `sourceIPAddress: rds.amazonaws.com`). Por isso as ações de uso (`DescribeKey`,
  > `CreateGrant`, `GenerateDataKey*`, `Encrypt`, `Decrypt`, `ReEncrypt*`) ficam num statement
  > condicionado por `kms:ViaService` — avaliado a partir do contexto da requisição, não do
  > estado das tags, portanto **efetivo imediatamente e imune ao atraso de propagação**. Continua
  > sendo menor privilégio: só vale para chamadas roteadas por EC2/EBS, RDS, Secrets Manager ou
  > SSM na região, nunca para uso direto da chave por um humano ou outro principal.
  >
  > **A mesma corrida existe nas chamadas diretas do Terraform logo após o `CreateKey`.** Com
  > `enable_key_rotation = true`, o provider chama `EnableKeyRotation` — e lê a chave com
  > `DescribeKey`, `GetKeyPolicy`, `GetKeyRotationStatus`, `ListResourceTags` — **segundos**
  > depois de criá-la. Essas cinco ações ficam no statement `KmsBootstrapAndReadKeys`,
  > condicionado apenas por `aws:RequestedRegion` (contexto da requisição, sem tag): são leituras
  > mais um único toggle de configuração **não destrutivo**, que rodam antes de a autorização por
  > tag propagar. O statement `KmsManageServiceKey` continua condicionado por tag e guarda apenas
  > o que é destrutivo ou altera acesso: `PutKeyPolicy`, `DisableKeyRotation`, `UntagResource`,
  > `ScheduleKeyDeletion`, `CancelKeyDeletion`, `Encrypt`, `Decrypt`, `GenerateDataKey`.
  >
  > **Regra geral, válida para qualquer permissão futura:** uma permissão KMS condicionada por tag
  > **nunca** pode guardar uma ação que roda no mesmo run do Terraform que cria a chave. Nesses
  > casos use condições de contexto da requisição (`aws:RequestedRegion`, `kms:ViaService`), que
  > são avaliadas na hora e não dependem de propagação de tags.
- **Parâmetros SSM** sob `/vehicle-core-service/*`:
  - `SecureString` com valores placeholder (definidos fora do Terraform, com `ignore_changes`),
    cifrados com o CMK dedicado: `SALES_SERVICE_BASE_URL`, `SALES_SERVICE_TIMEOUT_SECONDS`,
    `INTERNAL_API_TOKEN`, `SERVICE_NAME`, `DEBUG`, `LOG_LEVEL`. **O `deploy.sh` recusa o deploy
    (`exit 1`) se algum deles ainda estiver com o placeholder `CHANGE_ME`.**
  - `String` gerenciados pelo Terraform (derivados do RDS, não são segredos): `DATABASE_HOST`,
    `DATABASE_PORT`, `DATABASE_USER`, `DATABASE_NAME`, `DATABASE_PASSWORD_SECRET_ARN`.

Custo estimado: EC2 `t3.micro` (~US$ 8/mês) + RDS `db.t4g.micro` (~US$ 12/mês) + 36 GB `gp3`
(~US$ 4/mês) + 2 KMS CMKs (~US$ 2/mês); ECR/SSM/Secrets via RDS ~US$ 0. Ambas as instâncias são
elegíveis ao free tier em contas novas (depois disso, ~US$ 6/mês só de storage + KMS).

## Configuração do backend (Terraform Cloud / HCP Terraform)

A raiz `infra/main` usa um bloco `cloud {}` (execução e state remotos). Organização e workspace
vêm de variáveis de ambiente, não de variáveis do Terraform:

```bash
export TF_CLOUD_ORGANIZATION=<sua-organização-hcp-terraform>
export TF_WORKSPACE=vehicle-core-infra
```

### Configurações do workspace (UI da TFC)

- Workspace `vehicle-core-infra`, fluxo **CLI-driven** (sem conexão VCS).
- **Execution Mode:** Remote.
- **Apply Method:** Auto apply — o gate humano fica no ambiente `infra` do GitHub (revisores
  obrigatórios), não na TFC.
- **Terraform Working Directory:** `infra/main`. Com ele definido, a CLI precisa rodar a partir do
  diretório correspondente — o `infra.yml` já faz isso; o upload da configuração inclui `../stack`.

### Bootstrap do workspace (manual, uma única vez)

1. Criar o workspace na UI com as configurações da seção acima.
2. **Credenciais dinâmicas do provider são obrigatórias** — chaves AWS estáticas como variáveis de
   workspace são **proibidas**. Ver
   [Dynamic Provider Credentials da HCP Terraform para AWS](https://developer.hashicorp.com/terraform/cloud-docs/workspaces/dynamic-provider-credentials/aws-configuration).
3. Criar a **TFC run role** a partir dos arquivos de política já versionados no repositório
   (`infra/tfc-run-role-trust-policy.json` e `infra/tfc-run-role-policy.json`), usando uma
   identidade admin/bootstrap.

   > **O que é `run_phase`?** Todo run da TFC tem duas fases — `plan` e `apply` — e cada uma se
   > autentica na AWS separadamente: o token OIDC traz no campo `sub` o sufixo `run_phase:plan`
   > ou `run_phase:apply`. Exemplo de `sub` completo:
   > `organization:minha-org:project:Default Project:workspace:vehicle-core-infra:run_phase:apply`.
   > A trust policy versionada usa `run_phase:*` (`StringLike`), então **uma única role cobre as
   > duas fases e você não configura nada sobre `run_phase`** — o wildcard já está dentro do JSON
   > que você cola. A divisão em duas roles (`TFC_AWS_PLAN_ROLE_ARN`/`TFC_AWS_APPLY_ROLE_ARN`)
   > mostrada na
   > [doc oficial](https://developer.hashicorp.com/terraform/cloud-docs/dynamic-provider-credentials/aws-configuration)
   > só serve para dar permissões distintas por fase — fora do escopo aqui.

   Pela **CLI** (antes, edite os 3 placeholders em `tfc-run-role-trust-policy.json` — ver
   sub-passo 2 abaixo):

   ```bash
   cd infra
   aws iam create-open-id-connect-provider \
     --url https://app.terraform.io \
     --client-id-list aws.workload.identity \
     --thumbprint-list 9e99a48a9960b14926bb7f3b02e22da2b0ab7280

   aws iam create-role --role-name vehicle-core-infra-tfc \
     --assume-role-policy-document file://tfc-run-role-trust-policy.json

   aws iam put-role-policy --role-name vehicle-core-infra-tfc \
     --policy-name vehicle-core-infra-tfc-policy \
     --policy-document file://tfc-run-role-policy.json
   ```

   Ou pelo **console** (IAM), em vez da CLI:

   1. *Identity providers* → *Add provider* → tipo **OpenID Connect**, URL
      `https://app.terraform.io`, audience `aws.workload.identity` → *Get thumbprint* →
      *Add provider*. Em seguida, *Roles* → *Create role* → **Web identity** → provider
      recém-criado → crie a role e edite a trust policy colando o conteúdo integral de
      `tfc-run-role-trust-policy.json`.
   2. No JSON colado, substitua **exatamente 3 placeholders**: `<AWS_ACCOUNT_ID>` (ID numérico da
      conta), `<TFC_ORG>` (organização da HCP Terraform) e `<TFC_PROJECT>` (projeto que contém o
      workspace — `Default Project` caso você não tenha criado nenhum). Nada mais precisa mudar.
   3. Na role, *Add permissions* → *Create inline policy* → JSON, colando
      `tfc-run-role-policy.json` (ajuste `aws:RequestedRegion` se não usar `us-east-1`).
   4. Copie o **ARN da role** — ele é o valor de `TFC_AWS_RUN_ROLE_ARN` no passo 4 abaixo.

   - `tfc-run-role-trust-policy.json`: trust fixado em `aud = aws.workload.identity` e
     `sub = organization:<TFC_ORG>:project:<TFC_PROJECT>:workspace:vehicle-core-infra:run_phase:*`
     — org/projeto/workspace exatos, wildcard apenas em `run_phase` (ver callout acima).
   - `tfc-run-role-policy.json`: permissões de menor privilégio, restritas a recursos
     `vehicle-core-service*` sempre que a AWS permite. Ações de criação de EC2/KMS não
     restringíveis por nome usam `Resource: "*"`, mas fixadas em
     `aws:RequestedRegion = us-east-1` (edite o JSON se mudar `aws_region`);
     `ec2:TerminateInstances`/`ec2:StopInstances` exigem também a tag `Service =
     vehicle-core-service`; o gerenciamento das chaves KMS exige a mesma tag (aplicada na criação
     via `default_tags` do provider).

   > ⚠️ **Toda vez que `tfc-run-role-policy.json` mudar no repositório, re-cole o JSON na role.**
   > A inline policy da role **não** acompanha o git: o conteúdo do arquivo só chega à AWS quando
   > você o cola de novo (console: role `vehicle-core-infra-tfc` → *Permissions* → policy inline
   > → *Edit* → JSON → *Save*; ou repita o `aws iam put-role-policy` acima). Depois disso, rode o
   > `infra.yml` novamente. Sintoma típico de policy desatualizada: `AccessDenied` ou
   > `KMSKeyNotAccessibleFault` no apply.
   > Leia também
   > [A TFC run role e o ponto cego da validação local](#a-tfc-run-role-e-o-ponto-cego-da-validação-local)
   > — por que o Floci nunca pega esses erros e o que revisar a cada mudança na stack.

4. Variáveis do workspace na TFC:
   - Ambiente: `TFC_AWS_PROVIDER_AUTH=true` e
     `TFC_AWS_RUN_ROLE_ARN=<ARN da role vehicle-core-infra-tfc>`.
   - Terraform: `github_org` (obrigatória), opcionalmente `aws_region` / `instance_type`.
   - **Nunca** defina `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` no workspace — credenciais
     estáticas conflitam com a autenticação dinâmica.
5. Variáveis de ambiente para o `terraform init` em `infra/main` (a CI também as define):
   `TF_CLOUD_ORGANIZATION=<org>`, `TF_WORKSPACE=vehicle-core-infra` (o bloco `cloud {}` as lê).
6. Gerar um **token de time restrito ao time deste workspace** (nunca um token de usuário ou de
   organização inteira). Defina uma expiração (ex.: 90 dias) e rotacione periodicamente — ele
   será salvo no GitHub no passo 8.
7. Criar o **environment `infra` no GitHub** (nível de *Settings* do repositório — exige admin):
   *Settings* → *Environments* → *New environment* → nome `infra` (exato — o `infra.yml` o
   referencia) → habilite **Required reviewers** e adicione você mesmo → salve as regras de
   proteção. Sem esse environment o workflow ainda roda, porém **sem nenhum gate humano**; com
   ele, toda execução do `infra.yml` (apply **e** destroy) pausa aguardando aprovação. O
   environment é **apenas o gate de aprovação** — nenhum secret ou variável precisa ser criado
   dentro dele; tudo fica no nível do repositório (passo 8).
8. Configurar no GitHub (*Settings* → *Secrets and variables* → *Actions*, nível do repositório)
   o mínimo que o primeiro run do `infra.yml` exige:
   - Secret `TF_API_TOKEN` = token de time do passo 6.
   - Variável `TF_CLOUD_ORGANIZATION` = sua organização na HCP Terraform.
   - Variável `TF_WORKSPACE` = `vehicle-core-infra`.

   Os demais secrets/variáveis dependem de outputs do Terraform e só entram **depois** do
   primeiro apply (seção seguinte). A tabela consolidada fica em
   [Segredos e variáveis do GitHub Actions](#segredos-e-variáveis-do-github-actions).
9. Configurar o **SonarCloud**:
   1. Em [sonarcloud.io](https://sonarcloud.io), faça login com o GitHub → *Analyze new project* →
      importe o repositório `vehicle-core-service` (anote o *project key* e a *organization key*).
   2. No projeto → *Administration* → *Analysis Method* → **desligue Automatic Analysis**
      (obrigatório — conflita com a análise via CI e impede o envio de cobertura).
   3. *My Account* → *Security* → gere um token.
   4. No GitHub (mesmo caminho do passo 8): secret `SONAR_TOKEN` = token gerado; variáveis
      `SONAR_PROJECT_KEY` e `SONAR_ORGANIZATION` = chaves anotadas no sub-passo 1.

   Comportamento: sem `SONAR_TOKEN`, os steps do Sonar são pulados sem quebrar a CI/CD; com ele,
   o CI analisa PRs e o CD **bloqueia o deploy** se o quality gate do Sonar reprovar. O primeiro
   push/merge na `main` cria a baseline de análise.

### Primeiro apply → secrets/variáveis pós-apply (destravam o `cd.yml`)

1. Rode o workflow `infra.yml` (ou, a partir de `infra/main`: `terraform init && terraform apply`
   com as variáveis de ambiente acima).
2. Com os outputs do apply, configure no GitHub (mesmo caminho do passo 8 do bootstrap — nível do
   repositório):
   - Secret `AWS_ROLE_ARN` = output `deploy_role_arn`.
   - Variável `AWS_REGION` = mesma região de `aws_region` (`us-east-1` por padrão).
   - Variável opcional `APP_PUBLIC_IP` = output `elastic_ip` (usada no smoke test externo da CD).
3. Esses valores destravam o `cd.yml` (deploy), não o `infra.yml`: até o secret `AWS_ROLE_ARN`
   existir, o job de deploy da CD não consegue assumir a role (efeito ovo-e-galinha esperado).

## Aplicando a infraestrutura

Manualmente, a partir de `infra/main`:

```bash
cd infra/main
terraform init -input=false
terraform validate
terraform plan -input=false
terraform apply -auto-approve -input=false
```

Ou disparando o workflow **Infra** (`workflow_dispatch`) no GitHub Actions — protegido pelo
ambiente `infra` (requer revisores aprovadores configurados em *Settings > Environments*) e, para
`destroy`, pela confirmação explícita do input `confirm = vehicle-core-service`.

## A TFC run role e o ponto cego da validação local

> # ⚠️ RE-COLE A POLICY NA AWS APÓS **TODA** MUDANÇA EM `tfc-run-role-policy.json`
>
> A inline policy da role `vehicle-core-infra-tfc` **não acompanha o git**. O arquivo versionado
> só chega à AWS quando você o cola de novo:
>
> ```bash
> cd infra
> aws iam put-role-policy --role-name vehicle-core-infra-tfc \
>   --policy-name vehicle-core-infra-tfc-policy \
>   --policy-document file://tfc-run-role-policy.json
> ```
>
> Ou no console: IAM → *Roles* → `vehicle-core-infra-tfc` → *Permissions* → policy inline →
> *Edit* → JSON → *Save*. Só depois rode o `infra.yml` de novo. **Sintoma clássico de policy
> desatualizada: `AccessDenied` ou `KMSKeyNotAccessibleFault` no apply.**

### O Floci não valida autorização IAM

O emulador aceita **qualquer** credencial e autoriza **toda** chamada — ele não implementa o motor
de autorização do IAM. Consequência prática: falhas de `AccessDenied` são **estruturalmente
invisíveis** na validação local. Um `floci-validate.sh` verde prova apenas que o grafo de recursos
e o formato dos argumentos estão corretos; **não prova absolutamente nada sobre permissões**. O
único teste real da run role é um `apply`/`destroy` contra a AWS de verdade.

### Regra para toda mudança em `infra/stack/`

Todo recurso ou argumento novo adicionado a `infra/stack/` exige uma **revisão casada** de
`infra/tfc-run-role-policy.json`. A policy é de menor privilégio escrita à mão e **não falha no
`plan`** — o `terraform plan` não consulta o IAM, então a lacuna de permissão só aparece no meio do
`apply`, com recursos parcialmente criados.

### Cuidado com permissões exigidas do *chamador* para efeitos colaterais do serviço

Alguns serviços da AWS executam ações em recursos de outros serviços **usando as permissões de quem
chamou**, mesmo que esses recursos não existam no código Terraform. Caso concreto deste projeto:

- `manage_master_user_password = true` em `aws_db_instance.app` faz o **RDS criar um segredo no
  Secrets Manager em nome do principal chamador**. Por isso a run role precisa de
  `secretsmanager:CreateSecret`, `secretsmanager:TagResource` (criar/modificar/restaurar) e
  `secretsmanager:RotateSecret` (modificar/rotacionar) — **mesmo não existindo nenhum recurso
  `aws_secretsmanager_secret` na stack**. Sem isso o apply falha com
  `RDS CreateDBInstance ... AccessDenied: The user isn't authorized to create a secret in AWS
  Secrets Manager`.
- O statement `RdsManagedMasterSecret` cobre o ciclo de vida completo do segredo e usa o recurso
  `arn:aws:secretsmanager:*:*:secret:rds!*` — exatamente o padrão documentado pela AWS. O prefixo
  `rds!` é **reservado a segredos criados pelo RDS**, então o escopo continua mínimo. Sem
  `Condition` por tag de recurso: no `CreateSecret` o recurso ainda não existe e é o próprio RDS
  quem aplica a tag `aws:secretsmanager:owningService`.
- Referência: [Password management with Amazon RDS and AWS Secrets Manager](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-secrets-manager.html#rds-secrets-manager-permissions).

### Escalada de privilégio via `iam:AttachRolePolicy` (fechada)

Cadeia de exploração que existia na policy e foi eliminada: `iam:CreateRole` em
`role/vehicle-core-service-*` → `iam:AttachRolePolicy` **sem condição de `iam:PolicyARN`** (ou seja,
`arn:aws:iam::aws:policy/AdministratorAccess` era permitido) → `CreateInstanceProfile` +
`AddRoleToInstanceProfile` → `iam:PassRole` para `ec2.amazonaws.com` + `ec2:RunInstances` → o IMDS
da instância entrega credenciais de Administrator. Comprometimento total da conta a partir de um run
da TFC.

Correção: `iam:AttachRolePolicy` / `iam:DetachRolePolicy` saíram de `IamManageServiceRoles` para o
statement próprio `IamAttachSsmManagedPolicyOnly`, condicionado por
`ArnEquals { "iam:PolicyARN": "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore" }` — a única
managed policy que a stack realmente anexa (`infra/stack/main.tf`, `aws_iam_role_policy_attachment.instance_ssm`).

> ⚠️ **Restrição criada por essa condição — leia antes de mexer em IAM na stack.** Se qualquer `.tf`
> futuro anexar uma managed policy **diferente**, o apply vai falhar com `AccessDenied` em
> `iam:AttachRolePolicy`. É exatamente o comportamento desejado (a condição existe para isso), mas
> significa que **anexar uma nova managed policy exige estender o array de `iam:PolicyARN` neste
> statement e re-colar o JSON na AWS**. Policies *inline* (`aws_iam_role_policy`) não passam por
> essa condição e continuam funcionando sem alteração.

Limitação conhecida e aceita: `iam:PutRolePolicy` continua sem condição sobre
`role/vehicle-core-service-*` — a stack precisa dele para as policies inline
(`instance_db_secret`, `instance_ecr_pull`, `deploy`) e o IAM **não oferece chave de condição sobre
o conteúdo do documento inline**. Portanto a mesma escalada ainda é teoricamente alcançável por
`PutRolePolicy` + `PassRole` + `RunInstances`. O que a correção acima elimina é o caminho trivial de
um clique; o risco residual é inerente a dar permissão de IAM a uma run role de Terraform e só seria
removível tirando a criação de roles do escopo do Terraform.

### Condições por tag (ABAC) nunca guardam ações do mesmo run que cria o recurso

A autorização por tag no KMS não é imediata —
[mudanças em tags e aliases podem levar até 5 minutos para afetar a autorização](https://docs.aws.amazon.com/kms/latest/developerguide/troubleshooting-tags-aliases.html).
Este projeto já foi mordido por isso **duas vezes**, com a mesma causa raiz:

1. O RDS chamando `DescribeKey` sobre a CMK recém-criada em nome da run role →
   `KMSKeyNotAccessibleFault`. Resolvido movendo as ações de *uso* para um statement condicionado
   por `kms:ViaService`.
2. O provider chamando `EnableKeyRotation` (e os `Get*`/`Describe*` de leitura) segundos depois do
   `CreateKey`. Resolvido movendo essas cinco ações para `KmsBootstrapAndReadKeys`, condicionado
   apenas por `aws:RequestedRegion`.

> **Regra:** uma permissão KMS condicionada por tag **nunca** pode guardar uma ação executada no
> mesmo run do Terraform que cria a chave. Use condições de contexto da requisição
> (`aws:RequestedRegion`, `kms:ViaService`) nesses casos — elas são avaliadas na hora, sem depender
> de propagação. Reserve a condição por tag para o que é destrutivo ou altera acesso
> (`PutKeyPolicy`, `ScheduleKeyDeletion`, `UntagResource`, `Disable*`, uso direto da chave).

O detalhamento completo está no callout da seção
[Recursos provisionados](#recursos-provisionados-módulo-stack).

### O caminho de `destroy` nunca foi exercitado contra a AWS real

As ações abaixo existem na policy, mas **permanecem não verificadas até o primeiro destroy real**:

| Recurso | Ações de destruição na policy |
|---|---|
| RDS | `rds:DeleteDBInstance`, `rds:DeleteDBSubnetGroup` |
| EC2 / EIP / SG | `ec2:TerminateInstances`, `ec2:ReleaseAddress`, `ec2:DisassociateAddress`, `ec2:DeleteSecurityGroup` |
| KMS | `kms:ScheduleKeyDeletion`, `kms:DeleteAlias` |
| IAM | `iam:DeleteRole`, `iam:DeleteRolePolicy`, `iam:DeleteInstanceProfile`, `iam:DeleteOpenIDConnectProvider` |
| ECR | `ecr:DeleteRepository` + `ecr:BatchDeleteImage` (`force_delete = true`) |
| SSM | `ssm:DeleteParameter` |
| Secrets Manager | `secretsmanager:DeleteSecret` (segredo master do RDS) |

Ao rodar o primeiro `destroy`, trate qualquer `AccessDenied` como lacuna da policy — não como bug
do Terraform — e siga o mesmo procedimento: corrigir o JSON, **re-colar na AWS**, repetir.

## Variáveis de ambiente e segredos

Todos os nomes abaixo correspondem exatamente ao arquivo
[`service/env.example`](../service/env.example) do serviço. **Nunca** commite valores reais —
apenas os nomes das chaves.

| Variável | Descrição | Exemplo | Origem em produção |
|---|---|---|---|
| `DATABASE_HOST` | Host do PostgreSQL | `vehicle-core-db.xxxxx.us-east-1.rds.amazonaws.com` | Terraform (endpoint do RDS) |
| `DATABASE_PORT` | Porta do PostgreSQL | `5432` | Terraform (porta do RDS) |
| `DATABASE_USER` | Usuário de conexão com o banco | `vehicle_core_user` | Terraform (usuário master do RDS) |
| `DATABASE_PASSWORD` | Senha de conexão com o banco | *(gerada, não versionada)* | Secrets Manager, referenciado pela SSM `DATABASE_PASSWORD_SECRET_ARN`; materializada em runtime pelo `deploy.sh` |
| `DATABASE_NAME` | Nome do banco de dados | `vehicle_core` | Terraform (nome do banco no RDS) |
| `SALES_SERVICE_BASE_URL` | URL base do `vehicle-sales-service` | `http://vehicle-sales-service:8000` | SSM `SecureString` (`CHANGE_ME` até ser definida manualmente) |
| `SALES_SERVICE_TIMEOUT_SECONDS` | Timeout, em segundos, das chamadas HTTP ao serviço de vendas | `5.0` | SSM `SecureString` |
| `INTERNAL_API_TOKEN` | Token compartilhado exigido no header `X-Internal-Token` das rotas internas entre serviços | *(string aleatória com 32+ bytes)* | SSM `SecureString` |
| `SERVICE_NAME` | Nome do serviço usado em logs e no health check | `vehicle-core-service` | SSM `SecureString` |
| `DEBUG` | Habilita modo debug (echo de SQL, logs verbosos) | `false` | SSM `SecureString` |
| `LOG_LEVEL` | Nível mínimo de log | `INFO` | SSM `SecureString` |

As variáveis marcadas como SSM `SecureString` nascem com o placeholder `CHANGE_ME` (definido pelo
Terraform) e **precisam ser configuradas fora do Terraform**, uma vez por ambiente:

```bash
aws ssm put-parameter --overwrite --type SecureString \
  --name /vehicle-core-service/INTERNAL_API_TOKEN --value '<token aleatório com 32+ bytes>'
# repita para: SALES_SERVICE_BASE_URL, SALES_SERVICE_TIMEOUT_SECONDS,
#              SERVICE_NAME, DEBUG, LOG_LEVEL
```

`DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_USER` e `DATABASE_NAME` são escritos automaticamente
pelo Terraform — nada a fazer. `DATABASE_PASSWORD` nunca fica no SSM: vive no segredo gerenciado
pelo RDS no Secrets Manager, referenciado pelo parâmetro `DATABASE_PASSWORD_SECRET_ARN`.

### Segredos e variáveis do GitHub Actions

| Nome | Tipo | Descrição |
|---|---|---|
| `AWS_ROLE_ARN` | Secret do repositório | ARN da role OIDC de deploy (output `deploy_role_arn` do Terraform) |
| `AWS_REGION` | Variável do repositório | Região AWS, deve coincidir com `aws_region` do Terraform |
| `TF_API_TOKEN` | Secret do repositório | Token de time da HCP Terraform, usado pelo workflow `infra.yml` |
| `TF_CLOUD_ORGANIZATION` | Variável do repositório | Organização na HCP Terraform |
| `TF_WORKSPACE` | Variável do repositório | Nome do workspace (`vehicle-core-infra`) |
| `SONAR_TOKEN` | Secret do repositório | Token do SonarCloud (passo 9 do bootstrap); se ausente, os steps de análise são pulados sem quebrar a CI/CD |
| `SONAR_PROJECT_KEY` / `SONAR_ORGANIZATION` | Variáveis do repositório | Identificação do projeto no SonarCloud (passo 9 do bootstrap) |
| `APP_PUBLIC_IP` | Variável do repositório (opcional) | IP público (Elastic IP) usado no smoke test externo pós-deploy da CD |

## Deploy (`deploy/`)

O deploy é feito pelo workflow `cd.yml` a cada push em `main`: build e push da imagem para o ECR,
depois execução remota na instância EC2 via **AWS Systems Manager (SSM Run Command)** — não há SSH
nem checkout de repositório na instância.

- **`deploy/docker-compose.prod.yml`** — compose autocontido para a EC2: usa a imagem já publicada
  no ECR (`APP_IMAGE`) em vez de `build:`. Diferenças em relação ao `docker-compose.yml` de
  desenvolvimento local: sem serviço `postgres` (o banco é o RDS) e sem serviço `seed` (dados de
  demonstração nunca são inseridos em produção). Sobe `migrations` (`alembic upgrade head`) e depois
  o serviço da aplicação, com healthcheck em `/health`.
- **`deploy/deploy.sh`** — script executado na instância pelo comando SSM:
  1. Materializa `/opt/vehicle-core-service/.env` lendo os parâmetros SSM listados acima
     (`--with-decryption`) mais a senha do banco obtida do Secrets Manager via role da instância.
     Nenhum valor passa pelos parâmetros do `SendCommand` nem é logado.
  2. Recusa o deploy se qualquer parâmetro SSM ainda estiver com o valor `CHANGE_ME`.
  3. Garante a rede Docker compartilhada `vehicle-platform` (usada também pelo
     `vehicle-sales-service`).
  4. Autentica no ECR usando a role da instância, faz `pull` da imagem recebida como argumento e
     sobe a stack com `docker compose -f docker-compose.prod.yml up -d`.
  5. Aguarda `/health` responder; falha o comando SSM (e o job da CD) se o serviço não ficar
     saudável.

O workflow `cd.yml` envia `deploy.sh` e `docker-compose.prod.yml` do próprio checkout para a
instância (em base64, pelo canal do SSM) antes de executar o deploy — o `user_data` da EC2 apenas
prepara o Docker, o repositório é a fonte da verdade dos artefatos de deploy.

## Referências

- [`docs/adr/0001-deploy-aws-ec2.md`](../docs/adr/0001-deploy-aws-ec2.md) — decisão de arquitetura
  de infraestrutura, alternativas rejeitadas e riscos aceitos.
- [README raiz](../README.md) — visão geral do serviço, arquitetura de código e execução local.
- [`infra/local/README.md`](./local/README.md) — validação local da infraestrutura com o Floci.
