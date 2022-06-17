from app import db
from sqlalchemy.orm import relationship
from app.models.IniciarConsulta import Cid10

# TODO tb_evolucao_objetivo
# TODO tb_evolucao_subjetivo
# TODO tb_evolucao_avaliacao
# TODO tb_evolucao_plano
# TODO tb_exame_requisitado


class AtendimentoProfissional(db.Model):
    '''
    Atendimento profissional é o atendimento feito por um único profissional em um dia de dida à unidade de saúde
    '''
    co_seq_atend_prof = db.Column(db.Integer, primary_key=True)
    dt_fim = db.Column(db.DateTime)
    dt_inicio = db.Column(db.DateTime)
    co_atend = db.Column(db.Integer, db.ForeignKey(
        'tb_atend.co_seq_atend'), nullable=True)
    
    atendimento = relationship(
        'Atendimento', uselist=False, lazy='selectin', foreign_keys=[co_atend])

    __tablename__ = "tb_atend_prof"


class Atendimento(db.Model):
    '''
    Um atendimento é como uma ida ao posto de saúde, nessa ida podem ser realizadas vários atendimentos profissionais: triagem, vacina...
    '''
    co_seq_atend = db.Column(db.Integer, primary_key=True)
    co_prontuario = db.Column(db.Integer)
    st_registro_tardio = db.Column(db.Integer)
    tp_local_atend = db.Column(db.Integer)

    __tablename__ = "tb_atend"


class Prontuario(db.Model):
    '''
    Cada prnotuário pertence a um indivíduo
    '''
    co_seq_prontuario = db.Column(db.Integer, primary_key=True)
    co_cidadao = db.Column(db.Integer)

    __tablename__ = "tb_prontuario"


class Problema(db.Model):
    co_seq_evolucao_aval_ciap_cid = db.Column(db.Integer, primary_key=True)
    co_cid10 = db.Column(db.Integer, db.ForeignKey(
        'tb_cid10.co_cid10'), nullable=True)
    ds_nota = db.Column(db.Text)
    co_atend_prof = db.Column(db.Integer, db.ForeignKey(
        'tb_atend_prof.co_seq_atend_prof'), nullable=True)

    atendimento_profissional = relationship(
        'AtendimentoProfissional', uselist=False, lazy='selectin', foreign_keys=[co_atend_prof])
    
    cid10 = relationship(
        'Cid10', uselist=False, lazy='selectin', foreign_keys=[co_cid10])

    __tablename__ = "tl_evolucao_avaliacao_ciap_cid"

    def __repr__(self):
        return f'<Problema {self.co_cid10}>'
