from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class NumberEntry(BaseModel):
    value: float
    path: str
    origin: str
    expected_value: float
    tolerance: float = 0.01

class NumberRegistry:
    def __init__(self, entries: Optional[List[NumberEntry]] = None):
        self.entries: List[NumberEntry] = entries or []

    def register(
        self,
        value: float,
        path: str,
        origin: str,
        expected_value: float,
        tolerance: float = 0.01
    ) -> None:
        self.entries.append(
            NumberEntry(
                value=round(float(value), 4),
                path=path,
                origin=origin,
                expected_value=round(float(expected_value), 4),
                tolerance=tolerance
            )
        )

    def lookup_number(self, val: float, tolerance: float = 0.05) -> bool:
        """Checks if a numeric value matches any registered entry within relative or absolute tolerance."""
        for e in self.entries:
            abs_diff = abs(e.value - val)
            if abs_diff <= tolerance:
                return True
            # Check percentage scale (e.g. 0.02 vs 2.0%)
            if abs(e.value * 100.0 - val) <= tolerance:
                return True
            if val != 0 and abs(abs_diff / val) <= tolerance:
                return True
        return False

    def verify_all(self) -> List[Dict[str, Any]]:
        failures = []
        for e in self.entries:
            diff = abs(e.value - e.expected_value)
            if diff > e.tolerance:
                failures.append({
                    "path": e.path,
                    "origin": e.origin,
                    "value": e.value,
                    "expected": e.expected_value,
                    "diff": diff,
                    "tolerance": e.tolerance
                })
        return failures

    def to_dict(self) -> List[Dict[str, Any]]:
        return [e.model_dump() for e in self.entries]

    @classmethod
    def from_dict(cls, data: Any) -> "NumberRegistry":
        if isinstance(data, list):
            return cls([NumberEntry.model_validate(item) for item in data])
        return cls([])
