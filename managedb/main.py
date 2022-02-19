from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

DATABASE_URL = os.getenv('DATABASE_URL')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
db = SQLAlchemy(app)

# TODO tb_evolucao_objetivo
# TODO tb_evolucao_subjetivo
# TODO tb_evolucao_avaliacao
# TODO tb_evolucao_plano
# TODO tb_exame_requisitado
# TODO rl_evolucao_avaliacao_ciap_cid


class Cidadao(db.Model):
    co_seq_cidadao = db.Column(db.Integer, primary_key=True)
    no_cidadao = db.Column(db.Text)
    nu_cns = db.Column(db.Text)
    nu_telefone_residencial = db.Column(db.Text)
    nu_telefone_celular = db.Column(db.Text)
    nu_telefone_contato = db.Column(db.Text)
    no_sexo = db.Column(db.Text)
    dt_nascimento = db.Column(db.DateTime)

    __tablename__ = "tb_cidadao"

    def __repr__(self):
        return '<User %r>' % self.nu_cns


@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"


@app.route("/db-test")
def db_test():
    cidadaos = Cidadao.query.all()
    for cidadao in cidadaos:
        print(cidadao.no_cidadao)
        print(cidadao.dt_nascimento)
        print(cidadao.nu_telefone_celular or cidadao.nu_telefone_contato)
    return "<p>Hello, World! 2</p>"


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
