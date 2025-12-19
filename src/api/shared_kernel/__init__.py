"""Shared Kernel module.

This module contains foundational components that are explicitly shared across
multiple bounded contexts. Changes to this module affect multiple contexts and
should be carefully coordinated.

Following Domain-Driven Design principles, the Shared Kernel is a small,
carefully managed set of components that contexts agree to depend on.
"""
