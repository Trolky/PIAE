from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    CUSTOMER = "CUSTOMER"
    TRANSLATOR = "TRANSLATOR"
    ADMINISTRATOR = "ADMINISTRATOR"


class ProjectState(str, Enum):
    CREATED = "CREATED"
    ASSIGNED = "ASSIGNED"
    COMPLETED = "COMPLETED"
    APPROVED = "APPROVED"
    CLOSED = "CLOSED"

