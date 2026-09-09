from datetime import date

from pec_demo.citizens import TerritoryAssignment, _citizen_input
from pec_demo.patients import build_patient_cohort


def test_citizen_input_includes_the_current_microarea():
    patient = build_patient_cohort(seed=5522, generated_on=date(2026, 7, 27))[0]

    result = _citizen_input(
        patient,
        citizen_id="42",
        municipality_id="123",
        professional_cns="123456789012345",
        cnes="9999999",
        ine="9999999999",
        cbo2002="225130",
        microarea="01",
    )

    assert result["id"] == "42"
    assert result["vinculacaoCidadaoTerritorio"] == {
        "cbo2002": "225130",
        "cnes": "9999999",
        "cns": "123456789012345",
        "ine": "9999999999",
        "microarea": "01",
        "foraDeArea": False,
    }


def test_territory_assignment_has_three_demo_microareas_by_default():
    assignment = TerritoryAssignment(cnes="1", ine="2", cbo2002="3")

    assert assignment.microareas == ("01", "02", "03")
