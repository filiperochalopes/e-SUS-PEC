#!/bin/sh
set -eu

usage() {
    cat <<'EOF'
Uso:
  sh scripts/demo/build-demo-backup.sh [opções]

Cria um backup demo do PEC (versão lida de scripts/demo/pack/pack.json) sem
UI e sem credenciais externas.

Opções:
  --output ARQUIVO   Backup final (padrão: scripts/demo/output/pec-demo-<versão>.backup)
  --port PORTA       Porta HTTP local isolada (padrão: 18082)
  --pause-for-report-processing
                     Pausa no passo 7 para que o processamento oficial de
                     relatórios seja executado na tela de administração, e
                     aguarda a conclusão antes de exportar. Sem esta opção o
                     backup é publicado com selo parcial.
  --reference-date D Data clínica de referência YYYY-MM-DD (padrão: hoje em
                     America/Bahia). Define a cronologia da coorte estendida
                     e é registrada nos artefatos.
  --keep-runtime     Preserva o diretório temporário para diagnóstico
  --keep-environment Não derruba o Docker ao terminar (implica --keep-runtime).
                     O PEC e o banco continuam de pé para diagnóstico, e o
                     comando para removê-los é impresso no final.
  --upgrade-jar NOME       Gera um novo pack-base: usa o pack/base.backup
                           atual como semente, mas sobe o PEC a partir deste
                           JAR (arquivo em REPO_ROOT/NOME) em vez do JAR
                           travado em pack.json. O próprio PEC migra o schema
                           ao iniciar. Use junto com --upgrade-pec-version.
  --upgrade-pec-version V  Versão do PEC servida pelo --upgrade-jar. Some ao
                           --pec-version enviado à CLI e ao nome do output.
  --help             Mostra esta ajuda

Exemplos:
  # Usa o destino padrão dentro de scripts/demo/output:
  sh scripts/demo/build-demo-backup.sh

  # Publica o backup e os arquivos auxiliares em Downloads:
  sh scripts/demo/build-demo-backup.sh \
    --output "$HOME/Downloads/pec-demo.backup"

  # Escolhe também outra porta HTTP para o ambiente isolado:
  sh scripts/demo/build-demo-backup.sh \
    --output "$HOME/Downloads/pec-demo.backup" \
    --port 18083

Para um --output /caminho/NOME.backup, o script também publica:
  /caminho/NOME.validation.json
  /caminho/NOME.credentials.txt
  /caminho/NOME.clinical-manifest.json
  /caminho/NOME.patients.csv
  /caminho/NOME.cnes.zip
  /caminho/NOME.coverage-contract.json
  /caminho/NOME.chronology.json
  /caminho/NOME.preservation.json

O script:
  1. valida o pack base e o JAR por SHA-256;
  2. cria projeto, rede e volume Docker exclusivos;
  3. restaura o pack base e inicia o PEC em treinamento;
  4. gera/importa o CNES via API e atualiza credenciais, cidadãos e SOAPs;
  5. recria o PEC em produção;
  6. exporta um archive PostgreSQL custom;
  7. restaura o próprio archive e executa validação estrita;
  8. publica backup, manifesto, credenciais e relatório atomicamente.
EOF
}

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
PACK_DIR="$SCRIPT_DIR/pack"
PACK_METADATA="$PACK_DIR/pack.json"
COMPOSE_FILE="$SCRIPT_DIR/compose.factory.yml"
OUTPUT=
APP_PORT=18082
KEEP_RUNTIME=false
KEEP_ENVIRONMENT=false
UPGRADE_JAR_FILENAME=
UPGRADE_PEC_VERSION=
REFERENCE_DATE=
PAUSE_FOR_PROCESSING=false

while [ "$#" -gt 0 ]; do
    case "$1" in
        --output)
            [ "$#" -ge 2 ] || { echo "Falta valor para --output" >&2; exit 2; }
            OUTPUT=$2
            shift 2
            ;;
        --port)
            [ "$#" -ge 2 ] || { echo "Falta valor para --port" >&2; exit 2; }
            APP_PORT=$2
            shift 2
            ;;
        --keep-runtime)
            KEEP_RUNTIME=true
            shift
            ;;
        --keep-environment)
            KEEP_ENVIRONMENT=true
            KEEP_RUNTIME=true
            shift
            ;;
        --reference-date)
            [ "$#" -ge 2 ] || { echo "Falta valor para --reference-date" >&2; exit 2; }
            REFERENCE_DATE=$2
            shift 2
            ;;
        --pause-for-report-processing)
            PAUSE_FOR_PROCESSING=true
            shift
            ;;
        --upgrade-jar)
            [ "$#" -ge 2 ] || { echo "Falta valor para --upgrade-jar" >&2; exit 2; }
            UPGRADE_JAR_FILENAME=$2
            shift 2
            ;;
        --upgrade-pec-version)
            [ "$#" -ge 2 ] || { echo "Falta valor para --upgrade-pec-version" >&2; exit 2; }
            UPGRADE_PEC_VERSION=$2
            shift 2
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            echo "Opção desconhecida: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

case "$APP_PORT" in
    *[!0-9]*|'') echo "Porta inválida: $APP_PORT" >&2; exit 2 ;;
esac

# The clinical reference date is captured once per run so every artifact and
# every generated date agree, even if the build crosses midnight.
[ -n "$REFERENCE_DATE" ] || REFERENCE_DATE=$(TZ=America/Bahia date '+%Y-%m-%d')
python3 -c 'import sys
from datetime import date
try:
    date.fromisoformat(sys.argv[1])
except ValueError:
    sys.exit("Data de referência inválida: " + sys.argv[1])
' "$REFERENCE_DATE" || exit 2

if [ -n "$UPGRADE_JAR_FILENAME" ] || [ -n "$UPGRADE_PEC_VERSION" ]; then
    [ -n "$UPGRADE_JAR_FILENAME" ] && [ -n "$UPGRADE_PEC_VERSION" ] || {
        echo "--upgrade-jar e --upgrade-pec-version devem ser usados juntos" >&2
        exit 2
    }
fi

for command_name in docker curl uv python3 shasum; do
    command -v "$command_name" >/dev/null 2>&1 || {
        echo "Dependência ausente: $command_name" >&2
        exit 1
    }
done
docker compose version >/dev/null

metadata_value() {
    python3 -c '
import json
import sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
for part in sys.argv[2].split("."):
    value = value[part]
print(value)
' "$PACK_METADATA" "$1"
}

sha256_file() {
    shasum -a 256 "$1" | awk '{print $1}'
}

assert_checksum() {
    actual=$(sha256_file "$1")
    expected=$2
    if [ "$actual" != "$expected" ]; then
        echo "Checksum divergente: $1" >&2
        echo "esperado=$expected" >&2
        echo "obtido=$actual" >&2
        exit 1
    fi
}

[ -f "$PACK_METADATA" ] || {
    echo "Metadados do pack não encontrados: $PACK_METADATA" >&2
    exit 1
}
PEC_VERSION=$(metadata_value pec_version)
SEED=$(metadata_value seed)
GENERATED_ON=$(metadata_value generated_on)
MUNICIPALITY_IBGE=$(metadata_value municipality_ibge)
MUNICIPALITY_NAME=$(metadata_value municipality_name)
UF=$(metadata_value uf)
CEP=$(metadata_value cep)
BASE_BACKUP="$PACK_DIR/$(metadata_value base_backup.filename)"
CLINICAL_MANIFEST="$PACK_DIR/$(metadata_value clinical_manifest.filename)"
JAR_FILENAME=$(metadata_value jar.filename)
UPGRADING=false
if [ -n "$UPGRADE_JAR_FILENAME" ]; then
    UPGRADING=true
    JAR_FILENAME="$UPGRADE_JAR_FILENAME"
    PEC_VERSION="$UPGRADE_PEC_VERSION"
    echo "Modo de atualização de versão: pack/base.backup (PEC $(metadata_value pec_version)) será restaurado e migrado em runtime para o PEC $PEC_VERSION via $JAR_FILENAME." >&2
fi
JAR_PATH="$REPO_ROOT/$JAR_FILENAME"
[ -n "$OUTPUT" ] || OUTPUT="$SCRIPT_DIR/output/pec-demo-$PEC_VERSION.backup"

for required_file in "$BASE_BACKUP" "$CLINICAL_MANIFEST" "$JAR_PATH"; do
    [ -f "$required_file" ] || {
        echo "Arquivo obrigatório ausente: $required_file" >&2
        echo "Se for o pack base, execute git lfs pull." >&2
        exit 1
    }
done
[ "$(wc -c < "$BASE_BACKUP")" -gt 1000000 ] || {
    echo "Pack base parece ser apenas um ponteiro Git LFS; execute git lfs pull." >&2
    exit 1
}
assert_checksum "$BASE_BACKUP" "$(metadata_value base_backup.sha256)"
assert_checksum "$CLINICAL_MANIFEST" "$(metadata_value clinical_manifest.sha256)"
if [ "$UPGRADING" = false ]; then
    assert_checksum "$JAR_PATH" "$(metadata_value jar.sha256)"
fi

OUTPUT=$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())' "$OUTPUT")
PACK_DIR_RESOLVED=$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())' "$PACK_DIR")
case "$OUTPUT" in
    "$PACK_DIR_RESOLVED"|"$PACK_DIR_RESOLVED"/*)
        echo "Recusando publicar dentro do pack-base versionado: $OUTPUT" >&2
        exit 2
        ;;
    *.backup) ;;
    *)
        echo "O arquivo de saída deve terminar em .backup: $OUTPUT" >&2
        exit 2
        ;;
esac

RUNTIME=$(mktemp -d "$SCRIPT_DIR/.factory-runtime.XXXXXX")
PROJECT_NAME="pec-demo-factory-$$"
PLACEHOLDER_BACKUP="$REPO_ROOT/pec-demo-factory-input.backup"
DEMO_BACKUP_DIR="$RUNTIME/backups"
DEMO_OPT_DIR="$RUNTIME/opt"
DEMO_APP_PORT="$APP_PORT"
DEMO_JAR_FILENAME="$JAR_FILENAME"
DEMO_POSTGRES_DB=esus
DEMO_POSTGRES_USER=postgres
DEMO_POSTGRES_PASS=pass
DEMO_TRAINING=true
DEMO_TZ=America/Bahia
export DEMO_BACKUP_DIR DEMO_OPT_DIR DEMO_APP_PORT DEMO_JAR_FILENAME
export DEMO_POSTGRES_DB DEMO_POSTGRES_USER DEMO_POSTGRES_PASS DEMO_TRAINING
export DEMO_TZ

OUTPUT_DIR=$(dirname "$OUTPUT")
OUTPUT_NAME=$(basename "$OUTPUT" .backup)
VALIDATION="$OUTPUT_DIR/$OUTPUT_NAME.validation.json"
CREDENTIALS="$OUTPUT_DIR/$OUTPUT_NAME.credentials.txt"
MANIFEST="$OUTPUT_DIR/$OUTPUT_NAME.clinical-manifest.json"
PATIENT_INDEX="$OUTPUT_DIR/$OUTPUT_NAME.patients.csv"
CNES_ARCHIVE="$OUTPUT_DIR/$OUTPUT_NAME.cnes.zip"
COVERAGE_CONTRACT="$OUTPUT_DIR/$OUTPUT_NAME.coverage-contract.json"
CHRONOLOGY_REPORT="$OUTPUT_DIR/$OUTPUT_NAME.chronology.json"
PRESERVATION_REPORT="$OUTPUT_DIR/$OUTPUT_NAME.preservation.json"
OUTPUT_TEMP="$OUTPUT.$PROJECT_NAME.tmp"
VALIDATION_TEMP="$VALIDATION.$PROJECT_NAME.tmp"
CREDENTIALS_TEMP="$CREDENTIALS.$PROJECT_NAME.tmp"
MANIFEST_TEMP="$MANIFEST.$PROJECT_NAME.tmp"
PATIENT_INDEX_TEMP="$PATIENT_INDEX.$PROJECT_NAME.tmp"
CNES_ARCHIVE_TEMP="$CNES_ARCHIVE.$PROJECT_NAME.tmp"
COVERAGE_CONTRACT_TEMP="$COVERAGE_CONTRACT.$PROJECT_NAME.tmp"
CHRONOLOGY_REPORT_TEMP="$CHRONOLOGY_REPORT.$PROJECT_NAME.tmp"
PRESERVATION_REPORT_TEMP="$PRESERVATION_REPORT.$PROJECT_NAME.tmp"

mkdir -p "$DEMO_BACKUP_DIR" "$DEMO_OPT_DIR"
cp "$BASE_BACKUP" "$DEMO_BACKUP_DIR/base.backup"
cp "$CLINICAL_MANIFEST" "$RUNTIME/clinical_manifest.json"
[ ! -e "$PLACEHOLDER_BACKUP" ] || {
    echo "Placeholder de build já existe: $PLACEHOLDER_BACKUP" >&2
    exit 1
}
cp "$BASE_BACKUP" "$PLACEHOLDER_BACKUP"

compose() {
    docker compose \
        --project-name "$PROJECT_NAME" \
        -f "$COMPOSE_FILE" \
        "$@"
}

cleanup() {
    set +e
    compose exec -T pec chmod -R a+rwX /opt/e-SUS /backups \
        >/dev/null 2>&1
    if [ "$KEEP_ENVIRONMENT" = true ]; then
        echo
        echo "Ambiente Docker preservado para diagnóstico:"
        echo "  projeto=$PROJECT_NAME"
        echo "  pec=http://127.0.0.1:$APP_PORT"
        echo "  credenciais=$RUNTIME/demo_credentials.txt"
        echo "  remover=docker compose --project-name $PROJECT_NAME -f $COMPOSE_FILE down -v --remove-orphans"
    else
        compose down -v --remove-orphans >/dev/null 2>&1 || true
    fi
    rm -f "$PLACEHOLDER_BACKUP" || true
    rm -f \
        "$OUTPUT_TEMP" \
        "$VALIDATION_TEMP" \
        "$CREDENTIALS_TEMP" \
        "$MANIFEST_TEMP" \
        "$PATIENT_INDEX_TEMP" \
        "$CNES_ARCHIVE_TEMP" \
        "$COVERAGE_CONTRACT_TEMP" \
        "$CHRONOLOGY_REPORT_TEMP" \
        "$PRESERVATION_REPORT_TEMP" || true
    if [ "$KEEP_RUNTIME" = false ]; then
        case "$RUNTIME" in
            "$SCRIPT_DIR"/.factory-runtime.*)
                chmod -R u+w "$RUNTIME" 2>/dev/null || true
                rm -rf "$RUNTIME"
                if [ -e "$RUNTIME" ]; then
                    echo "Não foi possível remover todo o runtime: $RUNTIME" >&2
                fi
                ;;
            *) echo "Recusando remover runtime inesperado: $RUNTIME" >&2 ;;
        esac
    else
        echo "Runtime preservado em: $RUNTIME"
    fi
}

on_exit() {
    status=$?
    trap - EXIT INT TERM HUP
    cleanup
    exit "$status"
}
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

wait_database() {
    attempts=0
    until compose exec -T db \
        pg_isready -U "$DEMO_POSTGRES_USER" -d "$DEMO_POSTGRES_DB" \
        >/dev/null 2>&1; do
        attempts=$((attempts + 1))
        [ "$attempts" -lt 60 ] || {
            echo "PostgreSQL não ficou disponível." >&2
            return 1
        }
        sleep 2
    done
}

wait_pec() {
    attempts=0
    until code=$(curl -sS -o /dev/null -w '%{http_code}' \
        "http://127.0.0.1:$APP_PORT/" 2>/dev/null) &&
        [ "$code" = 200 ]; do
        attempts=$((attempts + 1))
        if [ "$attempts" -ge 300 ]; then
            echo "PEC não respondeu HTTP 200 dentro do limite." >&2
            compose logs --tail=300 pec >&2 || true
            return 1
        fi
        if [ $((attempts % 12)) -eq 0 ]; then
            echo "Aguardando PEC... $((attempts * 5))s"
        fi
        sleep 5
    done
}

recreate_database_from() {
    archive=$1
    compose exec -T db psql \
        -U "$DEMO_POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 \
        -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DEMO_POSTGRES_DB' AND pid <> pg_backend_pid();"
    compose exec -T db dropdb \
        -U "$DEMO_POSTGRES_USER" --if-exists "$DEMO_POSTGRES_DB"
    compose exec -T db createdb \
        -U "$DEMO_POSTGRES_USER" "$DEMO_POSTGRES_DB"
    compose exec -T db pg_restore \
        -U "$DEMO_POSTGRES_USER" -d "$DEMO_POSTGRES_DB" \
        -1 --no-owner --no-acl "$archive"
}

demo_cli() {
    UV_CACHE_DIR="${UV_CACHE_DIR:-$RUNTIME/uv-cache}" \
        uv run --project "$SCRIPT_DIR" pec-demo "$@"
}

psql_db() {
    compose exec -T db psql \
        -U "$DEMO_POSTGRES_USER" -d "$DEMO_POSTGRES_DB" "$@"
}

echo "Data clínica de referência: $REFERENCE_DATE"

echo "[1/12] Gerando e validando o CNES sintético..."
demo_cli generate-cnes \
    --output-dir "$RUNTIME/cnes" \
    --backend-jar "$JAR_PATH" \
    --municipality-ibge "$MUNICIPALITY_IBGE" \
    --uf "$UF" \
    --cep "$CEP" \
    --seed "$SEED" \
    --generated-on "$GENERATED_ON" \
    --pec-version "$PEC_VERSION" \
    --include-acs

echo "[2/12] Construindo ambiente Docker isolado em treinamento..."
compose build pec
compose up -d db
wait_database
recreate_database_from /backups/base.backup
compose up -d pec
wait_pec

echo "[3/12] Assinando a coorte protegida antes de qualquer escrita..."
demo_cli preservation-script \
    --output "$RUNTIME/preservation.sql" \
    --seed "$SEED" \
    --generated-on "$GENERATED_ON"
psql_db -Atq -v ON_ERROR_STOP=1 \
    < "$RUNTIME/preservation.sql" > "$RUNTIME/preservation-before.json"
[ -s "$RUNTIME/preservation-before.json" ] || {
    echo "Assinatura de preservação vazia; o pack base não tem a coorte protegida." >&2
    exit 1
}

echo "[4/12] Importando CNES e atualizando o pack pela API oficial..."
demo_cli refresh-pack \
    --base-url "http://127.0.0.1:$APP_PORT" \
    --cnes-archive "$RUNTIME/cnes/cnes-demo.zip" \
    --credentials-file "$RUNTIME/demo_credentials.txt" \
    --manifest-file "$RUNTIME/clinical_manifest.json" \
    --municipality-ibge "$MUNICIPALITY_IBGE" \
    --municipality-name "$MUNICIPALITY_NAME" \
    --uf "$UF" \
    --cep "$CEP" \
    --seed "$SEED" \
    --generated-on "$GENERATED_ON" \
    --pec-version "$PEC_VERSION" \
    --reference-date "$REFERENCE_DATE"

echo "[5/12] Aplicando a cronologia clínica planejada..."
demo_cli plan-chronology \
    --manifest-file "$RUNTIME/clinical_manifest.json" \
    --output-sql "$RUNTIME/chronology.sql" \
    --output-report "$RUNTIME/chronology.json" \
    --seed "$SEED" \
    --generated-on "$GENERATED_ON" \
    --reference-date "$REFERENCE_DATE"
psql_db -v ON_ERROR_STOP=1 < "$RUNTIME/chronology.sql" >/dev/null
# Re-applying must be a no-op: the adapter shifts by a delta that is now zero.
psql_db -v ON_ERROR_STOP=1 < "$RUNTIME/chronology.sql" >/dev/null

echo "[6/12] Verificando a preservação da coorte protegida..."
psql_db -Atq -v ON_ERROR_STOP=1 \
    < "$RUNTIME/preservation.sql" > "$RUNTIME/preservation-after.json"
demo_cli check-preservation \
    --before "$RUNTIME/preservation-before.json" \
    --after "$RUNTIME/preservation-after.json" \
    --output-report "$RUNTIME/preservation.json"

echo "[7/12] Verificando o processamento oficial de relatórios..."
REPORT_PROCESSING=false
processing_enabled=$(psql_db -Atq -c "
SELECT CASE WHEN coalesce(max(ds_inteiro), 1) = 1 THEN 'true' ELSE 'false' END
FROM tb_config_sistema
WHERE co_config_sistema = 'CONFIGURACAOPROCESSAMENTORELATORIOS';" 2>/dev/null || echo unknown)
individual_facts=$(psql_db -Atq -c "
SELECT count(*) FROM tb_fat_atendimento_individual;" 2>/dev/null || echo 0)
echo "  processamento_habilitado=$processing_enabled"
echo "  fatos_atendimento_individual=$individual_facts"
if [ "$individual_facts" -gt 0 ] 2>/dev/null; then
    REPORT_PROCESSING=true
elif [ "$PAUSE_FOR_PROCESSING" = true ] && [ -r /dev/tty ]; then
    administrator_login=$(sed -n 's/^CPF \/ login: //p' \
        "$RUNTIME/demo_credentials.txt" | head -1)
    cat <<EOF

  O ETL de relatórios precisa ser executado uma vez, pela tela oficial.
  Em 5.5.28 não existe endpoint REST, mutação GraphQL, operação JMX nem
  agendador que o dispare: a ação vive na administração de relatórios.

    1. abra  http://127.0.0.1:$APP_PORT
    2. entre com o login $administrator_login
       (a senha está em $RUNTIME/demo_credentials.txt)
    3. vá em Administração > Processamento de relatórios e clique Processar
    4. volte aqui e pressione ENTER

EOF
    printf '  Pressione ENTER depois de clicar em Processar: '
    read -r _ < /dev/tty
    echo "  Aguardando o processamento concluir..."
    attempts=0
    while [ "$attempts" -lt 240 ]; do
        individual_facts=$(psql_db -Atq -c "
SELECT count(*) FROM tb_fat_atendimento_individual;" 2>/dev/null || echo 0)
        if [ "$individual_facts" -gt 0 ] 2>/dev/null; then
            REPORT_PROCESSING=true
            echo "  Processamento concluído: $individual_facts fatos de atendimento individual."
            break
        fi
        attempts=$((attempts + 1))
        if [ $((attempts % 6)) -eq 0 ]; then
            echo "  ainda processando... $((attempts * 10))s"
        fi
        sleep 10
    done
    [ "$REPORT_PROCESSING" = true ] || {
        echo "  O processamento não produziu fatos dentro do limite de 40 minutos." >&2
    }
fi
if [ "$REPORT_PROCESSING" != true ]; then
    cat >&2 <<'WARN'
  AVISO: o ETL de relatórios não foi executado.
  Em 5.5.28 o único gatilho é a ação "Processar" da tela de administração de
  relatórios, que trafega pelo canal IPP (POST /esus/performerbrowser/ipp).
  Não existe endpoint REST, mutação GraphQL, operação JMX nem agendador.
  O backup será publicado sem o selo de validação completa: os dados
  operacionais e a cronologia estão corretos, mas as tabelas FAT/DIM seguem
  vazias e os relatórios Saúde 360 não retornarão resultados até que o
  processamento seja executado na instalação de destino.
WARN
fi

echo "[8/12] Recriando o PEC em modo produção..."
compose stop pec
DEMO_TRAINING=false
export DEMO_TRAINING
compose build pec
compose up -d --force-recreate pec
wait_pec

echo "[9/12] Exportando o archive PostgreSQL custom..."
compose exec -T db pg_dump \
    -U "$DEMO_POSTGRES_USER" -d "$DEMO_POSTGRES_DB" \
    -Fc --blobs --no-owner --no-acl \
    -f /backups/candidate.backup
compose exec -T db pg_restore -l /backups/candidate.backup >/dev/null

echo "[10/12] Restaurando o próprio candidato..."
compose stop pec
recreate_database_from /backups/candidate.backup
compose start pec
wait_pec

echo "[11/12] Executando validação estrita e somente leitura..."
demo_cli validate-pack \
    --base-url "http://127.0.0.1:$APP_PORT" \
    --manifest-file "$RUNTIME/clinical_manifest.json" \
    --municipality-ibge "$MUNICIPALITY_IBGE" \
    --uf "$UF" \
    --cep "$CEP" \
    --seed "$SEED" \
    --generated-on "$GENERATED_ON" \
    --pec-version "$PEC_VERSION" \
    --reference-date "$REFERENCE_DATE" \
    > "$RUNTIME/validation-counts.txt"
cat "$RUNTIME/validation-counts.txt"

measured() {
    value=$(sed -n "s/^$1=//p" "$RUNTIME/validation-counts.txt" | tail -1)
    case "$value" in
        ''|*[!0-9]*)
            echo "Contagem ausente ou inválida na validação: $1" >&2
            exit 1
            ;;
    esac
    echo "$value"
}
MEASURED_CREDENTIALS=$(measured validated_credentials)
MEASURED_ASSIGNMENTS=$(measured validated_assignments)
MEASURED_PATIENTS=$(measured validated_patients)
MEASURED_HISTORIES=$(measured validated_histories)

echo "[12/12] Publicando artefatos validados..."
mkdir -p "$OUTPUT_DIR"
demo_cli generate-patient-index \
    --output "$RUNTIME/patients.csv" \
    --seed "$SEED" \
    --generated-on "$GENERATED_ON"
demo_cli publish-coverage-contract \
    --output "$RUNTIME/coverage-contract.json" \
    --reference-date "$REFERENCE_DATE"

candidate_sha=$(sha256_file "$DEMO_BACKUP_DIR/candidate.backup")
candidate_size=$(wc -c < "$DEMO_BACKUP_DIR/candidate.backup" | tr -d ' ')
validated_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
python3 - "$RUNTIME/validation.tmp" <<PY
import json
import sys
from pathlib import Path

report_processing = "$REPORT_PROCESSING" == "true"
Path(sys.argv[1]).write_text(json.dumps({
    "schema_version": 2,
    # A step that did not run must show as not run and must withhold the
    # complete-validation seal.
    "status": "validated" if report_processing else
              "validated-without-report-processing",
    "validated_at": "$validated_at",
    "pec_version": "$PEC_VERSION",
    "seed": $SEED,
    "reference_date": "$REFERENCE_DATE",
    "synthetic_only": True,
    "backup": {
        "filename": "$(basename "$OUTPUT")",
        "sha256": "$candidate_sha",
        "size_bytes": $candidate_size,
        "format": "PostgreSQL custom",
    },
    "checks": {
        "cnes_imported_by_api": True,
        "production_mode": True,
        "round_trip_restore": True,
        "chronology_applied": True,
        "chronology_reapplied_without_change": True,
        "protected_cohort_preserved": True,
        "official_report_processing": report_processing,
        "credentials": $MEASURED_CREDENTIALS,
        "assignments": $MEASURED_ASSIGNMENTS,
        "patients": $MEASURED_PATIENTS,
        "histories": $MEASURED_HISTORIES,
    },
    "artifacts": {
        "coverage_contract": "$(basename "$COVERAGE_CONTRACT")",
        "chronology": "$(basename "$CHRONOLOGY_REPORT")",
        "preservation": "$(basename "$PRESERVATION_REPORT")",
    },
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

cp "$DEMO_BACKUP_DIR/candidate.backup" "$OUTPUT_TEMP"
cp "$RUNTIME/validation.tmp" "$VALIDATION_TEMP"
cp "$RUNTIME/demo_credentials.txt" "$CREDENTIALS_TEMP"
cp "$RUNTIME/clinical_manifest.json" "$MANIFEST_TEMP"
cp "$RUNTIME/patients.csv" "$PATIENT_INDEX_TEMP"
cp "$RUNTIME/cnes/cnes-demo.zip" "$CNES_ARCHIVE_TEMP"
cp "$RUNTIME/coverage-contract.json" "$COVERAGE_CONTRACT_TEMP"
cp "$RUNTIME/chronology.json" "$CHRONOLOGY_REPORT_TEMP"
cp "$RUNTIME/preservation.json" "$PRESERVATION_REPORT_TEMP"
chmod 600 "$CREDENTIALS_TEMP"
mv "$OUTPUT_TEMP" "$OUTPUT"
mv "$VALIDATION_TEMP" "$VALIDATION"
mv "$CREDENTIALS_TEMP" "$CREDENTIALS"
mv "$MANIFEST_TEMP" "$MANIFEST"
mv "$PATIENT_INDEX_TEMP" "$PATIENT_INDEX"
mv "$CNES_ARCHIVE_TEMP" "$CNES_ARCHIVE"
mv "$COVERAGE_CONTRACT_TEMP" "$COVERAGE_CONTRACT"
mv "$CHRONOLOGY_REPORT_TEMP" "$CHRONOLOGY_REPORT"
mv "$PRESERVATION_REPORT_TEMP" "$PRESERVATION_REPORT"

echo
echo "Backup demo criado com sucesso:"
echo "  backup=$OUTPUT"
echo "  sha256=$candidate_sha"
echo "  validation=$VALIDATION"
echo "  credentials=$CREDENTIALS"
echo "  clinical_manifest=$MANIFEST"
echo "  patient_index=$PATIENT_INDEX"
echo "  cnes=$CNES_ARCHIVE"
echo "  coverage_contract=$COVERAGE_CONTRACT"
echo "  chronology=$CHRONOLOGY_REPORT"
echo "  preservation=$PRESERVATION_REPORT"
echo "  reference_date=$REFERENCE_DATE"
if [ "$REPORT_PROCESSING" != true ]; then
    echo
    echo "ATENÇÃO: selo parcial (validated-without-report-processing)."
    echo "Execute Administração > Processamento de relatórios na instalação"
    echo "de destino para que os relatórios Saúde 360 retornem resultados."
fi
