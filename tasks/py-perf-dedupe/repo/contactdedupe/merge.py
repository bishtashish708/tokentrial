"""Building one merged record from a cluster (SPEC.md, "Merged records")."""

from contactdedupe.normalize import normalize_email, normalize_phone, normalize_tag


def rank(records, members):
    """Cluster members (positions) ordered winner-first."""
    return sorted(members, key=lambda p: (-records[p]["updated"], p))


def _first(values):
    for v in values:
        if v is not None:
            return v
    return None


def merge_cluster(records, members):
    """`members` is the sorted list of positions in one cluster."""
    ranked = rank(records, members)
    winner = records[ranked[0]]
    names = [records[p]["name"].strip() for p in ranked]
    tags = set()
    for p in members:
        for t in records[p]["tags"]:
            t = normalize_tag(t)
            if t:
                tags.add(t)
    return {
        "id": winner["id"],
        "name": _first(n if n else None for n in names) or "",
        "email": _first(normalize_email(records[p]["email"]) for p in ranked),
        "phone": _first(normalize_phone(records[p]["phone"]) for p in ranked),
        "updated": winner["updated"],
        "tags": sorted(tags),
        "merged_ids": [records[p]["id"] for p in members if p != ranked[0]],
    }
