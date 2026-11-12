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

    Union-find over positions: every record is unioned with the first record that had the
    same normalized email (or phone). The root of a set is always its smallest position.
    """
    n = len(records)
    parent = list(range(n))

    def find(x):
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            if ra < rb:
                parent[rb] = ra
            else:
                parent[ra] = rb

    first_email = {}
    first_phone = {}
    for i, rec in enumerate(records):
        e = normalize_email(rec["email"])
        if e is not None:
            j = first_email.setdefault(e, i)
            if j != i:
                union(i, j)
        p = normalize_phone(rec["phone"])
        if p is not None:
            j = first_phone.setdefault(p, i)
            if j != i:
                union(i, j)

    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    # roots are smallest positions, and dict order follows first insertion (ascending i)
    return list(groups.values())


def dedupe(records):
    """Merge duplicate contacts. See SPEC.md for the exact semantics."""
    return [merge_cluster(records, members) for members in find_clusters(records)]
