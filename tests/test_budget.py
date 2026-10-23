import pytest

from pra.budget import Budget, BudgetExceeded


def test_step_limit():
    b = Budget(max_steps=2)
    b.charge()
    b.charge()
    with pytest.raises(BudgetExceeded):
        b.charge()


def test_token_limit():
    b = Budget(max_tokens=10)
    with pytest.raises(BudgetExceeded):
        b.charge(tokens=11)
