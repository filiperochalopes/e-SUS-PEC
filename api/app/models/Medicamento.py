from app import db
from sqlalchemy.orm import relationship


class Medicamento(db.Model):
    co_seq_medicamento = db.Column(db.Integer, primary_key=True)
    no_principio_ativo = db.Column(db.Text)
    ds_concentracao = db.Column(db.Text)
    co_forma_farmaceutica = db.Column(db.Integer, db.ForeignKey(
        'tb_forma_farmaceutica.co_forma_farmaceutica'), nullable=False)
    ds_unidade_fornecimento = db.Column(db.Text)
    
    forma_farmaceutica = relationship(
        'FormaFarmaceutica', uselist=False, lazy='selectin', foreign_keys=[co_forma_farmaceutica])

    receitas = relationship('Receita', back_populates="medicamento")

    __tablename__ = "tb_medicamento"

    def __repr__(self):
        return f'<Medicamento {self.no_principio_ativo} {self.ds_concentracao}>'


class FormaFarmaceutica(db.Model):
    co_forma_farmaceutica = db.Column(db.Integer, primary_key=True)
    no_forma_farmaceutica = db.Column(db.Text)
    st_ativo = db.Column(db.Boolean)

    __tablename__ = "tb_forma_farmaceutica"


class ViaAdministracao(db.Model):
    co_aplicacao_medicamento = db.Column(db.Integer, primary_key=True)
    no_aplicacao_med_filtro = db.Column(db.Text)

    __tablename__ = "tb_aplicacao_medicamento"


class TipoFrequencia(db.Model):
    '''
    Para verificação do 'nome' da frequencia, se é 1 - TURNO (manhã, tarde, noite), 2 - FREQUENCIA (1x, 2x...) ou 3 - INTERVALO (2/2h, 6/6h, ...)
    '''
    co_receita_tipo_frequencia = db.Column(db.Integer, primary_key=True)
    no_identificador = db.Column(db.Text)

    __tablename__ = "tb_receita_tipo_frequencia"


class DuracaoTratamentoUnidadeMedida(db.Model):
    '''
    Para verificação do 'nome' da duração de tratamento, se são dias, semanas, meses ou indeterminado
    '''
    cod_seq_dim_duracao_trat_med = db.Column(db.Integer, primary_key=True)
    no_duracao_tratamento_med_filt = db.Column(db.Text)

    __tablename__ = "tb_dim_duracao_tratamento_med"


class Receita(db.Model):
    co_seq_receita_medicamento = db.Column(db.Integer, primary_key=True)
    ds_dose = db.Column(db.Text, comment='Dose, ex.: 1 comprimido, 15ml')

    qt_receitada = db.Column(
        db.Text, comment='Quantidade de comprimidos ou frascos receitados')
    
    qt_duracao_tratamento = db.Column(db.Integer,nullable=True, comment='Quantidade de duração do tratamento')
    tp_un_medida_tempo_tratamento = db.Column(db.Integer, db.ForeignKey(
        'tb_unidade_medida_tempo.co_unidade_medida_tempo'),nullable=True, comment='Tipo da unidade de medida do tempo do tratamento')
    
    qt_periodo_frequencia = db.Column(db.Integer,nullable=True, comment='Quantidade da frequência "a durante >> 1 << Mês" ')
    tp_un_medida_tempo_frequencia = db.Column(db.Integer, db.ForeignKey(
        'tb_unidade_medida_tempo.co_unidade_medida_tempo'), nullable=True, comment='Tipo da unidade de medida do tempo da frequencia "Durante 1 >> Mês <<')
        
    st_uso_continuo = db.Column(db.Boolean)
    st_dose_unica = db.Column(db.Boolean)

    ds_frequencia_dose = db.Column(
        db.Text, comment='1,2,3 para uma vez ao dia, duas vezes... manha, tarde, noite ou 6,8,12,24 para 6/6h...')
    tp_frequencia_dose = db.Column(db.Integer, db.ForeignKey(
        'tb_receita_tipo_frequencia.co_receita_tipo_frequencia'), nullable=True,)

    st_registro_manual = db.Column(db.Boolean)
    ds_recomendacao = db.Column(
        db.Text, comment='Recomendação/Observação em html')

    co_aplicacao_medicamento = db.Column(db.Integer, db.ForeignKey(
        'tb_aplicacao_medicamento.co_aplicacao_medicamento'), nullable=False)
    co_medicamento = db.Column(db.Integer, db.ForeignKey(
        'tb_medicamento.co_seq_medicamento'), nullable=False)

    tipo_frequencia_dose = relationship(
        'TipoFrequencia', uselist=False, lazy='selectin', foreign_keys=[tp_frequencia_dose])
    frequencia_dose_tempo = relationship(
        'UnidadeMedidaTempo', uselist=False, lazy='selectin', foreign_keys=[tp_un_medida_tempo_frequencia])
    tempo_tratamento = relationship(
        'UnidadeMedidaTempo', uselist=False, lazy='selectin', foreign_keys=[tp_un_medida_tempo_tratamento])
    via_administracao = relationship(
        'ViaAdministracao', uselist=False, lazy='selectin', foreign_keys=[co_aplicacao_medicamento])
    medicamento = relationship('Medicamento', back_populates="receitas")

    __tablename__ = "tb_receita_medicamento"


class UnidadeMedida(db.Model):
    '''
    Unidade de medida para apresentação do medicamento: ampola, barra, tubo
    '''
    co_unidade_medida = db.Column(db.Integer, primary_key=True)
    no_unidade_medida = db.Column(db.Text)

    __tablename__ = "tb_unidade_medida"


class UnidadeMedidaTempo(db.Model):
    '''
    Unidade de medida de tempo: hora, dia, semana
    '''
    co_unidade_medida_tempo = db.Column(db.Integer, primary_key=True)
    no_unidade_medida_tempo = db.Column(db.Text)

    __tablename__ = "tb_unidade_medida_tempo"
