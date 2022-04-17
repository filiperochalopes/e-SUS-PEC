import json
from flask import Blueprint
from app.models.IniciarConsulta import Ciap

all_views = Blueprint('all', __name__,
                      template_folder='templates')

'''
- Lista de agravos mais atendidos top10
- Controle hiperdia (controles de glicemia, hba1c e pa)
- Controle gestantes
- procedimentos
- numero de atendimentos
- media atendimentos/dia
- qualidade de registro

- Colocando servidor
- Agendamentos controlados pela internet
'''


@all_views.route("/")
def dashboard():
    '''
    Tabelas envolvidas: tb_medicao
    '''
    # pacientes com diabetes
    # grafico com glicemias maiores que 200
    # grafico com pa maiores que 140/90
    # numero de pacientes com diabetes e pressao alta, asma e lista de problemas por ordem de incidencia
    cidadaos_cadastrados = None
    cidadaos_atendidos = None
    # numero de atendimentos ja registrados
    numero_atendimentos = None
    # numero de visitas domiciliares
    numero_visitas_domiciliares = None
    # numero de dias que houve atendimento
    dias_atendimento = None
    # problemas pesquisa o cidada, vê os problemas e coloca em uma lista
    pacientes_hba1c_maior_que_6 = None
    pacientes_hba1c_maior_que_7 = None
    return "<p>Hello, World!</p>"


@all_views.route("/pacientes")
def pacientes():
    '''
    Aqui aparece um mini prontuário de cada um com a opção de exportação em json para o PIN
    '''
    # buca por pacientes, mostrnado numero de telefone, numero de consultas, lista de problemas e documentos
    # a intencao aqui eh exportar o prontuario para o pin, comecar por aqui
    return "<p>Hello, World!</p>"


@all_views.route("/procedimentos")
def exames():
    Procedimento.query.all()
    return "<p>Hello, World!</p>"


@all_views.route("/medicamentos")
def medicamentos():
    '''
    Tabelas envolvidas: tb_medicamento, tb_forma_farmaceutica
    '''
    Medicamento.query.all()
    return "<p>Hello, World!</p>"


@all_views.route("/fixtures/<table>")
def fixtures(table: str = 'procedimentos'):
    '''
    Captura a lista em formato de fixtures
    '''
    if table == 'motivo_consulta':
        ciap_list_all = Ciap.query.all()
        return json.dumps([{'model': 'iniciar_consulta.MotivoConsulta', 'pk': ciap.co_ciap, 'fields': {'ciap2': ciap.co_ciap, 'nome': ciap.ds_ciap}} for ciap in ciap_list_all], indent=2)
    return "<p>Hello, World!</p>"


@all_views.route("/prescricoes")
def prescricoes():
    '''
    Tabelas envolvidas: tb_receita_medicamento, tb_medicamento, tb_forma_farmaceutica
    Retorna: json de prescrições prontas para alimentar
    '''
    return "<p>Hello, World!</p>"


@all_views.route("/db-test")
def db_test():
    cidadaos = Cidadao.query.all()
    for cidadao in cidadaos:
        print(cidadao.no_cidadao)
        print(cidadao.dt_nascimento)
        print(cidadao.nu_telefone_celular or cidadao.nu_telefone_contato)
    return "<p>Hello, World! 2</p>"
