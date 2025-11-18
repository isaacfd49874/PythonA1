
def test_overdue_blocks_reservation_until_paid(app):
    rec = app.add_payment("S123456", "0", "overdue", 2000)
    can, reason = app.can_student_reserve("S123456")
    assert not can and "overdue" in reason.lower()

    app.settle_payment(rec["id"], "paid", note_append="test paid")
    can2, reason2 = app.can_student_reserve("S123456")
    assert can2

def test_settle_payment_rules(app):
    rec = app.add_payment("S123456", "0", "overdue", 2000)
    app.settle_payment(rec["id"], "paid")
    import pytest
    with pytest.raises(ValueError):
        app.settle_payment(rec["id"], "void")
