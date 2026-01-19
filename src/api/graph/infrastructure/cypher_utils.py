"""Utilities for safe Cypher query construction.

Provides shared utilities for generating secure Cypher queries
when working with Apache AGE.
"""

from __future__ import annotations

import secrets
import string


def generate_cypher_nonce() -> str:
    """Generate a random nonce for Cypher dollar-quoting.

    Returns a 64-character random string for use as a unique delimiter
    in Cypher queries. This prevents injection attacks via $$ breakout.

    The nonce is used to create unique dollar-quote tags like ${nonce}$
    instead of the default $$, making it impossible for attackers to
    craft malicious input that breaks out of the Cypher context.

    Returns:
        64-character random alphabetic string
    """
    return "".join(secrets.choice(string.ascii_letters) for _ in range(64))
