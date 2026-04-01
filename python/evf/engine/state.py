# Copyright (C) 2026 Arun Venkataswamy
#
# This file is part of PushNav.
#
# PushNav is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PushNav is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PushNav. If not, see <https://www.gnu.org/licenses/>.

"""Engine state machine with validated transitions."""

import enum
import threading


class EngineState(enum.Enum):
    SETUP = "SETUP"
    SYNC = "SYNC"
    SYNC_CONFIRM = "SYNC_CONFIRM"
    CALIBRATE = "CALIBRATE"
    WARMING_UP = "WARMING_UP"
    TRACKING = "TRACKING"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"


# Allowed transitions: {from_state: {to_state, ...}}
_TRANSITIONS: dict[EngineState, set[EngineState]] = {
    EngineState.SETUP: {EngineState.SYNC, EngineState.RECONNECTING},
    EngineState.SYNC: {
        EngineState.SYNC_CONFIRM,
        EngineState.WARMING_UP,
        EngineState.SETUP,
        EngineState.RECONNECTING,
    },
    EngineState.SYNC_CONFIRM: {
        EngineState.CALIBRATE,
        EngineState.WARMING_UP,
        EngineState.SYNC,
        EngineState.SETUP,
        EngineState.RECONNECTING,
    },
    EngineState.CALIBRATE: {
        EngineState.WARMING_UP,
        EngineState.SETUP,
        EngineState.RECONNECTING,
    },
    EngineState.WARMING_UP: {
        EngineState.TRACKING,
        EngineState.SETUP,
        EngineState.RECONNECTING,
    },
    EngineState.TRACKING: {EngineState.SETUP, EngineState.RECONNECTING},
    EngineState.RECONNECTING: {EngineState.SETUP, EngineState.ERROR},
    EngineState.ERROR: {EngineState.SETUP},
}


class InvalidTransitionError(Exception):
    pass


class StateMachine:
    """Thread-safe engine state machine with validated transitions."""

    def __init__(self) -> None:
        self._state = EngineState.SETUP
        self._lock = threading.Lock()

    @property
    def state(self) -> EngineState:
        with self._lock:
            return self._state

    def transition(self, target: EngineState) -> None:
        """Transition to a new state. Raises InvalidTransitionError if not allowed."""
        with self._lock:
            allowed = _TRANSITIONS.get(self._state, set())
            if target not in allowed:
                raise InvalidTransitionError(
                    f"Cannot transition from {self._state.value} to {target.value}"
                )
            self._state = target

    @staticmethod
    def allowed_transitions(state: EngineState) -> set[EngineState]:
        """Return the set of states reachable from the given state."""
        return _TRANSITIONS.get(state, set()).copy()
