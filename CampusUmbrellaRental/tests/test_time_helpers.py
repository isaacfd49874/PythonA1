
def test_week_helpers_present_or_skip(app):
    import pytest
    if not hasattr(app, "start_of_week"):
        pytest.skip("Weekly report helpers not present; UI-only in this version")
    wk = app.week_key_from_dt(app.now_dt())
    label = app.week_label(wk)
    assert isinstance(label, str) and label
