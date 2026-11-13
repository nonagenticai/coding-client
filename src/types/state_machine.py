"""Type-safe state machine for container and execution lifecycle management.

This module provides a generic state machine implementation with type safety for managing
the lifecycle of containers, analyses, and other stateful components in the system.

The state machine enforces valid transitions between states and maintains a history of
all state changes for auditing and debugging purposes.

Usage:
    from ..types.state_machine import ContainerStateMachine, AnalysisStateMachine

    # Create a container state machine
    container_sm = ContainerStateMachine()

    # Check if transition is valid
    if container_sm.can_transition_to("running"):
        container_sm.transition_to("running")
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, TypeVar

from .core_types import AnalysisState, ContainerState, HealthState, ResponseState

logger = logging.getLogger(__name__)

StateType = TypeVar("StateType", bound=str)


@dataclass(frozen=True)
class StateTransition[StateType: str]:
    """Type-safe state transition record.

    Represents a single state transition with metadata for auditing and debugging.
    """

    from_state: StateType
    to_state: StateType
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    trigger: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.from_state} -> {self.to_state}"


@dataclass
class StateTransitionRule[StateType: str]:
    """Rule for state transition validation.

    Defines conditions and actions for valid state transitions.
    """

    from_state: StateType
    to_state: StateType
    condition: Callable[[Any], bool] | None = None
    action: Callable[[Any], None] | None = None
    description: str | None = None


class StateTransitionError(Exception):
    """Exception raised when an invalid state transition is attempted."""

    def __init__(self, from_state: str, to_state: str, message: str = ""):
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Invalid transition from {from_state} to {to_state}: {message}")


class StateMachine[StateType: str]:
    """Generic type-safe state machine.

    Provides a framework for managing state transitions with validation,
    history tracking, and extensible transition rules.
    """

    def __init__(
        self,
        initial_state: StateType,
        valid_transitions: dict[StateType, frozenset[StateType]],
        transition_rules: list[StateTransitionRule[StateType]] | None = None,
        max_history: int = 100,
    ):
        """Initialize the state machine.

        Args:
            initial_state: Starting state for the machine
            valid_transitions: Map of valid state transitions
            transition_rules: Optional list of transition rules with conditions
            max_history: Maximum number of transitions to keep in history
        """
        self._current_state = initial_state
        self._valid_transitions = valid_transitions
        self._transition_rules = transition_rules or []
        self._max_history = max_history
        self._transition_history: list[StateTransition[StateType]] = []
        self._state_change_callbacks: dict[
            StateType, list[Callable[[StateType, StateType], None]]
        ] = {}

        logger.debug(f"State machine initialized with state: {initial_state}")

    @property
    def current_state(self) -> StateType:
        """Get the current state."""
        return self._current_state

    @property
    def transition_history(self) -> list[StateTransition[StateType]]:
        """Get the transition history."""
        return self._transition_history.copy()

    def can_transition_to(self, target_state: StateType) -> bool:
        """Check if transition to target state is valid.

        Args:
            target_state: State to transition to

        Returns:
            True if transition is valid, False otherwise
        """
        # Check basic transition validity
        if target_state not in self._valid_transitions.get(self._current_state, frozenset()):
            return False

        # Check transition rules
        for rule in self._transition_rules:
            if rule.from_state == self._current_state and rule.to_state == target_state:
                if rule.condition and not rule.condition(self):
                    return False

        return True

    def transition_to(
        self,
        target_state: StateType,
        trigger: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Attempt to transition to target state.

        Args:
            target_state: State to transition to
            trigger: Optional trigger description
            metadata: Optional metadata for the transition

        Returns:
            True if transition successful, False otherwise

        Raises:
            StateTransitionError: If transition is invalid
        """
        if not self.can_transition_to(target_state):
            raise StateTransitionError(
                self._current_state,
                target_state,
                f"No valid transition from {self._current_state} to {target_state}",
            )

        previous_state = self._current_state

        # Execute transition actions
        for rule in self._transition_rules:
            if rule.from_state == previous_state and rule.to_state == target_state:
                if rule.action:
                    try:
                        rule.action(self)
                    except Exception as e:
                        logger.error(f"Transition action failed: {e}")
                        return False

        # Update state
        self._current_state = target_state

        # Record transition
        transition = StateTransition(
            from_state=previous_state,
            to_state=target_state,
            trigger=trigger,
            metadata=metadata or {},
        )
        self._transition_history.append(transition)

        # Trim history if needed
        if len(self._transition_history) > self._max_history:
            self._transition_history = self._transition_history[-self._max_history :]

        # Execute callbacks
        self._execute_callbacks(previous_state, target_state)

        logger.debug(f"State transition: {previous_state} -> {target_state}")
        return True

    def force_transition_to(self, target_state: StateType, reason: str = "Forced") -> None:
        """Force a state transition without validation.

        Use with caution - this bypasses all validation rules.

        Args:
            target_state: State to transition to
            reason: Reason for forcing the transition
        """
        logger.warning(
            f"Forced state transition from {self._current_state} to {target_state}: {reason}"
        )

        previous_state = self._current_state
        self._current_state = target_state

        # Record forced transition
        transition = StateTransition(
            from_state=previous_state,
            to_state=target_state,
            trigger=f"FORCED: {reason}",
            metadata={"forced": True},
        )
        self._transition_history.append(transition)

        # Execute callbacks
        self._execute_callbacks(previous_state, target_state)

    def add_state_change_callback(
        self, state: StateType, callback: Callable[[StateType, StateType], None]
    ) -> None:
        """Add a callback to be executed when transitioning to a specific state.

        Args:
            state: State to trigger callback on
            callback: Function to call with (from_state, to_state) arguments
        """
        if state not in self._state_change_callbacks:
            self._state_change_callbacks[state] = []
        self._state_change_callbacks[state].append(callback)

    def _execute_callbacks(self, from_state: StateType, to_state: StateType) -> None:
        """Execute callbacks for state transitions."""
        for callback in self._state_change_callbacks.get(to_state, []):
            try:
                callback(from_state, to_state)
            except Exception as e:
                logger.error(f"State change callback failed: {e}")

    def get_valid_transitions(self) -> frozenset[StateType]:
        """Get all valid transitions from current state."""
        return self._valid_transitions.get(self._current_state, frozenset())

    def is_terminal_state(self) -> bool:
        """Check if current state is terminal (no outgoing transitions)."""
        return len(self.get_valid_transitions()) == 0

    def get_state_summary(self) -> dict[str, Any]:
        """Get a summary of the current state machine state."""
        return {
            "current_state": self._current_state,
            "valid_transitions": list(self.get_valid_transitions()),
            "is_terminal": self.is_terminal_state(),
            "transition_count": len(self._transition_history),
            "last_transition": (self._transition_history[-1] if self._transition_history else None),
        }


# Container State Machine Configuration
CONTAINER_TRANSITIONS: dict[ContainerState, frozenset[ContainerState]] = {
    "creating": frozenset(["running", "error"]),
    "running": frozenset(["stopped", "error", "paused"]),
    "stopped": frozenset(["running", "removing"]),
    "error": frozenset(["removing", "creating"]),
    "paused": frozenset(["running", "stopped"]),
    "removing": frozenset(),  # Terminal state
    "restarting": frozenset(["running", "error"]),
}

# Analysis State Machine Configuration
ANALYSIS_TRANSITIONS: dict[AnalysisState, frozenset[AnalysisState]] = {
    "queued": frozenset(["processing", "cancelled"]),
    "processing": frozenset(["completed", "failed", "cancelled", "timeout"]),
    "completed": frozenset(),  # Terminal state
    "failed": frozenset(["queued"]),  # Can retry
    "cancelled": frozenset(),  # Terminal state
    "timeout": frozenset(["queued"]),  # Can retry
}

# Response State Machine Configuration
RESPONSE_TRANSITIONS: dict[ResponseState, frozenset[ResponseState]] = {
    "pending": frozenset(["success", "error", "timeout", "unauthorized", "forbidden"]),
    "success": frozenset(),  # Terminal state
    "error": frozenset(["pending"]),  # Can retry
    "timeout": frozenset(["pending"]),  # Can retry
    "unauthorized": frozenset(["pending"]),  # Can retry after authentication
    "forbidden": frozenset(),  # Terminal state - requires permission changes
}

# Health State Machine Configuration
HEALTH_TRANSITIONS: dict[HealthState, frozenset[HealthState]] = {
    "healthy": frozenset(["degraded", "unhealthy", "unknown", "critical", "maintenance"]),
    "degraded": frozenset(["healthy", "unhealthy", "unknown", "critical"]),
    "unhealthy": frozenset(["healthy", "degraded", "unknown", "critical"]),
    "unknown": frozenset(["healthy", "degraded", "unhealthy", "critical"]),
    "critical": frozenset(["healthy", "degraded", "unhealthy", "unknown", "maintenance"]),
    "maintenance": frozenset(
        ["healthy", "degraded", "unknown"]
    ),  # Usually returns to good states after maintenance
}


class ContainerStateMachine(StateMachine[ContainerState]):
    """Type-safe container state machine.

    Manages the lifecycle of Docker containers with proper state validation.
    """

    def __init__(self, initial_state: ContainerState = "creating"):
        super().__init__(initial_state, CONTAINER_TRANSITIONS)

        # Add container-specific transition rules
        self._add_container_rules()

    def _add_container_rules(self) -> None:
        """Add container-specific transition rules."""

        # Example: Only allow removing if container is stopped or error
        def can_remove(sm: Any) -> bool:
            return sm.current_state in ["stopped", "error"]

        remove_rule: StateTransitionRule[ContainerState] = StateTransitionRule(
            from_state="stopped",
            to_state="removing",
            condition=can_remove,
            description="Can only remove stopped or error containers",
        )

        self._transition_rules.append(remove_rule)


class AnalysisStateMachine(StateMachine[AnalysisState]):
    """Type-safe analysis state machine.

    Manages the lifecycle of code analysis operations.
    """

    def __init__(self, initial_state: AnalysisState = "queued"):
        super().__init__(initial_state, ANALYSIS_TRANSITIONS)

        # Add analysis-specific transition rules
        self._add_analysis_rules()

    def _add_analysis_rules(self) -> None:
        """Add analysis-specific transition rules."""

        # Example: Track processing start time
        def start_processing(sm: Any) -> None:
            if hasattr(sm, "_processing_start_time"):
                sm._processing_start_time = datetime.now(UTC)

        processing_rule: StateTransitionRule[AnalysisState] = StateTransitionRule(
            from_state="queued",
            to_state="processing",
            action=start_processing,
            description="Record processing start time",
        )

        self._transition_rules.append(processing_rule)


class ResponseStateMachine(StateMachine[ResponseState]):
    """Type-safe response state machine.

    Manages the lifecycle of API responses and async operations.
    """

    def __init__(self, initial_state: ResponseState = "pending"):
        super().__init__(initial_state, RESPONSE_TRANSITIONS)


class HealthStateMachine(StateMachine[HealthState]):
    """Type-safe health state machine.

    Manages the health status of system components.
    """

    def __init__(self, initial_state: HealthState = "unknown"):
        super().__init__(initial_state, HEALTH_TRANSITIONS)


# Utility functions for state machine management
def create_container_state_machine(
    initial_state: ContainerState = "creating",
) -> ContainerStateMachine:
    """Create a new container state machine."""
    return ContainerStateMachine(initial_state)


def create_analysis_state_machine(
    initial_state: AnalysisState = "queued",
) -> AnalysisStateMachine:
    """Create a new analysis state machine."""
    return AnalysisStateMachine(initial_state)


def create_response_state_machine(
    initial_state: ResponseState = "pending",
) -> ResponseStateMachine:
    """Create a new response state machine."""
    return ResponseStateMachine(initial_state)


def create_health_state_machine(
    initial_state: HealthState = "unknown",
) -> HealthStateMachine:
    """Create a new health state machine."""
    return HealthStateMachine(initial_state)


# State machine factory
def create_state_machine(state_type: str, initial_state: str | None = None) -> StateMachine:
    """Factory function to create state machines based on type.

    Args:
        state_type: Type of state machine ('container', 'analysis', 'response', 'health')
        initial_state: Optional initial state

    Returns:
        Appropriate state machine instance

    Raises:
        ValueError: If state_type is not recognized
    """
    factories = {
        "container": lambda s: create_container_state_machine(s or "creating"),
        "analysis": lambda s: create_analysis_state_machine(s or "queued"),
        "response": lambda s: create_response_state_machine(s or "pending"),
        "health": lambda s: create_health_state_machine(s or "unknown"),
    }

    if state_type not in factories:
        raise ValueError(f"Unknown state machine type: {state_type}")

    return factories[state_type](initial_state)
