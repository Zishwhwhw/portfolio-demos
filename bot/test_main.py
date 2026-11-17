import os
os.environ.setdefault("DB_PATH", ":memory:")
import pytest
from main import order_total

def test_total_and_text():
    assert order_total([{"id": 1, "qty": 2}, {"id": 4, "qty": 1}]) == (270, "Monstera × 2, Sunflower × 1")

def test_qty_is_clamped_and_unknown_rejected():
    assert order_total([{"id": 2, "qty": 999}])[0] == 45 * 20
    with pytest.raises(KeyError):
        order_total([{"id": 99, "qty": 1}])
    with pytest.raises(ValueError):
        order_total([])
