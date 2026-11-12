"""Duplicate detection and merging (SPEC.md)."""

from contactdedupe.merge import merge_cluster
from contactdedupe.normalize import normalize_email, normalize_phone


def same_person(a, b):
    """True if two records are directly linked (shared email or shared phone)."""
    ea = normalize_email(a["email"])
    eb = normalize_email(b["email"])
    if ea is not None and ea == eb:
        return True
    pa = normalize_phone(a["phone"])
    pb = normalize_phone(b["phone"])
    if pa is not None and pa == pb:
        return True
    return False


def find_clusters(records):
    """Group record positions into clusters of duplicates.

    Returns a list of clusters, each a sorted list of positions; clusters are ordered by
    their smallest position.
    """
    clusters = []
    for i, rec in enumerate(records):
        hits = []
        for ci, members in enumerate(clusters):
            for j in members:
                if same_person(records[j], rec):
                    hits.append(ci)
                    break
        if not hits:
            clusters.append([i])
            continue
        merged = [i]
        for ci in hits:
            merged.extend(clusters[ci])
        merged.sort()
        # clusters is ordered by smallest member, so hits[0] keeps the right slot
        clusters[hits[0]] = merged
        for ci in reversed(hits[1:]):
            del clusters[ci]
    return clusters


def dedupe(records):
    """Merge duplicate contacts. See SPEC.md for the exact semantics."""
    return [merge_cluster(records, members) for members in find_clusters(records)]
