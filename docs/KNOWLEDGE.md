# Base de Conhecimento Operacional do e-SUS PEC

## Configurações do Sistema

### Tabela principal de configuração

As configurações globais do e-SUS-PEC ficam na tabela `tb_config_sistema` do banco `esus`:

```sql
SELECT co_config_sistema, ds_config_sistema, ds_texto, ds_inteiro
FROM tb_config_sistema;
```

### Campos críticos

| chave | descrição | nota |
|-------|-----------|------|
| `LINKINSTALACAO` | Endereço URI base da instalação | Define as rotas internas; deve apontar para a URL de acesso local (ex: `http://localhost:8082`) |
| `VERSAOBANCODADOS` | Versão do banco de dados | Deve ser compatível com a versão do JAR do app |
| `TIPOINSTALACAO` | Tipo: `PRONTUARIO` ou `CENTRALIZADORA` | Define o modo de operação |
| `NOMEINSTALACAO` | Nome da instalação | Identificador textual |
| `HORUSHABILITADO` / `CADSUSHABILITADO` | Integrações com Hórus / CADSUS | Desabilitar se não usar |

### Arquivos de configuração dentro do container

- `/etc/pec.config` — JSON com metadata da instalação (criado na primeira inicialização). Usado pelo `scripts/entrypoint.sh` para verificar se o sistema já foi instalado.
- `/opt/e-SUS/webserver/config/application.properties` — Configuração Spring Boot (apenas datasource: usuário, senha, URL do banco).

## Versão do App vs Versão do Banco

O e-SUS-PEC verifica compatibilidade na inicialização (`StartupListener` → `SystemVersionService.ensureCompatibleVersions`). Se as versões não coincidirem, a aplicação falha com:

```
O PEC e o seu banco de dados não estão na mesma versão.
```

Verificar:

```sql
-- Versão do banco
SELECT ds_texto FROM tb_config_sistema WHERE co_config_sistema = 'VERSAOBANCODADOS';
```

A versão do app está embutida no JAR (ex: `pec-bundle.jar:5.4.21`).

## Como acessar o banco via docker compose

```bash
# Listar bancos
docker compose exec db psql -U postgres -c "\l"

# Listar tabelas do banco esus
docker compose exec db psql -U postgres -d esus -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;"

# Consultar configurações do sistema
docker compose exec db psql -U postgres -d esus -c "SELECT * FROM tb_config_sistema;"

# Atualizar URL base
docker compose exec db psql -U postgres -d esus -c \
  "UPDATE tb_config_sistema SET ds_texto = 'http://localhost:8082' WHERE co_config_sistema = 'LINKINSTALACAO';"

# Verificar versão do banco
docker compose exec db psql -U postgres -d esus -c \
  "SELECT ds_texto FROM tb_config_sistema WHERE co_config_sistema = 'VERSAOBANCODADOS';"

# Verificar configurações específicas
docker compose exec db psql -U postgres -d esus -c \
  "SELECT co_config_sistema, ds_texto FROM tb_config_sistema WHERE co_config_sistema IN ('LINKINSTALACAO','VERSAOBANCODADOS','TIPOINSTALACAO','NOMEINSTALACAO');"
```

## Como verificar logs do app

```bash
# Logs da aplicação
docker compose exec pec cat /opt/e-SUS/webserver/logs/pec.log

# Logs recentes
docker compose logs -f pec

# Reiniciar app após alterações de config
docker compose restart pec
```

## Healthcheck HTTP do container PEC

Na versão 5.5.22, o endpoint mais apropriado para um healthcheck sem credenciais é
`GET /api/public/info` na porta interna `8080` do Spring Boot. A rota é marcada
como pública na configuração do Spring Security e é usada pelo próprio PEC para
validar a comunicação com outras instalações. O `InfoController` só responde
depois que a aplicação foi inicializada; durante a criação do componente que
fornece seus dados, o PEC carrega de `tb_config_sistema` valores como UUID, tipo
de instalação e `LINKINSTALACAO`.

A imagem instala `wget`, portanto o Compose pode testar diretamente o backend,
sem depender das portas publicadas no host:

```yaml
healthcheck:
  test: ["CMD", "wget", "--quiet", "--tries=1", "--timeout=5", "--output-document=/dev/null", "http://127.0.0.1:8080/api/public/info"]
  interval: 30s
  timeout: 10s
  retries: 5
  start_period: 5m
```

O bundle também contém Spring Boot Actuator e expõe `/actuator/**`, mas todas
essas rotas exigem o papel `ACTUATOR`. O usuário é fixo
`spring-actuator-admin`, enquanto a senha é um UUID aleatório gerado em cada
inicialização e não possui configuração externa no codebase 5.5.22. Por isso,
`/actuator/health` não é um alvo operacional estável para o Docker Compose sem
alterar o aplicativo.

Limite: `/api/public/info` é um bom teste de prontidão na inicialização, inclusive
porque a inicialização dos dados do endpoint consulta o banco, mas as informações
ficam em cache. Após a aplicação estar pronta, o endpoint não comprova a saúde
contínua do PostgreSQL. Para distinguir os dois estados, mantenha também um
healthcheck próprio no serviço `db` com `pg_isready`.

## Fluxo de restauração de backup

1. Executar `make restore BACKUP=<backup>` para reconstruir a imagem e restaurar o banco
2. Verificar se a versão do JAR bate com a versão no banco (`VERSAOBANCODADOS`)
3. Atualizar `LINKINSTALACAO` para a URL local
4. Reiniciar o container: `docker compose restart pec`
5. Verificar logs: `docker compose logs pec`

O `scripts/build.sh` aplica automaticamente o `compose.override.yml` localizado no mesmo
diretório do arquivo Compose selecionado. Isso é necessário porque o uso explícito
de `docker compose -f <arquivo>` não carrega o override implicitamente. No modo
cloud, portanto, `cloud/compose.yml` e `cloud/compose.override.yml` são combinados
em todas as etapas, incluindo `down`, build, restauração e `up`.

## Problemas comuns

- **Rotas não funcionam**: geralmente `LINKINSTALACAO` ainda aponta para a URL de produção
- **App não inicia**: version mismatch entre JAR e banco de dados
- **Erro de EntityManager**: consequência do version mismatch — o app falha na inicialização e fecha o EntityManagerFactory
- **Instalador não conecta no PostgreSQL** com `authentication type 10 is not supported`: o driver do instalador PEC pode não suportar autenticação SCRAM. Para banco local em Docker, inicializar PostgreSQL com autenticação host MD5 e `password_encryption=md5`.

## Compatibilidade com PostgreSQL

O instalador PEC pode usar driver PostgreSQL sem suporte a SCRAM-SHA-256. Em PostgreSQL moderno, isso aparece como:

```
The authentication type 10 is not supported.
```

Para bancos locais criados pelo Docker Compose, usar:

```yaml
command: ["postgres", "-c", "password_encryption=md5"]
environment:
  - POSTGRES_INITDB_ARGS=--auth-host=md5
```

Essa configuração só afeta a inicialização de um volume novo. Se o volume do PostgreSQL já foi criado com SCRAM, recriar o volume ou redefinir a senha do usuário com `password_encryption=md5`.

## JAR, latest release e instalação persistida

O `Makefile` é a interface operacional pública do repositório. Os alvos
`training`, `production`, `external`, `cloud`, `restore`, `update-local`,
`update-external` e `codebase` delegam para os scripts versionados em
`scripts/`. Chamadas diretas aos scripts ficam reservadas para depuração e
automações que precisem das flags de baixo nível.

O arquivo `.env.example` é o modelo único da instalação local. O alvo
`training` respeita `TRAINING` (padrão `true`), enquanto `production` e
`external` forçam o modo de produção. O modelo cloud continua separado em
`cloud/.env.example` porque possui portas e caminhos próprios.

Na atualização, `scripts/update.sh` usa `POSTGRES_HOST` e `POSTGRES_PORT` do
ambiente tanto para banco local quanto externo; não deve fixar o hostname do
serviço Docker local.

`scripts/build.sh` só busca o latest release quando `filename` está vazio. A origem do JAR pode ser:

- `-f <arquivo-ou-url>`
- `FILENAME` no `.env` ou `cloud/.env`
- `scripts/get-latest-pec-release.sh --url-only`, quando nenhum JAR foi informado

Para instalação direta, fora de container, o helper
`helpers/linux-standalone-instalation/linux-install.sh` automatiza Ubuntu/Debian
x86_64 com systemd. O fluxo é dividido em duas etapas: primeiro instala o
cliente PostgreSQL, valida conexão e, quando solicitado, restaura um backup com
`pg_restore`; somente depois instala Java 17 e fontes, descobre o último
instalador Linux64 no SISAPS e executa o JAR em modo console. Falha na
restauração impede o início da etapa Java/PEC. O domínio de
`-cert-domain` deve ser somente o hostname; o helper aceita uma URL
`https://...` na entrada e a normaliza. O JAR instala o runtime em `/opt/e-SUS`,
gera `webserver/standalone.sh` e inclui a unidade `e-SUS-PEC.service`, que deve
ser habilitada e iniciada pelo systemd.

O cliente da distribuição pode ser antigo demais para o arquivo: por exemplo,
`pg_restore` 14 rejeita com `unsupported version (1.16) in file header` um dump
custom criado pelo PostgreSQL 17. O helper instala por padrão
`postgresql-client-17`, adicionando o repositório oficial PGDG quando necessário,
e usa os binários em `/usr/lib/postgresql/17/bin`. A versão pode ser alterada
com `PEC_POSTGRES_CLIENT_MAJOR`.

A restauração standalone preserva o fluxo operacional histórico com formato
custom (`-Fc`), `--clean --if-exists`, `--no-owner`, `--verbose` e
`--exclude-schema=pg_catalog`. Como `--clean` pode substituir objetos de um
banco existente, o helper exige uma confirmação destrutiva específica. A senha
é solicitada pelo próprio `pg_restore` no terminal. O stderr completo continua
visível e é gravado em `restore_full.log`; as linhas contendo erro ou warning
no prefixo de severidade do `pg_restore` são separadas em
`restore_warn_error.log`. O filtro deve ser ancorado em
`^pg_restore: (error|warning|erro|aviso):`; uma busca solta por `erro` captura
falsos positivos em objetos legítimos como `tb_*_erro` e `ds_mensagem_erro`.
Se o comando terminar com código não zero, o helper não decide automaticamente
que a restauração é utilizável: mostra
no terminal o conteúdo de `restore_warn_error.log`, informa os caminhos dos dois
relatórios e pede ao administrador para interromper ou continuar com a instalação
Java/PEC. Continuar é a resposta padrão (`S/n`), mantendo a opção de interromper
quando o relatório indicar falha relevante.

O helper standalone não solicita senha administrativa: deve ser executado como
`root` ou por usuário com `sudo` configurado como `NOPASSWD`. A validação usa
`sudo -n true` e falha imediatamente quando o sudo exigiria autenticação. Isso
não afeta os prompts próprios da senha do PostgreSQL.

Funções shell usadas por substituição de comando devem reservar `stdout` para o
valor retornado. Em especial, `download_installer` retorna somente o caminho do
JAR no stdout e envia mensagens como “Baixando” ou “Usando instalador” ao
stderr. Caso contrário, `jar_path=$(download_installer ...)` incorpora a
mensagem e a quebra de linha ao nome do arquivo, levando o Java a informar
`Unable to access jarfile` mesmo quando o JAR existe. Antes da execução, o
helper também rejeita caminho com quebra de linha, inexistente ou sem leitura.

O portal SISAPS atual, às vezes, anuncia somente a família da versão no botão da página
inicial (por exemplo, `5.5`) e mantém o link completo do instalador no handler
JavaScript desse botão. A descoberta do latest release deve usar essa família
para selecionar o link Linux no chunk da página inicial; procurar o primeiro
link Linux do bundle pode retornar uma versão legada que ainda esteja empacotada.
O caminho das notas segue `docs/Versoes/versao_<major>_<minor>`.

No modo cloud, `/opt/e-SUS` é persistido por bind mount:

```yaml
./esus-data/opt:/opt/e-SUS
```

Rebuild da imagem pode copiar um JAR novo para `/var/www/html`, mas isso não garante substituição do webserver já instalado em `/opt/e-SUS/webserver`. Quando houver mismatch, verificar:

```bash
docker compose exec db psql -U postgres -d esus -c \
  "SELECT ds_texto FROM tb_config_sistema WHERE co_config_sistema = 'VERSAOBANCODADOS';"

unzip -l cloud/esus-data/opt/webserver/pec-bundle.jar | grep 'backend-'
```

Se o webserver persistido estiver em versão antiga, preservar chaves/configurações necessárias e recriar ou limpar a instalação persistida antes de reinstalar.
"⚠️ Atenção ao atualizar para produção: o valor antigo (https://esus.dominio.com.br) pode ser restaurado quando necessário."

## Resolução de profissional CDS (CdsProfissionalServiceImpl)

O PEC resolve `tb_cds_prof` por **hash SHA1** gerado a partir de `CNS + CBO + CNES + INE` (`CdsEncrypt.generateSHA1CdsProf`). Não é lookup por INE/CNES soltos.

### Fluxo de criação
- `saveProfissional()` gera hash do CNS da lotação → tenta `loadProfissional(hash)` → se não encontra, cria novo registro em `tb_cds_prof`
- O hash é único por combinação CNS+CBO+CNES+INE

### Fluxo de exibição
- `loadUnicaLotacaoHeaderForm(co_seq_cds_prof)` carrega o header do CDS e faz join com `tb_prof_historico_cns` para recuperar CPF/CNS
- A listagem de fichas (`FichaAtendimentoIndividualRowItemPagingQuery`) usa `cdsProfissionalPrincipal` da ficha e exibe CNS, CBO, CNES e INE

### Known Issue: CNS duplicado em `tb_prof_historico_cns`
Se o mesmo CNS aparece no `tb_prof_historico_cns` de **dois profissionais diferentes**, a query de exibição retorna o primeiro encontrado (não necessariamente o correto). Sintomas:
- Atendimentos de um profissional aparecem com nome de outro na interface
- Módulo CDS Individual fica inacessível ("Funcionalidade não acessivel")

**Diagnóstico:**
```sql
-- Buscar CNS duplicados entre profissionais diferentes
SELECT ph.nu_cns, COUNT(DISTINCT ph.co_prof) AS num_perfis
FROM tb_prof_historico_cns ph
GROUP BY ph.nu_cns
HAVING COUNT(DISTINCT ph.co_prof) > 1;
```

**Correção:** Remover o registro errôneo de `tb_prof_historico_cns` (scripts em `scripts/fix-alynne-cds-prof.sql`).

## INE como identificador de equipe

O campo `nu_ine` em `tb_equipe` é o **número da equipe ESF**, não um identificador único de profissional. Múltiplos profissionais compartilham o mesmo INE quando pertencem à mesma equipe. O campo `nu_ine` em `tb_cds_prof` reflete o INE da equipe de lotação do profissional.

## Tabela `tb_prof_historico_cns`

Armazena o histórico de CNS vinculados a cada profissional (`co_prof`). Usada pela aplicação para:
- Recuperar CPF/CNS do profissional CDS na exibição de fichas
- Validar CNS durante cadastro

**Regra:** Cada CNS deve aparecer em apenas UM `co_prof`. Duplicação entre profissionais diferentes causa confusão na resolução de nome.

## Known Issues

### Conflito de Identificação por CNS em `tb_prof_historico_cns`

**Problema:**
Ocorrem inconsistências na exibição do nome do profissional e no acesso a módulos (como Ficha de Atendimento Individual) quando um mesmo número de CNS está associado a mais de um profissional na tabela `tb_prof_historico_cns`.

**Causa:**
A aplicação utiliza o CNS para resolver a identidade do profissional no banco de dados. Se um registro de identificação (como o histórico de um médico) contiver um CNS que também pertence a outro profissional, a consulta pode retornar o registro incorreto (ex: exibir o nome do médico A no prontuário da médica B).

**Solução:**
Garantir que cada CNS seja único dentro da tabela `tb_prof_historico_cns`. Caso existam registros duplicados, devem ser removidos para que a associação entre o identificador e o profissional seja única e consistente.


## Identidade do Profissional e Fluxo de Acessos

A identidade do profissional não é determinada pelo campo `TB_USUARIO.CO_ACTOR` (campo legado). A resolução de identidade e de papéis ativos segue o fluxo abaixo:

### Cadeia de Identidade
`TB_USUARIO.DS_LOGIN` $\rightarrow$ `TB_USUARIO.CO_SEQ_USUARIO` $\rightarrow$ `TB_PROF.CO_USUARIO` $\rightarrow$ `TB_PROF.CO_SEQ_PROF` $\rightarrow$ `TB_ATOR_PAPEL.CO_PROF`.

### Tipos de Acessos
O sistema distingue dois tipos principais de papéis que aparecem na interface:
1.  **LOTACAO (Acessos de Unidade/CBO):** O CBO e a Unidade de Saúde não vêm do perfil, mas sim da tabela `TB_LOTACAO`. O vínculo ocorre via `TB_LOTACAO.CO_ATOR_PAPEL = TB_ATOR_PAPEL.CO_SEQ_ATOR_PAPEL`.
2.  **PERFIL (Acessos de Permissão):** Define as permissões do profissional via `RL_ATOR_PAPEL_PERFIL`.

### Consulta de Diagnóstico de Papéis Ativos
Para listar exatamente os acessos que o usuário visualiza na interface (Unidade, CBO e Perfil):

```sql
SELECT 
    u.ds_login,
    l.co_unidade_saude,
    c.no_cbo,
    c.co_cbo_2002,
    tap.no_tipo_ator_papel,
    p.no_perfil
FROM tb_usuario u
JOIN tb_prof pr ON u.co_seq_usuario = pr.co_usuario
JOIN tb_ator_papel tap ON pr.co_seq_prof = tap.co_prof
LEFT JOIN tb_lotacao l ON tap.co_seq_ator_papel = l.co_ator_papel
LEFT JOIN rl_ator_papel_perfil rpp ON tap.co_seq_ator_papel = rpp.co_actor_papel
LEFT JOIN tb_perfil p ON rpp.co_perfil = p.co_seq_perfil
LEFT JOIN tb_cbo c ON l.co_cbo = c.co_cbo
WHERE u.ds_login = 'login_do_usuario'
  AND tap.st_ativo = 1;
Nota: Se o papel for do tipo 'LOTACAO', o CBO/Unidade não vêm do perfil, mas sim da tabela TB_LOTACAO.

## Importação de CNES

- Na versão 5.5.22, `ImportarCnes` aceita arquivos `.xml` e `.zip`; o ZIP deve
  conter exatamente um XML.
- As versões de layout aceitas são 2.1, 3.0 e 3.1. O backend lê
  `IDENTIFICACAO.VERSAO_XSD` e valida o documento contra o recurso embarcado
  `cnes/cnes_<versao>.xsd` antes de processá-lo.
- Além do XSD, o importador confirma que o município do XML corresponde ao
  município selecionado e impede importar uma versão de layout inferior à
  versão já registrada para o município.
- A carga desativa previamente unidades, equipes e lotações do município,
  persiste unidades/equipes antes de profissionais/lotações e reativa os
  registros presentes no arquivo.
- As validações de negócio conferem CNPJ, CPF, CNS, município/UF, tipo de
  unidade, complexidade, conselho, CBO, CNES e a combinação CNES/INE.
- Profissional novo importado do CNES recebe um `Usuario` cujo login é o CPF.
  `UsuarioService.create(cpf)` cria esse usuário sem senha e com troca de senha
  obrigatória; a credencial precisa ser provisionada depois.
- Uma lotação importada fica ativa, marcada como importada e com código único
  derivado de profissional, unidade, equipe e CBO.
- A importação usa serviços que também atualizam histórico de CNS, dimensões e
  caches derivados; inserir somente as tabelas principais por SQL não reproduz
  automaticamente esse fluxo.
- O backend 5.5.22 contém o XSD em `cnes/cnes_3.1.xsd`, dentro de
  `backend-5.5.22.jar`. O gerador deve validar contra esse recurso exato e
  registrar seu checksum.
- `UnidadeSaudeCnesValidator` exige nome, CNPJ válido, CNES, tipo/descrição,
  complexidade e endereço; o município da unidade precisa ser o mesmo do
  arquivo/importação.
- `EquipeCnesValidator` exige tipo, sigla, nome, INE e descrição. A data de
  desativação, quando presente, usa `dd/MM/yyyy`.
- `ProfissionalCnesValidator` exige CPF e CNS válidos e preserva a coerência do
  par CPF/CNS com cadastros existentes.
- `LotacaoCnesValidator` resolve CBO no catálogo, unidade por CNES e equipe
  pelo par CNES/INE.
- O XSD 3.1 exige a ordem estrutural unidade
  `ENDERECO -> COMPLEXIDADE -> EQUIPES` e profissional
  `ENDERECO -> LOTACOES`.

## Formato de senha na versão 5.4.38

- `PasswordStorage` grava o formato
  `sha256:64000:32:<saltBase64>:<hashBase64>`.
- A estratégia `sha256` usa PBKDF2-HMAC-SHA-256, salt aleatório de 24 bytes,
  64.000 iterações e saída de 32 bytes.

## Grafo relacional mínimo para dados demo (schema 5.5.22)

Inspeção realizada somente sobre metadados com `db-schema.sh`,
`db-columns.sh` e `db-fks.sh`; nenhum conteúdo de tabela foi consultado.

- `tb_lotacao.co_ator_papel` referencia
  `tb_ator_papel.co_seq_ator_papel` e funciona como identidade compartilhada
  da lotação. `tb_atend_prof.co_lotacao` aponta para essa chave.
- CBO e unidade pertencem à lotação; permissões pertencem ao vínculo
  `rl_ator_papel_perfil -> tb_perfil`. Um acesso assistencial funcional exige
  considerar ambos os ramos.
- A cadeia clínica principal é
  `tb_cidadao -> tb_prontuario -> tb_atend -> tb_atend_prof`.
- Existe ciclo entre `tb_atend.co_atend_prof` e
  `tb_atend_prof.co_atend`. Como o primeiro é anulável, inserção SQL teria de
  criar atendimento, criar atendimento profissional e preencher depois a
  referência reversa.
- `tb_evolucao_subjetivo`, `tb_evolucao_objetivo`,
  `tb_evolucao_avaliacao` e `tb_evolucao_plano` usam `co_atend_prof` como
  chave compartilhada/FK, formando extensões 1:1 de `tb_atend_prof`.
- `tb_problema` pertence ao prontuário e pode apontar para sua última
  `tb_problema_evolucao`; a evolução pode apontar para `tb_atend_prof`.
- `tb_cidadao` tem poucos campos `NOT NULL` no banco. Isso não deve ser tratado
  como contrato mínimo de negócio: criação e exibição ainda dependem das
  validações dos serviços do PEC.
- Em `rl_unidade_saude_complexidade`, a coluna `co_ator_papel` referencia
  `tb_unidade_saude.co_seq_unidade_saude`; o nome da coluna é enganoso e o
  destino deve ser confirmado pela FK.

## Compatibilidade do gerador demo com PEC 5.5.22

> Atualizacao operacional (PEC 5.5.24): unidades basicas devem ser
> identificadas pelo codigo natural
> `tb_tipo_unidade_saude.co_tipo_unidade_cnes = 2`. A descricao canonica
> emitida no CNES 3.1 e `CENTRO DE SAUDE/UNIDADE BASICA`; consultas nao devem
> usar `no_tipo_unidade_saude` como chave, pois bases anteriores podem conter
> variacoes textuais como `UNIDADE BASICA DE SAUDE`.

- O primeiro alvo de execução do gerador demo é o JAR 5.5.22 presente no
  pacote; o codebase local foi regenerado a partir desse JAR.
- O schema foi inspecionado diretamente na instância 5.5.22. A execução deve
  comparar tabelas, colunas, tipos, nulabilidade e FKs críticas com esse
  inventário e abortar se houver divergência.
- O ambiente confirmado usa PostgreSQL 17.10 e instalação `PRONTUARIO`.
- A instância inspecionada está em modo de produção/atendimento e deve
  permanecer somente como referência de leitura. A geração deve ocorrer em
  instalação 5.5.22 nova, isolada e preferencialmente de treinamento.
- No schema 5.5.22, `tb_tipo_atend_prof` possui somente
  `co_tipo_atend_prof` e `no_tipo_atend_prof`. FKs como `co_atend`,
  `co_lotacao` e `st_atend_prof` pertencem a `tb_atend_prof`, não ao catálogo.
- A PK de `tb_subtipo_unidade_saude` é
  `co_seq_subtp_unidade_saude`.
- Para catálogos, não confundir PK interna com código natural: candidatos
  confirmados por coluna incluem `co_tipo_unidade_cnes`, `sg_complexidade`,
  `nu_ms`, `co_cbo_2002` e `no_identificador`.
- O XSD CNES deve ser extraído do próprio JAR alvo. Não reutilizar o XSD
  embarcado no backend anterior apenas porque o layout aparenta ser igual.
- `demo_credentials.txt` é uma saída intencional do laboratório: deve listar
  CPF/login, senha, perfis e lotações de cada profissional sintético. Deve ser
  gerado somente depois do provisionamento e validação dos logins e ficar
  ignorado pelo Git.

## Cidadão e prontuário no codebase 5.5.22

- O cadastro oficial entra pela mutation GraphQL
  `CidadaoMutationResolver.salvarCidadao`, passa por
  `CidadaoInputValidator` e `CidadaoFciService` e persiste uma FCI antes de
  recuperar o cidadão materializado. SQL direto em `tb_cidadao` não reproduz
  esse fluxo.
- Nome, nascimento, sexo, raça/cor e nacionalidade são obrigatórios no
  validador. CPF é obrigatório salvo quando há flag e justificativa válida de
  ausência; CPF e CNS informados são validados e verificados contra duplicação
  pelo serviço de grupo do cidadão.
- `Cidadao` recalcula `no_cidadao_filtro` e `no_mae_filtro` com minúsculas,
  remoção de acentos e `trim` nos setters correspondentes.
- A FCI recebe identificador no formato `<CNES>-<UUID>`, gerado por
  `CidadaoConverter.generateUuidCadastroIndividual`.
- `ProntuarioService.loadOrCreateProntuarioByIdCidadao` cria prontuário sob
  demanda. `ProntuarioCreate` também cria o grupo inicial e
  `ProntuarioGrupoHistorico`.
- A entidade JPA usa `@OneToOne` entre prontuário e cidadão, mas a cardinalidade
  física ainda deve ser confirmada por unique constraint/índice do PostgreSQL.
- A busca de cidadãos filtra `ativoParaExibicao=true` e aceita isoladamente
  nome normalizado, data exata, CPF ou CNS; nome+nascimento não é uma
  combinação mínima obrigatória.

## Identidade, acessos e credenciais no codebase 5.5.22

- A cadeia assistencial vigente é
  `tb_usuario -> tb_prof -> tb_ator_papel -> tb_lotacao`.
  `tb_lotacao.co_ator_papel` é PK compartilhada/FK da herança JPA.
- “Instalador” é um `ADMINISTRADOR_GERAL` em `tb_adm_geral`, não um tipo de
  papel próprio. Administrador municipal usa `tb_adm_municipal`; ambas as
  subtabelas compartilham `co_ator_papel` com `tb_ator_papel`.
- CBO, unidade e equipe pertencem à lotação. Autorização pertence a
  `rl_ator_papel_perfil`, cuja PK lógica é
  `(co_ator_papel, co_perfil)`.
- `LotacaoCnesPersister.persistPerfis` escolhe perfis padrão por CBO 2002 e
  grupo da unidade (UBS, CEO, UBS indígena ou AD) e
  `AddPerfisLotacao` grava somente os vínculos ausentes.
- Usuário criado para o CPF começa sem senha, desbloqueado e com troca
  obrigatória. No código 5.5.22, `st_termo_uso=true` é o estado inicial e
  `UsuarioAceitarTermosUso` muda o campo para `false`.
- Para senha definitiva, `UsuarioService.redefinirSenha` audita, revoga
  tokens, limpa recuperação, zera tentativas, desbloqueia e atualiza senha,
  `st_forcar_troca_senha=false` e `dt_ultima_atualizacao_senha`.
- O hash usa PBKDF2-HMAC-SHA-256, 64.000 iterações, salt aleatório de 24 bytes
  e saída de 32 bytes no formato
  `sha256:64000:32:<saltBase64>:<hashBase64>`.
- O gerador demo deve preferir CNES para lotações/perfis e serviços da
  aplicação para papéis administrativos e senha final. SQL direto não
  reproduz auditoria nem o ciclo de tokens.

## Validação real do CNES demo no PEC 5.5.22

- A seed `5522` passou pelo importador oficial em 2026-07-27: 2 unidades
  novas, 2 equipes novas, 2 profissionais novos, 1 profissional atualizado e
  4 lotações novas.
- O profissional atualizado era o instalador previamente cadastrado com o
  mesmo CPF sintético; o importador preservou sua identidade e criou as duas
  lotações CNES.
- Para preparar a base isolada sem contra-chave do e-Gestor, o município pode
  ser ativado temporariamente com `TREINAMENTO=1`. O fluxo ainda executa
  `AutorizarMunicipioCommand` e cria perfis, agenda e configurações municipais
  padrão.
- Em build local, `TRAINING=true` aplica `TREINAMENTO=1` e `make production`
  declara `TRAINING=false`, aplicando `TREINAMENTO=0`. Com banco externo,
  `TRAINING` permanece ausente e `scripts/install.sh` não faz escrita adicional,
  preservando o comportamento anterior.

## Constraints físicas confirmadas para o demo 5.5.22

- Existe índice único em `tb_prontuario.co_cidadao`, confirmando relação
  cidadão-prontuário 1:0..1. A FK usa `NO ACTION` em update/delete.
- Não foram confirmadas uniques físicas para CPF, CNS ou
  `tb_cidadao.co_unico_cidadao`; a geração precisa garantir unicidade lógica.
- `st_ativo` e `st_ativo_para_exibicao` de cidadão têm default 1;
  `st_unificado` tem default 0.
- `tb_usuario.co_ator -> tb_ator.co_seq_ator` existe como ramo legado.
- `tb_adm_geral.co_ator_papel`, `tb_adm_municipal.co_ator_papel` e
  `tb_lotacao.co_ator_papel` são identidades compartilhadas com
  `tb_ator_papel`. Para lotação, isso foi confirmado pelo schema anterior e
  pelo `@PrimaryKeyJoinColumn` do modelo, apesar de omissão em relatório
  posterior.
- A PK composta de `rl_ator_papel_perfil` impede repetir o mesmo perfil no
  mesmo papel. Não foram confirmadas uniques físicas para login, CPF
  profissional ou `tb_prof.co_usuario`.

## Operações oficiais de cidadão e atendimento no PEC 5.5.22

- O endpoint GraphQL usado pelo cliente web espera
  `Api-Consumer-Id: ESUS_WEB_CLIENT` e metadados Apollo compatíveis. Uma
  requisição HTTP válida sem esse contexto pode ser recusada antes do
  resolver.
- A criação de um encontro individual segue
  `SalvarAtendimento -> Atender -> SalvarAtendimentoIndividual`. O primeiro
  cria a entrada da lista, o segundo abre a participação profissional e o
  terceiro persiste SOAP e finaliza.
- Busca de cidadão e catálogos assistenciais depende de acesso operacional
  selecionado. Um login multiperfil deve selecionar a lotação antes dessas
  operações e trocar novamente ao alternar CBO/unidade.
- Procedimentos automáticos não devem ser fixados por ID interno. No cenário
  5.5.22 validado, os códigos naturais foram `0301010064` para médico de
  família e `0301010030` para enfermeiro; o ID deve ser resolvido no contexto
  da lotação ativa.
- Um payload mínimo finalizado e visível usa atendimento
  `CONSULTA_NO_DIA`, conduta
  `RETORNO_PARA_CUIDADO_CONTINUADO_PROGRAMADO`, participação presencial e
  desfecho que remove o cidadão da lista.
- O histórico longitudinal pode exigir uma justificativa de auditoria antes
  de exibir detalhes. A validação por interface deve cobrir esse passo e
  confirmar S/O/A/P, CIAP, procedimento, conduta, CNES e INE.
- Para geração repetível, cidadãos podem ser resolvidos pelo CPF sintético;
  atendimentos precisam de uma chave externa de idempotência. O gerador demo
  usa manifesto atômico por cenário e papel, pois a API de finalização não
  expõe uma chave idempotente do cliente.

## Round trip de backup demo no ambiente Docker

- O caminho `make restore JAR=<jar-5.5.22> BACKUP=<backup-custom>` foi validado
  com um volume PostgreSQL novo. O script cria o banco, usa `pg_restore -1
  --no-owner --no-acl`, executa a migração do instalador e aplica
  `TREINAMENTO=0`.
- Um backup custom criado pelo PostgreSQL 17.10 preservou o grafo sintético:
  após restauração, a API localizou os dez cidadãos sem recriação e validou os
  vinte atendimentos finalizados controlados pelo manifesto.
- Para provar isolamento, execute `docker compose down -v` somente no Compose
  sintético e confirme que o volume esperado deixou de existir antes da
  restauração. O backup canônico deve estar fora desse volume.
- Em Apple Silicon, o PEC `linux/amd64` inicia sob QEMU e pode permanecer
  vários minutos a 99% de CPU depois do instalador. Reset de conexão nesse
  intervalo não é suficiente para declarar falha; aguarde processo ativo,
  migração concluída e HTTP 200.

## Fábrica automatizada do backup demo 5.5.22

- O importador oficial expõe `POST /api/cnes/{municipioId}` como multipart,
  com o arquivo no campo `file`; a chamada autenticada requer cookie
  `JSESSIONID`, cookie XSRF e o header XSRF correspondente.
- A importação é assíncrona. O estado e as contagens devem ser acompanhados
  pela query GraphQL `importacoesCnes`, incluindo `processo.status`, e não
  inferidos apenas pela resposta HTTP do upload.
- Reimportar o CNES pode voltar a marcar troca obrigatória de senha do
  profissional. A fábrica atualiza a base em treinamento, onde o administrador
  municipal pode normalizar as credenciais, e somente depois recria o PEC em
  produção antes do dump.
- `scripts/demo/build-demo-backup.sh` cria projeto Compose, volume, rede e
  runtime exclusivos, restaura o pack-base, atualiza por APIs oficiais,
  exporta em formato custom e restaura o próprio candidato antes de publicar.
- A validação final é somente leitura e exige três credenciais, quatro
  lotações, dez cidadãos e vinte atendimentos finalizados com cidadão e os
  quatro textos SOAP esperados.
- O bootstrap canônico fica em `scripts/demo/pack/base.backup` (pasta única,
  sem versão no caminho — trocar de versão do PEC substitui o conteúdo em vez
  de acumular uma pasta por release), com checksum e `pec_version` em
  `pack.json` e armazenamento Git LFS. O script recusa publicar dentro da
  pasta do pack e usa nomes temporários por execução.

## Microárea no cadastro territorial

`VinculacaoCidadaoTerritorioInput` aceita a propriedade GraphQL `microarea`
(além de `cnes`, `ine`, `cns`, `cbo2002` e `foraDeArea`).
`CidadaoConverter` encaminha esse valor à FCI como `microArea`, de modo que a
atribuição territorial deve usar a mutation `salvarCidadao`, e não uma escrita
direta em `tb_cidadao` ou tabelas de fatos. A listagem do MCP deriva as
microáreas ativas de `tb_fat_cad_individual.nu_micro_area` por equipe.
