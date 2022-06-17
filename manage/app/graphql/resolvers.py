import json
from pprint import pp
from . import query
import random

from app.serializers import ReceitaSchema
from app.models.IniciarConsulta import Ciap
from app.models.Medicamento import Medicamento, Receita

random_instance = random.Random(500)

@query.field("fixtures")
def fixtures(*_, table=None, model=None):
    if table == 'ciap':
        ciap_list_all = Ciap.query.all()
        return [{'model': model, 'pk': ciap.co_ciap, 'fields': json.dumps({'ciap2': ciap.co_ciap, 'nome': ciap.ds_ciap})} for ciap in ciap_list_all]
    elif table == 'medicamento':
        medicamento_list_all = Medicamento.query.all()
        return [{'model': model, 'pk': m.co_seq_medicamento, 'fields': json.dumps({'nome': m.no_principio_ativo, 'concentracao': m.ds_concentracao, 'forma_farmaceutica': m.co_forma_farmaceutica, 'unidade_fornecimento': m.ds_unidade_fornecimento})} for m in medicamento_list_all]
    return []

@query.field("prescriptions")
def prescriptions(*_):
    receitas_schema = ReceitaSchema(many=True)
    receitas = Receita.query.all()
    prescriptions = []
    for r in receitas_schema.dump(receitas):
        # verifica o medicamento
        drug = f"{r['medicamento']['no_principio_ativo']} {r['medicamento']['ds_concentracao']}"

        # Verifica a dose
        dose = r['ds_dose']

        # Ver forma de administração. Se a dose tiver muitos caracteres é pq a forma de uso foi escrita nele.
        route = r['via_administracao']['no_aplicacao_med_filtro']
        verbs = {
            'oral': ['ingerir, por via oral,', 'engolir, via oral,', 'via oral,'],
            'vaginal': ['aplicar, por via vaginal'],
            'intramuscular': ['aplicar, por via vaginal'],
            'intravenosa': ['aplicar, por via vaginal', 'via vaginal, '],
            'subcutanea': ['aplicar, por via subcutanea', 'injetar, via subcutanea, ', 'via subcutânea,'],
            'oftalmica': ['aplicar, por via oftalmica', 'pingar no olho acometido, ', 'pingar nos olhos,'],
            'local': ['tópico', 'ação local,', 'na pele,'],
            'inalatoria por via oral': ['inalar, por via oral,', 'Aspirar, por via oral', 'inalação por via oral,'],
            'otologica': ['pingar nos ouvidos,', 'Pingar no ouvido acometido', 'pingar no ouvido doente,'],
            'retal': ['aplicar, por via retal,', 'inserir por via anal/retal,'],
            'nasal': ['pingar no nariz', 'em cada narina'],
            'sublingual': ['colocar debaixo da língua', 'ingerir, por via sublingual,', 'dissolver embaixo da língua'],
        }

        # Verifica frequencia do tratamento 12/12h ou 1x a cada 5 dias
        # 1. Verifica qual o tipo da frequenci, para ver se vai ser necessário ver o tempo da frequencia
        if not r['tipo_frequencia_dose']:
            continue
        if r['tipo_frequencia_dose']['no_identificador'] == 'FREQUENCIA':
            # transformando unidades no singular
            time_unit = r['frequencia_dose_tempo']['no_unidade_medida_tempo'].lower()
            singular_time_unit = {
                'dias': 'dia',
                'meses': 'mes',
                'semanas': 'semana',
                'anos': 'ano'
            }
            if r['qt_periodo_frequencia'] <= 1:
                time_unit = singular_time_unit[time_unit]
            # Verifica qual o tempo da frequencia
            time_unit_phrase = f"a cada {r['qt_periodo_frequencia']} {time_unit}" if time_unit != 'dia' else 'ao dia'
            dose_frequence = f"{r['ds_frequencia_dose']}x {time_unit_phrase}"
        elif r['tipo_frequencia_dose']['no_identificador'] == 'TURNO':
            dose_frequence = f"pela {r['ds_frequencia_dose']}"
        else:
            dose_frequence = f"de {r['ds_frequencia_dose']}/{r['ds_frequencia_dose']}h"
        # Verifica se é contínuo ou tem número de dias
        if r['st_uso_continuo'] == True:
            dose_duration = random_instance.choice(['- contínuo', '- uso contínuo', '. uso contínuo'])
        elif r['st_dose_unica'] == True:
            dose_duration = 'dose única'
        elif r['tempo_tratamento']['no_unidade_medida_tempo'].lower() != 'indeterminado':
            dose_duration = f"por {r['qt_duracao_tratamento']} {r['tempo_tratamento']['no_unidade_medida_tempo'].lower()}"
        else:
            dose_duration = ''

        recommendations = r['ds_recomendacao'] or ''
        prescriptions.append(f"{drug}. {random_instance.choice(verbs[route])} {dose} {dose_frequence} {dose_duration}. {recommendations}")

    return prescriptions
    