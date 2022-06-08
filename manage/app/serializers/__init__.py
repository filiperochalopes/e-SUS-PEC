from app import ma
from app.models.Medicamento import Medicamento, Receita
from marshmallow_sqlalchemy import fields

class MedicamentoSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Medicamento

class ReceitaSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Receita
        include_fk = True
        load_instance = True
        include_relationships = True
    
    medicamento = fields.Nested(MedicamentoSchema)