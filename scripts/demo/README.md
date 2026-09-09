# PEC demo data factory

Fábrica de instalações e-SUS PEC prontas para demonstração e testes, usando
somente dados sintéticos.

O objetivo não é fabricar um banco do zero. O banco do PEC contém schema,
catálogos, migrações e dados de referência dependentes da versão. A estratégia
segura é partir de uma instalação limpa criada pelo instalador oficial da mesma
versão do PEC, importar um CNES sintético pelo próprio sistema, criar os
cenários clínicos e só então exportar um backup completo.

## Versão atual

O pack-base (`scripts/demo/pack/`) está travado no **PEC 5.5.24**. É a única
versão suportada em um dado momento: cada pack embute justamente o
`base.backup` compatível com o schema, os catálogos e as migrações dessa
versão. `scripts/demo/pack/pack.json` é a fonte da verdade — todo o resto
(script, CLI, testes) lê a versão de lá em vez de fixá-la em vários lugares.

Para atualizar de versão, veja "Atualizando o pack para uma nova versão do
PEC" mais abaixo.

## Um comando, sem LLM e sem interface

Pré-requisitos: Docker com `docker compose`, `uv`, Python 3, `curl`, Git LFS e
o JAR `eSUS-AB-PEC-<versão-do-pack>-Linux64.jar` (ver "Versão atual") na raiz
de `esus-pec`. Depois de clonar, materialize o pack-base uma vez com
`git lfs pull`.

Na raiz de `esus-pec`, execute:

```bash
sh scripts/demo/build-demo-backup.sh
```

O backup validado será publicado em:

```text
scripts/demo/output/pec-demo-<versão-do-pack>.backup
```

Para escolher outro nome ou evitar conflito de porta:

```bash
sh scripts/demo/build-demo-backup.sh \
  --output /caminho/pec-demo-teste.backup \
  --port 18083
```

O script não altera o Compose normal nem o pack-base. Ele cria projeto, rede,
volume e diretório temporário exclusivos; restaura o pack-base; inicia o PEC em
treinamento; gera e importa o CNES por API; garante credenciais, cidadãos e
atendimentos por GraphQL; recria o PEC em produção; exporta um archive custom;
restaura esse próprio archive em banco limpo e executa validação somente
leitura. Só após todo o round trip os arquivos finais são movidos para o
destino.

Além do `.backup`, são publicados com o mesmo prefixo:

- `.validation.json`, com versão, SHA-256, tamanho e checks executados;
- `.credentials.txt`, com os logins exclusivamente sintéticos;
- `.clinical-manifest.json`, com as chaves dos 60 atendimentos;
- `.patients.csv`, índice sem documentos com uma linha de história clínica
  por paciente para orientar os testes manuais;
- `.cnes.zip`, com o CNES 3.1 sintético usado.

O arquivo `pack/base.backup` é o bootstrap canônico, versionado por Git LFS e
protegido contra sobrescrita pelo script. Ele não é o resultado de cada
execução: serve como ponto de partida durável e verificável pelo checksum de
`pack/pack.json`. Existe um único pack ativo por vez (ver "Versão atual"), não
uma pasta por versão — trocar de versão do PEC substitui o conteúdo de
`pack/` em vez de acumular um `base.backup` por release.

## Resultado esperado

O alvo de execução é a versão travada em `pack/pack.json` (ver "Versão
atual"). O schema foi inspecionado diretamente nessa versão e o codebase
local também foi regenerado a partir do JAR correspondente.

A fábrica produz, para a versão ativa do pack:

- `cnes-demo.xml` e `cnes-demo.zip`;
- um manifesto sem segredos com a seed e os identificadores sintéticos;
- um relatório de validação;
- um backup custom do PostgreSQL para restauração pelo `make restore`;
- opcionalmente um dump SQL legível, também preso à versão;
- `demo_credentials.txt`, com CPF/login, email sintético, senha, perfis e
  lotações de cada profissional sintético.

## Estado atual

O fluxo executável para a versão ativa do pack já:

- gera e valida o CNES 3.1 sintético;
- provisiona e valida as credenciais dos profissionais;
- cria dez cidadãos por mutations oficiais do PEC;
- cria 60 atendimentos SOAP finalizados, variando de 2 a 10 por cidadão;
- alterna medições completas, parciais e ausentes e inclui prescrições
  estruturadas, inclusive medicamentos de uso contínuo nas crônicas;
- alterna entre duas UBS, duas equipes e os CBOs `225130` e `223505`;
- distribui os dez cidadãos entre as duas equipes e as microáreas `01`, `02`
  e `03`, usando a mutation oficial de cadastro territorial;
- publica um manifesto clínico para tornar a geração repetível;
- produz um backup completo restaurável pelo `make restore`.

O CNES é importado automaticamente pelo endpoint oficial do PEC. As demais
etapas usam as mesmas operações GraphQL consumidas pelo cliente web da versão
ativa do pack, sem SQL clínico direto.
`demo_credentials.txt` é uma saída local de laboratório, publicada somente
depois da validação dos logins e ignorada pelo Git.

Execute tudo apenas em instalação isolada. CPF, CNS, CNES e INE são
sintéticos, mas sequências algoritmicamente válidas não constituem uma faixa
oficialmente reservada.

## Leitura sugerida

1. [`docs/01-escopo-e-seguranca.md`](docs/01-escopo-e-seguranca.md)
2. [`docs/02-contrato-cnes.md`](docs/02-contrato-cnes.md)
3. [`docs/03-arquitetura-proposta.md`](docs/03-arquitetura-proposta.md)
4. [`docs/04-status-da-investigacao.md`](docs/04-status-da-investigacao.md)
5. [`docs/05-inventario-schema-5.5.22.md`](docs/05-inventario-schema-5.5.22.md)
6. [`docs/06-revisao-prompt-01-5.5.22.md`](docs/06-revisao-prompt-01-5.5.22.md)
7. [`docs/07-revisao-prompts-01b-02-03.md`](docs/07-revisao-prompts-01b-02-03.md)
8. [`docs/08-contrato-cidadao-prontuario-codebase-5.5.22.md`](docs/08-contrato-cidadao-prontuario-codebase-5.5.22.md)
9. [`docs/09-identidade-acessos-credenciais-codebase-5.5.22.md`](docs/09-identidade-acessos-credenciais-codebase-5.5.22.md)
10. [`docs/10-fechamento-prompts-02b-03b-schema-5.5.22.md`](docs/10-fechamento-prompts-02b-03b-schema-5.5.22.md)
11. [`docs/11-codigos-naturais-operacionais-5.5.22.md`](docs/11-codigos-naturais-operacionais-5.5.22.md)
12. [`docs/12-fluxo-atendimento-soap-codebase-5.5.22.md`](docs/12-fluxo-atendimento-soap-codebase-5.5.22.md)
13. [`docs/13-backup-restauracao-e-integridade-local-5.5.22.md`](docs/13-backup-restauracao-e-integridade-local-5.5.22.md)
14. [`docs/14-scaffold-e-gerador-cnes-3.1.md`](docs/14-scaffold-e-gerador-cnes-3.1.md)
15. [`docs/15-provisionamento-cidadaos-e-soap-5.5.22.md`](docs/15-provisionamento-cidadaos-e-soap-5.5.22.md)
16. [`docs/16-fabrica-backup-um-comando.md`](docs/16-fabrica-backup-um-comando.md)
17. [`prompts/README.md`](prompts/README.md)

## Gerar o CNES sintético

```bash
cd scripts/demo
uv sync --extra dev

uv run pec-demo generate-cnes \
  --output-dir output \
  --backend-jar ../../codebase/app-extracted/BOOT-INF/lib/backend-<versão>.jar \
  --municipality-ibge 2927408 \
  --uf BA \
  --cep 40000000 \
  --seed 5522 \
  --generated-on 2026-07-27
```

O comando valida o dataset com a réplica Python das regras do importador e
depois com o XSD embarcado no JAR informado.

```bash
uv run pytest
```

## Comandos internos para desenvolvimento

O fluxo abaixo é útil para depuração de uma etapa específica. Para produzir o
backup reproduzível, use `build-demo-backup.sh`.

### Provisionar uma instalação limpa

Depois de importar `output/cnes-demo.zip` e concluir a ativação municipal,
gere as credenciais no mesmo processo que valida os logins:

```bash
uv run pec-demo provision-credentials \
  --base-url http://127.0.0.1:8082 \
  --admin-login '<CPF_ADMIN_DEMO>' \
  --admin-password '<SENHA_ADMIN_DEMO>' \
  --credentials-file demo_credentials.txt \
  --municipality-ibge 2927408 \
  --uf BA \
  --cep 40000000 \
  --seed 5522 \
  --generated-on 2026-07-27
```

Use uma credencial assistencial validada para criar a coorte:

```bash
uv run pec-demo provision-patients \
  --base-url http://127.0.0.1:8082 \
  --login '<CPF_PROFISSIONAL_DEMO>' \
  --password '<SENHA_DEMO>' \
  --municipality-ibge 2927408 \
  --municipality-name SALVADOR \
  --cnes '<CNES_UBS_MEDICA>' \
  --ine '<INE_EQUIPE_MEDICA>' \
  --seed 5522 \
  --generated-on 2026-07-27
```

Por fim, gere os históricos longitudinais por cidadão:

```bash
uv run pec-demo provision-histories \
  --base-url http://127.0.0.1:8082 \
  --login '<CPF_PROFISSIONAL_DEMO>' \
  --password '<SENHA_DEMO>' \
  --doctor-cnes '<CNES_UBS_MEDICA>' \
  --nurse-cnes '<CNES_UBS_ENFERMAGEM>' \
  --manifest-file output/clinical_manifest.json \
  --seed 5522 \
  --generated-on 2026-07-27
```

Os comandos de cidadãos e históricos são idempotentes: cidadãos são
resolvidos por CPF e os atendimentos concluídos são registrados no manifesto
atômico.

## Inspeção segura do arquivo CNES

O comando abaixo mostra somente estrutura, contagens, formatos e integridade
referencial. Ele nunca imprime valores dos atributos:

```bash
python3 scripts/demo/tools/inspect_cnes.py \
  /caminho/para/XmlParaESUS.zip \
  --xsd /caminho/para/cnes_3.1.xsd
```

O XSD da versão 3.1 está embarcado no `backend-<versao>.jar`, no caminho
`cnes/cnes_3.1.xsd`. O gerador o descobre pelo JAR da versão-alvo e não mantém
uma cópia divergente no repositório.

## Atualizando o pack para uma nova versão do PEC

O pack-base não é versionado por pasta (não existe `pack/5.5.x/`): há sempre
um único `scripts/demo/pack/`, e a atualização de versão *substitui* seu
conteúdo em vez de somar mais um `base.backup` ao Git LFS.

Na raiz de `esus-pec`:

```bash
make upgrade-demo
```

Isso, sozinho:

1. descobre a última versão publicada do PEC e baixa o JAR Linux para a raiz
   do repositório, com `scripts/resolve-pec-jar.sh` (o mesmo mecanismo que
   `scripts/build.sh` usa quando chamado sem `-f`) — pula o download se o
   arquivo já existir. Para travar numa versão específica em vez da última:
   `make upgrade-demo JAR=/caminho/eSUS-AB-PEC-<versão>-Linux64.jar` (aceita
   também uma URL);
2. gera o novo `base.backup` reaproveitando o `pack/base.backup` atual como
   semente — o próprio PEC migra o schema em runtime ao subir uma versão
   nova sobre um banco de uma versão anterior, o mesmo mecanismo usado por
   `make update-local`/`update.sh` em uma instalação real, então não é
   preciso partir de uma instalação vazia. Roda o round trip completo de
   [`docs/16-fabrica-backup-um-comando.md`](docs/16-fabrica-backup-um-comando.md)
   (CNES, credenciais, cidadãos, atendimentos, exportação, restauração e
   validação);
3. promove o resultado validado a novo pack-base canônico: substitui
   `pack/base.backup`, `pack/clinical_manifest.json` e `pack/pack.json`
   (recalculando os checksums e mantendo seed, município, UF e CEP do pack
   anterior) e atualiza `DEFAULT_PEC_VERSION` em
   [`src/pec_demo/version.py`](src/pec_demo/version.py) — o único lugar do
   código-fonte que fixa a versão como literal; CLI, cliente GraphQL e
   testes leem dessa constante ou do `pack.json` em runtime.

O `base.backup` anterior sai do working tree, mas continua recuperável pelo
histórico do Git/LFS se for preciso comparar versões. Depois de rodar:

- regenere `codebase/` a partir do mesmo JAR, se ainda não feito:
  `make codebase JAR=eSUS-AB-PEC-<nova-versão>-Linux64.jar` (sem `JAR=`,
  também baixa sozinho a última versão publicada);
- atualize a seção "Versão atual" no topo deste README;
- rode `uv run pytest` antes de comitar.

Nenhum outro arquivo do código-fonte precisa ser tocado só por causa do
número de versão.

`make upgrade-demo` é açúcar sintático para dois comandos que continuam
disponíveis separadamente (úteis para depurar uma etapa isolada ou montar o
pack manualmente, por exemplo quando um instalador não suporta migrar um
banco existente):

```bash
sh scripts/demo/build-demo-backup.sh \
  --upgrade-jar eSUS-AB-PEC-<nova-versão>-Linux64.jar \
  --upgrade-pec-version <nova-versão>

sh scripts/demo/promote-pack.sh \
  --backup scripts/demo/output/pec-demo-<nova-versão>.backup \
  --jar eSUS-AB-PEC-<nova-versão>-Linux64.jar \
  --pec-version <nova-versão>
```
