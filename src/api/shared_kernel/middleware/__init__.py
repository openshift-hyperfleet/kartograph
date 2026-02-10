"""Shared middleware for cross-cutting concerns.

This module contains FastAPI dependencies and middleware that are shared
across bounded contexts. The tenant context dependency is the primary
component, resolving tenant context from request headers.
"""
