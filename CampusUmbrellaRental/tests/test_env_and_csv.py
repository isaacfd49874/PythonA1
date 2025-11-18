
import os

def test_env_data_dir_from_fixture(app, tmp_path):
    assert str(tmp_path) in app.DATA_DIR

def test_seeding_created_all_csvs(app):
    assert os.path.exists(app.STUDENTS_CSV)
    assert os.path.exists(app.STAFF_CSV)
    assert os.path.exists(app.UMBRELLAS_CSV)
    assert os.path.exists(app.RESERVATIONS_CSV)
    assert os.path.exists(app.PAYMENTS_CSV)
    umbrellas = app.read_csv(app.UMBRELLAS_CSV)
    assert len(umbrellas) >= 6
    assert all(u["status"] == "Available" for u in umbrellas)

def test_migration_of_reservations_columns(app):
    legacy_rows = [{
        "id":"1","sid":"S123456","umbrella_id":"1","status":"Reserved",
        "reserved_at": app.now_str(),"pickup_at":"","due_at":"","return_at":"",
        "close_reason":"","notes":""
    }]
    app.write_csv(app.RESERVATIONS_CSV,
                  ["id","sid","umbrella_id","status","reserved_at","pickup_at","due_at","return_at","close_reason","notes"],
                  legacy_rows)
    app._migrate_reservations_columns()
    rows2 = app.read_csv(app.RESERVATIONS_CSV)
    assert "requested_days" in rows2[0]
    assert "start_date" in rows2[0]
    assert "end_date" in rows2[0]

def test_next_id_and_roundtrip_write_read(app):
    umb_rows = app.read_csv(app.UMBRELLAS_CSV)
    nid = app.next_id(umb_rows, "id")
    rec = {"id": nid, "code": f"UMB{int(nid):03d}", "status":"Available",
           "location":"MainStation","note":"","created_at":app.now_str(),"updated_at":app.now_str()}
    app.append_csv(app.UMBRELLAS_CSV, app.UMBRELLAS_HEADERS, rec)
    umb_rows2 = app.read_csv(app.UMBRELLAS_CSV)
    assert any(u["id"] == nid for u in umb_rows2)

def test_currency_helpers(app):
    cents = app.dollars_to_cents(20.0)
    assert cents == 2000
    s = app.cents_to_str(cents)
    assert s.startswith("HK$20.00")
