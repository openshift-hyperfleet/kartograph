"""Authentication bridge for Management presentation layer.

Re-exports the IAM dependency primitives required by route handlers.
Centralizing these imports into a single module means only this file
needs to be excluded from the IAM isolation architecture rule — all
other modules in management.presentation remain subject to the rule.
"""

from __future__ import annotations

from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user

__all__ = ["CurrentUser", "get_current_user"]
