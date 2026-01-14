"""IAM-specific outbox infrastructure.

Contains the translator and serializer implementations for IAM domain events.
These are registered with the composite handlers at application startup.
"""

from iam.infrastructure.outbox.serializer import IAMEventSerializer
from iam.infrastructure.outbox.translator import IAMEventTranslator

__all__ = ["IAMEventSerializer", "IAMEventTranslator"]
