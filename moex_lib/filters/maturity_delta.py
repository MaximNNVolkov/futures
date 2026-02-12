from dataclasses import dataclass

@dataclass(frozen=True)
class MaturityDelta:
    years: int = 0
    months: int = 0

    def to_months(self) -> int:
        return self.years * 12 + self.months
