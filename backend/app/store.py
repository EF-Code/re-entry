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
        # Callers can mutate Pydantic model containers after construction, so
        # validate again at the store boundary before accepting a new case.
        validated = CaseState.model_validate(case.model_dump(mode="python"))
        with self._registry_lock:
            case_lock = self._case_locks.setdefault(validated.id, RLock())
        with case_lock, self._registry_lock:
            self._cases[validated.id] = validated.model_copy(deep=True)
            return self._cases[validated.id].model_copy(deep=True)

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
            if working.revision >= MAX_CASE_REVISION:
                # Refuse before invoking the transition. A future transition
                # may perform provider or connector work, so checking after
                # it runs could create an external side effect without a
                # representable committed revision.
                raise ValueError("case_revision_limit_reached")
            before = working.model_copy(deep=True)
            updated = transition(working)
            if not isinstance(updated, CaseState):
                raise TypeError("case transition must return CaseState")
            # Re-validate after arbitrary transition code has had a chance to
            # mutate list fields. The store owns identity and revision tokens;
            # transitions may update domain fields but cannot rewrite either.
            validated = CaseState.model_validate(updated.model_dump(mode="python"))
            if validated.id != case_id:
                raise ValueError("case_identity_mutation_forbidden")
            if validated.revision != before.revision:
                raise ValueError("case_revision_mutation_forbidden")
            # Idempotent transitions (for example a duplicate upload or a
            # repeated demo rejection) must not invalidate an approval that
            # was based on the current revision. Compare the complete working
            # state before advancing the optimistic-concurrency token.
            if validated == before:
                return validated.model_copy(deep=True)
            validated.revision = before.revision + 1
            with self._registry_lock:
                self._cases[case_id] = validated.model_copy(deep=True)
                return validated.model_copy(deep=True)

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
