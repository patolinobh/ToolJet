import pytest
from app.services.vin_decoder import is_valid_vin, normalize_vin


def test_valid_vin():
    assert is_valid_vin("9BWZZZ377VT004251")


def test_invalid_vin():
    assert not is_valid_vin("INVALIDVIN123")


def test_normalize_vin():
    assert normalize_vin(" 9bwzzz377vt004251 ") == "9BWZZZ377VT004251"
