from pydantic import BaseModel, Field, field_validator
from enum import Enum

from ..core.utils import is_valid_page_range


class SidesOption(str, Enum):
    ONE_SIDED = "one-sided"
    TWO_SIDED_LONG = "two-sided-long-edge"
    TWO_SIDED_SHORT = "two-sided-short-edge"


class PrintOptions(BaseModel):
    copies: int = Field(1, ge=1)
    media: str = "A4"
    sides: SidesOption = SidesOption.ONE_SIDED
    fit_to_page: bool = True
    color: bool = False
    page_ranges: str = "all"
    number_up: int = Field(1, ge=1)

    @property
    def cups_options(self) -> dict:
        """
        Convert Pydantic model fields into CUPS options dictionary.
        """
        options = {
            "copies": str(self.copies),
            "media": self.media,
            "sides": self.sides,
            "fit-to-page": "true" if self.fit_to_page else "false",
            "print-color-mode": "color" if self.color else "monochrome",
            "number-up": str(self.number_up),
        }

        if self.page_ranges != "all":
            options["page-ranges"] = self.page_ranges

        return options
