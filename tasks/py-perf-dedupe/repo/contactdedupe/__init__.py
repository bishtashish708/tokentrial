"""Contact deduplication. See SPEC.md."""

from contactdedupe.dedupe import dedupe
from contactdedupe.normalize import normalize_email, normalize_phone

__all__ = ["dedupe", "normalize_email", "normalize_phone"]
