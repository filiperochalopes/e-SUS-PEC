SHELL := /bin/sh
.DEFAULT_GOAL := help

BUILD_SCRIPT := scripts/build.sh
UPDATE_SCRIPT := scripts/update.sh
CODEBASE_SCRIPT := scripts/gen-codebase.sh
RESOLVE_JAR_SCRIPT := scripts/resolve-pec-jar.sh
DEMO_BUILD_SCRIPT := scripts/demo/build-demo-backup.sh
DEMO_PROMOTE_SCRIPT := scripts/demo/promote-pack.sh
BUILD_ARGS ?=
DEMO_ARGS ?=
JAR ?=
BACKUP ?=
OUTPUT ?= codebase

jar_arg = $(if $(strip $(JAR)),-f "$(JAR)")

.PHONY: help training production external cloud restore update-local update-external codebase upgrade-demo check-env check-cloud-env

help:
	@printf '%s\n' \
		'Uso: make <alvo> [VAR=valor]' \
		'' \
		'Instalação:' \
		'  training       Instala com banco local em modo de treinamento' \
		'  production     Instala com banco local em modo de produção' \
		'  external       Instala em produção usando o banco externo do .env' \
		'  cloud          Instala em produção usando cloud/.env' \
		'  restore        Restaura BACKUP no modo cloud e inicia o PEC' \
		'' \
		'Manutenção:' \
		'  update-local    Atualiza a instalação com banco local' \
		'  update-external Atualiza a instalação com banco externo' \
		'  codebase       Gera o codebase de JAR em OUTPUT (padrão: codebase);' \
		'                 sem JAR=, baixa sozinho a última versão publicada' \
		'  upgrade-demo   Atualiza scripts/demo/pack/ para a última versão' \
		'                 publicada do PEC (ou JAR=) em um só comando' \
		'' \
		'Variáveis:' \
		'  JAR=<arquivo-ou-url>  Usa uma versão específica do PEC' \
		'  BACKUP=<arquivo>      Backup usado pelo alvo restore' \
		'  OUTPUT=<diretório>    Saída usada pelo alvo codebase' \
		'  BUILD_ARGS="..."      Opções adicionais para scripts/build.sh' \
		'  DEMO_ARGS="..."       Opções adicionais para o alvo upgrade-demo'

check-env:
	@test -f .env || { echo 'Erro: copie .env.example para .env e revise a configuração.' >&2; exit 1; }

check-cloud-env:
	@test -f cloud/.env || { echo 'Erro: copie cloud/.env.example para cloud/.env e revise a configuração.' >&2; exit 1; }

training: check-env
	@sh $(BUILD_SCRIPT) $(jar_arg) $(BUILD_ARGS)

production: check-env
	@sh $(BUILD_SCRIPT) -p $(jar_arg) $(BUILD_ARGS)

external: check-env
	@sh $(BUILD_SCRIPT) -e $(jar_arg) $(BUILD_ARGS)

cloud: check-cloud-env
	@sh $(BUILD_SCRIPT) -C -p $(jar_arg) $(BUILD_ARGS)

restore: check-cloud-env
	@test -n "$(BACKUP)" || { echo 'Erro: informe BACKUP=/caminho/arquivo.backup.' >&2; exit 1; }
	@sh $(BUILD_SCRIPT) -C -p $(jar_arg) -r "$(BACKUP)" $(BUILD_ARGS)

update-local: check-env
	@sh $(UPDATE_SCRIPT) compose.local-db.yml

update-external: check-env
	@sh $(UPDATE_SCRIPT) compose.external-db.yml

codebase:
	@resolved=$$(sh $(RESOLVE_JAR_SCRIPT) "$(JAR)") || exit 1; \
	jar_path=$${resolved%% *}; \
	bash $(CODEBASE_SCRIPT) "$$jar_path" "$(OUTPUT)"

upgrade-demo:
	@resolved=$$(sh $(RESOLVE_JAR_SCRIPT) "$(JAR)") || exit 1; \
	jar_path=$${resolved%% *}; \
	version=$${resolved#* }; \
	jar_filename=$$(basename "$$jar_path"); \
	echo "Atualizando scripts/demo/pack/ para o PEC $$version ($$jar_filename)..."; \
	sh $(DEMO_BUILD_SCRIPT) \
		--upgrade-jar "$$jar_filename" \
		--upgrade-pec-version "$$version" $(DEMO_ARGS) && \
	sh $(DEMO_PROMOTE_SCRIPT) \
		--backup "scripts/demo/output/pec-demo-$$version.backup" \
		--jar "$$jar_filename" \
		--pec-version "$$version"
