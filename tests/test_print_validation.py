import pytest
from pydantic import ValidationError

from src.schemas.print import PrintOptions


class TestPrintOptionsValidation:
    def test_default_copies_and_number_up_are_valid(self):
        opts = PrintOptions()
        assert opts.copies == 1
        assert opts.number_up == 1

    def test_zero_copies_is_rejected(self):
        with pytest.raises(ValidationError):
            PrintOptions(copies=0)

    def test_negative_copies_is_rejected(self):
        with pytest.raises(ValidationError):
            PrintOptions(copies=-1)

    def test_zero_number_up_is_rejected(self):
        with pytest.raises(ValidationError):
            PrintOptions(number_up=0)

    def test_negative_number_up_is_rejected(self):
        with pytest.raises(ValidationError):
            PrintOptions(number_up=-1)
