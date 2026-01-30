from broken_app.main import calculate_discount


def test_twenty_percent_discount():
    """200 with 20% discount should be 160."""
    assert calculate_discount(200, 20) == 160


def test_ten_percent_discount():
    """50 with 10% discount should be 45."""
    assert calculate_discount(50, 10) == 45


def test_full_discount():
    """75 with 100% discount should be 0."""
    assert calculate_discount(75, 100) == 0
