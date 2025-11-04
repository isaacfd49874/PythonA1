
import csv

def test_student_login_success_plaintext(app):
    rows = app.read_csv(app.STUDENTS_CSV)
    assert rows, "students.csv should be seeded"
    assert "password" in rows[0], "students.csv must have a 'password' column"
    assert rows[0]["password"] == "student123"

    user = app.login_student("S123456", "student123")
    assert user is not None
    assert user["sid"] == "S123456"

def test_staff_login_success_plaintext(app):
    rows = app.read_csv(app.STAFF_CSV)
    assert rows, "staff.csv should be seeded"
    assert "password" in rows[0], "staff.csv must have a 'password' column"
    assert rows[0]["password"] == "staff123"

    user = app.login_staff("T001", "staff123")
    assert user is not None
    assert user["staff_id"] == "T001"

def test_wrong_password(app):
    user = app.login_student("S123456", "wrongpw")
    assert user is None
