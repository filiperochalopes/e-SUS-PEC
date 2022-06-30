from app import db


class Ciap(db.Model):
    co_ciap = db.Column(db.String, primary_key=True)
    ds_ciap = db.Column(db.Text)

    __tablename__ = "tb_ciap"

    def __repr__(self):
        return '<CIAP {} {}>'.format(self.co_ciap, self.ds_ciap)


class Cid10(db.Model):
    co_cid10 = db.Column(db.Integer, primary_key=True)
    nu_cid10 = db.Column(db.String)
    no_cid10 = db.Column(db.Text)
    no_cid10_filtro = db.Column(db.Text)

    __tablename__ = "tb_cid10"

    def __repr__(self):
        return f'<CID10 {self.nu_cid10} {self.no_cid10_filtro}>'
