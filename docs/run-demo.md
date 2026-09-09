# Como executar a PEC demo

Este procedimento inicia uma instância local descartável a partir do
`base.backup` sintético versionado no repositório. Não use o backup nem a
instância resultante em produção.

## Pré-requisitos

- Docker Engine com Docker Compose;
- Git LFS, para obter o arquivo de backup;
- o JAR `eSUS-AB-PEC-<versão>-Linux64.jar` compatível com o backup (a versão
  ativa está fixada em `scripts/demo/pack/pack.json` e documentada em
  `scripts/demo/README.md`, seção "Versão atual").

Na raiz do projeto:

```sh
git lfs pull
cp cloud/.env.example cloud/.env
```

Revise `cloud/.env`, especialmente `APP_PORT` se a porta `8082` já estiver em
uso.

## Restaurar o backup-base

O backup em `scripts/demo/pack/base.backup` requer o PEC na versão fixada em
`scripts/demo/pack/pack.json` (`pec_version`). Informe explicitamente o JAR
correspondente:

```sh
make restore \
  BACKUP="$PWD/scripts/demo/pack/base.backup" \
  JAR=/caminho/para/eSUS-AB-PEC-<versão>-Linux64.jar
```

`JAR` só pode ser omitido se `FILENAME` em `cloud/.env` já apontar para o JAR
dessa mesma versão:

```sh
make restore \
  BACKUP="$PWD/scripts/demo/pack/base.backup"
```

Sem `JAR` nem `FILENAME`, o comando baixa a versão mais recente disponível do
PEC. Não use essa alternativa para a demo, pois essa versão pode não ser a
mesma do pack e tornar o banco incompatível.

O comando encerra os containers do projeto, constrói a imagem, inicia o
PostgreSQL, recria o banco `esus`, restaura o backup e inicia o PEC.

## Acompanhar e acessar

```sh
docker compose -f cloud/compose.yml --env-file cloud/.env logs -f pec
```

Com a configuração padrão, acesse [http://localhost:8082](http://localhost:8082).
Se `APP_PORT` foi alterada, substitua `8082` pela porta escolhida.

Se o PEC informar incompatibilidade de versão, o JAR não corresponde ao
backup. Use o JAR 5.5.22 ou verifique `VERSAOBANCODADOS` e o JAR utilizado.

## Demonstração hospedada e credenciais

O repositório não contém a URL nem as credenciais da demonstração hospedada.
Publique apenas credenciais sintéticas e mantenha-as fora do backup-base quando
precisar rotacioná-las. Consulte [Comandos `make`](makefile.md) para os demais
fluxos operacionais.

## Atualizar uma demo sem microáreas

Não preencha `tb_cidadao` nem tabelas de fatos manualmente. A fábrica distribui
os dez cidadãos sintéticos entre as duas equipes e as microáreas `01`, `02` e
`03` usando a mutation oficial do PEC, que gera a FCI e seus derivados.

Gere e valide um novo backup em ambiente isolado:

```sh
sh scripts/demo/build-demo-backup.sh \
  --output "$PWD/scripts/demo/output/pec-demo-com-microareas.backup"
```

Faça antes um backup recuperável da cloud e agende uma janela de manutenção:
`make restore` recria o banco `esus`. Depois da restauração do backup validado,
abra o Console MCP, selecione cada equipe e confirme que as microáreas `01`,
`02` e `03` aparecem. Isso preserva a coerência entre cadastro territorial,
FCI e fatos que alimentam os filtros do MCP.
