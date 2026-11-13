"""Tests for coding_client.types.state_machine."""

from __future__ import annotations

from typing import Any

import pytest
from coding_client.types.state_machine import (
    ANALYSIS_TRANSITIONS,
    CONTAINER_TRANSITIONS,
    HEALTH_TRANSITIONS,
    RESPONSE_TRANSITIONS,
    AnalysisStateMachine,
    ContainerStateMachine,
    HealthStateMachine,
    ResponseStateMachine,
    StateMachine,
    StateTransition,
    StateTransitionError,
    StateTransitionRule,
    create_analysis_state_machine,
    create_container_state_machine,
    create_health_state_machine,
    create_response_state_machine,
    create_state_machine,
)

# ---------------------------------------------------------------------------
# StateTransition dataclass
# ---------------------------------------------------------------------------


class TestStateTransition:
    def test_str_representation(self):
        t = StateTransition(from_state="a", to_state="b")
        assert str(t) == "a -> b"

    def test_fields(self):
        t = StateTransition(from_state="x", to_state="y", trigger="manual", metadata={"k": "v"})
        assert t.from_state == "x"
        assert t.to_state == "y"
        assert t.trigger == "manual"
        assert t.metadata == {"k": "v"}

    def test_timestamp_auto_set(self):
        t = StateTransition(from_state="a", to_state="b")
        assert t.timestamp is not None


# ---------------------------------------------------------------------------
# StateTransitionError
# ---------------------------------------------------------------------------


class TestStateTransitionError:
    def test_attributes(self):
        err = StateTransitionError("running", "creating", "not allowed")
        assert err.from_state == "running"
        assert err.to_state == "creating"
        assert "running" in str(err)
        assert "creating" in str(err)

    def test_is_exception(self):
        assert issubclass(StateTransitionError, Exception)


# ---------------------------------------------------------------------------
# Generic StateMachine
# ---------------------------------------------------------------------------


class TestStateMachine:
    def _simple_machine(self) -> StateMachine:
        transitions: dict[str, frozenset[str]] = {
            "idle": frozenset(["active"]),
            "active": frozenset(["idle", "done"]),
            "done": frozenset(),
        }
        return StateMachine("idle", transitions)

    def test_initial_state(self):
        sm = self._simple_machine()
        assert sm.current_state == "idle"

    def test_valid_transition(self):
        sm = self._simple_machine()
        result = sm.transition_to("active")
        assert result is True
        assert sm.current_state == "active"

    def test_invalid_transition_raises(self):
        sm = self._simple_machine()
        with pytest.raises(StateTransitionError):
            sm.transition_to("done")

    def test_can_transition_to_valid(self):
        sm = self._simple_machine()
        assert sm.can_transition_to("active") is True

    def test_can_transition_to_invalid(self):
        sm = self._simple_machine()
        assert sm.can_transition_to("done") is False

    def test_history_tracking(self):
        sm = self._simple_machine()
        sm.transition_to("active")
        sm.transition_to("done")
        history = sm.transition_history
        assert len(history) == 2
        assert history[0].from_state == "idle"
        assert history[0].to_state == "active"
        assert history[1].from_state == "active"
        assert history[1].to_state == "done"

    def test_history_returns_copy(self):
        sm = self._simple_machine()
        sm.transition_to("active")
        h1 = sm.transition_history
        h1.clear()
        assert len(sm.transition_history) == 1

    def test_max_history_trimming(self):
        transitions: dict[str, frozenset[str]] = {
            "a": frozenset(["b"]),
            "b": frozenset(["a"]),
        }
        sm = StateMachine("a", transitions, max_history=3)
        for _ in range(5):
            sm.transition_to("b")
            sm.transition_to("a")
        assert len(sm.transition_history) <= 3

    def test_callback_on_transition(self):
        sm = self._simple_machine()
        callback_log: list[tuple] = []
        sm.add_state_change_callback("active", lambda f, t: callback_log.append((f, t)))
        sm.transition_to("active")
        assert len(callback_log) == 1
        assert callback_log[0] == ("idle", "active")

    def test_callback_not_triggered_for_other_state(self):
        sm = self._simple_machine()
        callback_log: list[tuple] = []
        sm.add_state_change_callback("done", lambda f, t: callback_log.append((f, t)))
        sm.transition_to("active")
        assert len(callback_log) == 0

    def test_get_valid_transitions(self):
        sm = self._simple_machine()
        valid = sm.get_valid_transitions()
        assert valid == frozenset(["active"])

    def test_is_terminal_state(self):
        sm = self._simple_machine()
        sm.transition_to("active")
        sm.transition_to("done")
        assert sm.is_terminal_state() is True

    def test_not_terminal_state(self):
        sm = self._simple_machine()
        assert sm.is_terminal_state() is False

    def test_get_state_summary(self):
        sm = self._simple_machine()
        summary = sm.get_state_summary()
        assert summary["current_state"] == "idle"
        assert "active" in summary["valid_transitions"]
        assert summary["is_terminal"] is False
        assert summary["transition_count"] == 0
        assert summary["last_transition"] is None

    def test_get_state_summary_after_transition(self):
        sm = self._simple_machine()
        sm.transition_to("active")
        summary = sm.get_state_summary()
        assert summary["transition_count"] == 1
        assert summary["last_transition"] is not None

    def test_force_transition_bypasses_validation(self):
        sm = self._simple_machine()
        sm.force_transition_to("done", reason="test bypass")
        assert sm.current_state == "done"

    def test_force_transition_records_history(self):
        sm = self._simple_machine()
        sm.force_transition_to("done", reason="override")
        history = sm.transition_history
        assert len(history) == 1
        assert history[0].metadata.get("forced") is True
        assert "FORCED" in history[0].trigger

    def test_transition_with_trigger_and_metadata(self):
        sm = self._simple_machine()
        sm.transition_to("active", trigger="user_click", metadata={"user": "test"})
        h = sm.transition_history[0]
        assert h.trigger == "user_click"
        assert h.metadata == {"user": "test"}

    def test_transition_rule_condition_blocks(self):
        transitions: dict[str, frozenset[str]] = {
            "idle": frozenset(["active"]),
            "active": frozenset(),
        }
        rule = StateTransitionRule(
            from_state="idle",
            to_state="active",
            condition=lambda sm: False,
            description="always deny",
        )
        sm = StateMachine("idle", transitions, transition_rules=[rule])
        assert sm.can_transition_to("active") is False
        with pytest.raises(StateTransitionError):
            sm.transition_to("active")

    def test_transition_rule_action_executed(self):
        transitions: dict[str, frozenset[str]] = {
            "idle": frozenset(["active"]),
            "active": frozenset(),
        }
        action_log: list[str] = []
        rule = StateTransitionRule(
            from_state="idle",
            to_state="active",
            action=lambda sm: action_log.append("fired"),
        )
        sm = StateMachine("idle", transitions, transition_rules=[rule])
        sm.transition_to("active")
        assert action_log == ["fired"]

    def test_transition_rule_action_failure_returns_false(self):
        transitions: dict[str, frozenset[str]] = {
            "idle": frozenset(["active"]),
            "active": frozenset(),
        }

        def bad_action(sm: Any) -> None:
            raise RuntimeError("action failed")

        rule = StateTransitionRule(from_state="idle", to_state="active", action=bad_action)
        sm = StateMachine("idle", transitions, transition_rules=[rule])
        result = sm.transition_to("active")
        assert result is False

    def test_callback_exception_does_not_propagate(self):
        sm = self._simple_machine()

        def bad_callback(f: str, t: str) -> None:
            raise RuntimeError("callback boom")

        sm.add_state_change_callback("active", bad_callback)
        result = sm.transition_to("active")
        assert result is True
        assert sm.current_state == "active"


# ---------------------------------------------------------------------------
# ContainerStateMachine
# ---------------------------------------------------------------------------


class TestContainerStateMachine:
    def test_default_initial_state(self):
        sm = ContainerStateMachine()
        assert sm.current_state == "creating"

    def test_custom_initial_state(self):
        sm = ContainerStateMachine(initial_state="running")
        assert sm.current_state == "running"

    def test_creating_to_running(self):
        sm = ContainerStateMachine()
        sm.transition_to("running")
        assert sm.current_state == "running"

    def test_creating_to_error(self):
        sm = ContainerStateMachine()
        sm.transition_to("error")
        assert sm.current_state == "error"

    def test_running_to_stopped(self):
        sm = ContainerStateMachine()
        sm.transition_to("running")
        sm.transition_to("stopped")
        assert sm.current_state == "stopped"

    def test_running_to_paused(self):
        sm = ContainerStateMachine()
        sm.transition_to("running")
        sm.transition_to("paused")
        assert sm.current_state == "paused"

    def test_stopped_to_running(self):
        sm = ContainerStateMachine()
        sm.transition_to("running")
        sm.transition_to("stopped")
        sm.transition_to("running")
        assert sm.current_state == "running"

    def test_stopped_to_removing(self):
        sm = ContainerStateMachine()
        sm.transition_to("running")
        sm.transition_to("stopped")
        sm.transition_to("removing")
        assert sm.current_state == "removing"

    def test_removing_is_terminal(self):
        sm = ContainerStateMachine()
        sm.transition_to("running")
        sm.transition_to("stopped")
        sm.transition_to("removing")
        assert sm.is_terminal_state() is True

    def test_invalid_creating_to_stopped(self):
        sm = ContainerStateMachine()
        with pytest.raises(StateTransitionError):
            sm.transition_to("stopped")

    def test_error_to_creating_retry(self):
        sm = ContainerStateMachine()
        sm.transition_to("error")
        sm.transition_to("creating")
        assert sm.current_state == "creating"

    def test_paused_to_running(self):
        sm = ContainerStateMachine()
        sm.transition_to("running")
        sm.transition_to("paused")
        sm.transition_to("running")
        assert sm.current_state == "running"

    def test_container_transitions_config(self):
        assert "creating" in CONTAINER_TRANSITIONS
        assert "removing" in CONTAINER_TRANSITIONS
        assert CONTAINER_TRANSITIONS["removing"] == frozenset()


# ---------------------------------------------------------------------------
# AnalysisStateMachine
# ---------------------------------------------------------------------------


class TestAnalysisStateMachine:
    def test_default_initial_state(self):
        sm = AnalysisStateMachine()
        assert sm.current_state == "queued"

    def test_queued_to_processing(self):
        sm = AnalysisStateMachine()
        sm.transition_to("processing")
        assert sm.current_state == "processing"

    def test_processing_to_completed(self):
        sm = AnalysisStateMachine()
        sm.transition_to("processing")
        sm.transition_to("completed")
        assert sm.current_state == "completed"

    def test_completed_is_terminal(self):
        sm = AnalysisStateMachine()
        sm.transition_to("processing")
        sm.transition_to("completed")
        assert sm.is_terminal_state() is True

    def test_processing_to_failed(self):
        sm = AnalysisStateMachine()
        sm.transition_to("processing")
        sm.transition_to("failed")
        assert sm.current_state == "failed"

    def test_failed_to_queued_retry(self):
        sm = AnalysisStateMachine()
        sm.transition_to("processing")
        sm.transition_to("failed")
        sm.transition_to("queued")
        assert sm.current_state == "queued"

    def test_timeout_to_queued_retry(self):
        sm = AnalysisStateMachine()
        sm.transition_to("processing")
        sm.transition_to("timeout")
        sm.transition_to("queued")
        assert sm.current_state == "queued"

    def test_queued_to_cancelled(self):
        sm = AnalysisStateMachine()
        sm.transition_to("cancelled")
        assert sm.current_state == "cancelled"
        assert sm.is_terminal_state() is True

    def test_invalid_queued_to_completed(self):
        sm = AnalysisStateMachine()
        with pytest.raises(StateTransitionError):
            sm.transition_to("completed")

    def test_analysis_transitions_config(self):
        assert ANALYSIS_TRANSITIONS["completed"] == frozenset()
        assert "queued" in ANALYSIS_TRANSITIONS["failed"]


# ---------------------------------------------------------------------------
# ResponseStateMachine
# ---------------------------------------------------------------------------


class TestResponseStateMachine:
    def test_default_initial_state(self):
        sm = ResponseStateMachine()
        assert sm.current_state == "pending"

    def test_pending_to_success(self):
        sm = ResponseStateMachine()
        sm.transition_to("success")
        assert sm.current_state == "success"
        assert sm.is_terminal_state() is True

    def test_pending_to_error_and_retry(self):
        sm = ResponseStateMachine()
        sm.transition_to("error")
        sm.transition_to("pending")
        assert sm.current_state == "pending"

    def test_response_transitions_config(self):
        assert RESPONSE_TRANSITIONS["forbidden"] == frozenset()


# ---------------------------------------------------------------------------
# HealthStateMachine
# ---------------------------------------------------------------------------


class TestHealthStateMachine:
    def test_default_initial_state(self):
        sm = HealthStateMachine()
        assert sm.current_state == "unknown"

    def test_unknown_to_healthy(self):
        sm = HealthStateMachine()
        sm.transition_to("healthy")
        assert sm.current_state == "healthy"

    def test_healthy_to_degraded(self):
        sm = HealthStateMachine()
        sm.transition_to("healthy")
        sm.transition_to("degraded")
        assert sm.current_state == "degraded"

    def test_health_transitions_config(self):
        assert "maintenance" in HEALTH_TRANSITIONS["healthy"]
        assert "healthy" in HEALTH_TRANSITIONS["maintenance"]


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


class TestFactoryFunctions:
    def test_create_container_state_machine(self):
        sm = create_container_state_machine()
        assert isinstance(sm, ContainerStateMachine)
        assert sm.current_state == "creating"

    def test_create_container_state_machine_custom(self):
        sm = create_container_state_machine("running")
        assert sm.current_state == "running"

    def test_create_analysis_state_machine(self):
        sm = create_analysis_state_machine()
        assert isinstance(sm, AnalysisStateMachine)
        assert sm.current_state == "queued"

    def test_create_response_state_machine(self):
        sm = create_response_state_machine()
        assert isinstance(sm, ResponseStateMachine)
        assert sm.current_state == "pending"

    def test_create_health_state_machine(self):
        sm = create_health_state_machine()
        assert isinstance(sm, HealthStateMachine)
        assert sm.current_state == "unknown"

    def test_create_state_machine_container(self):
        sm = create_state_machine("container")
        assert isinstance(sm, ContainerStateMachine)

    def test_create_state_machine_analysis(self):
        sm = create_state_machine("analysis")
        assert isinstance(sm, AnalysisStateMachine)

    def test_create_state_machine_response(self):
        sm = create_state_machine("response")
        assert isinstance(sm, ResponseStateMachine)

    def test_create_state_machine_health(self):
        sm = create_state_machine("health")
        assert isinstance(sm, HealthStateMachine)

    def test_create_state_machine_with_initial_state(self):
        sm = create_state_machine("container", "running")
        assert sm.current_state == "running"

    def test_create_state_machine_unknown_type(self):
        with pytest.raises(ValueError, match="Unknown state machine type"):
            create_state_machine("invalid_type")
