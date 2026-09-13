"""Small in-memory case store for the synthetic demo."""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock

from .demo_data import clone_demo_case
from .models import MAX_CASE_REVISION, CaseState


class CaseStore:
    def __init__(self) -> None:
        self._registry_lock = RLock()
        self._cases: dict[str, CaseState] = {"case-042": clone_demo_case()}
        self._case_locks: dict[str, RLock] = {"case-042": RLock()}

    def _lock_for(self, case_id: str) -> RLock:
        with self._registry_lock:
            if case_id not in self._cases:
                raise KeyError("case_not_found")
            return self._case_locks.setdefault(case_id, RLock())

    def get(self, case_id: str) -> CaseState:
        case_lock = self._lock_for(case_id)
        with case_lock, self._registry_lock:
            return self._cases[case_id].model_copy(deep=True)

    def put(self, case: CaseState) -> CaseState:
        with self._registry_lock:
            case_lock = self._case_locks.setdefault(case.id, RLock())
        with case_lock, self._registry_lock:
            self._cases[case.id] = case.model_copy(deep=True)
            return self._cases[case.id].model_copy(deep=True)

    def apply(self, case_id: str, transition: Callable[[CaseState], CaseState]) -> CaseState:
        """Apply one case transition while holding only that case's lock.

        A live planner may perform bounded network I/O during ``transition``.
        Per-case locks keep approvals and plans serialized for one case while
        allowing unrelated cases to progress independently in this demo
        process. A durable multi-worker store remains required for production.
        """

        case_lock = self._lock_for(case_id)
        with case_lock:
            with self._registry_lock:
                case = self._cases[case_id]
                working = case.model_copy(deep=True)
            before = working.model_copy(deep=True)
            updated = transition(working)
            # Idempotent transitions (for example a duplicate upload or a
            # repeated demo rejection) must not invalidate an approval that
            # was based on the current revision. Compare the complete working
            # state before advancing the optimistic-concurrency token.
            if updated == before:
                return updated.model_copy(deep=True)
            if working.revision >= MAX_CASE_REVISION:
                raise ValueError("case_revision_limit_reached")
            updated.revision = working.revision + 1
            with self._registry_lock:
                self._cases[case_id] = updated.model_copy(deep=True)
                return updated.model_copy(deep=True)

    def reset(self, case_id: str) -> CaseState:
        case_lock = self._lock_for(case_id)
        with case_lock:
            if case_id != "case-042":
                raise KeyError("case_not_found")
            with self._registry_lock:
                replacement = clone_demo_case()
                current_revision = self._cases[case_id].revision
                if current_revision >= MAX_CASE_REVISION:
                    raise ValueError("case_revision_limit_reached")
                replacement.revision = current_revision + 1
                self._cases[case_id] = replacement
                return self._cases[case_id].model_copy(deep=True)
