"""API smoke tests for the stateless engine surface."""

from fastapi.testclient import TestClient

from quoteforge_api.main import app

client = TestClient(app)


def test_healthz():
    # No DB is wired in this stateless surface, so 'db' may be False ('degraded').
    r = client.get("/api/healthz")
    assert r.status_code == 200
    assert "db" in r.json()
    assert r.json()["status"] in {"ok", "degraded"}


def test_list_assemblies():
    r = client.get("/api/assemblies")
    assert r.status_code == 200
    ids = {a["id"] for a in r.json()["assemblies"]}
    assert "circuit_new_15a_residential" in ids


def test_preview_matches_engine_fixture():
    body = {
        "contractor": {"blended_labor_rate_cad": 110, "default_material_markup_pct": 35},
        "province": "ON",
        "code_edition": "OESC 2024 (28th)",
        "assemblies": [{
            "assembly_id": "circuit_new_15a_residential",
            "quantity": 1,
            "parameters": {"run_length_ft": 40, "access": "open"},
        }],
    }
    r = client.post("/api/estimate/preview", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["total_cad"] == "242.02"


def test_preview_underbid_blocks_pdf():
    body = {
        "contractor": {"blended_labor_rate_cad": 110, "default_material_markup_pct": 0,
                       "minimum_margin_pct": 20},
        "province": "ON",
        "code_edition": "OESC 2024 (28th)",
        "assemblies": [{"assembly_id": "ev_charger_l2_attached_garage", "quantity": 1,
                        "parameters": {"wire_run_ft": 30}}],
    }
    r = client.post("/api/estimate/preview", json=body)
    data = r.json()
    assert data["pdf_blocked"] is True
    assert "MARGIN_BELOW_MIN" in {f["code"] for f in data["audit_flags"]}


def test_preview_unknown_assembly_422():
    body = {
        "contractor": {"blended_labor_rate_cad": 110},
        "province": "ON",
        "code_edition": "x",
        "assemblies": [{"assembly_id": "nope_not_real", "quantity": 1}],
    }
    r = client.post("/api/estimate/preview", json=body)
    assert r.status_code == 422
