"""Small in-memory case store for the synthetic demo."""

from __future__ import annotations

from threading import RLock

from .demo_data import clone_demo_case
from .models import CaseState


class CaseStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._cases: dict[str, CaseState] = {"case-042": clone_demo_case()}

    def get(self, case_id: str) -> CaseState:
        with self._lock:
            case = self._cases.get(case_id)
            if case is None:
                raise KeyError("case_not_found")
            return case.model_copy(deep=True)

    def put(self, case: CaseState) -> CaseState:
        with self._lock:
            self._cases[case.id] = case.model_copy(deep=True)
            return case.model_copy(deep=True)

    def reset(self, case_id: str) -> CaseState:
        with self._lock:
            if case_id != "case-042":
                raise KeyError("case_not_found")
            self._cases[case_id] = clone_demo_case()
            return self._cases[case_id].model_copy(deep=True)

