# contactdedupe specification

`contactdedupe.dedupe(records)` takes a list of contact records and returns a new list of
merged contact records. The input list and its records are never modified.

## Input records

Each input record is a dict with exactly these keys:

| key       | type                  |
|-----------|-----------------------|
| `id`      | str (unique)          |
| `name`    | str                   |
| `email`   | str or None           |
| `phone`   | str or None           |
| `updated` | int (unix timestamp)  |
| `tags`    | list of str           |

The *position* of a record is its index in the input list.

## Email normalization

`normalize_email(raw)` returns a str or None:

1. If `raw` is None, return None.
2. `s = raw.strip().lower()`.
3. If `s` does not contain exactly one `@`, return None. Split into `local` and `domain`
   at the `@`. If either is empty, return None.
4. If `domain == "googlemail.com"`, set `domain = "gmail.com"`.
5. If `domain == "gmail.com"`: cut `local` at the first `+` (keep only the part before
   it, if there is a `+`), then remove every `.` from `local`.
   Otherwise, if `domain` is one of `outlook.com`, `hotmail.com`, `fastmail.com`: cut
   `local` at the first `+` (dots are kept).
   Any other domain: `local` is unchanged.
6. If `local` is now empty, return None.
7. Return `local + "@" + domain`.

## Phone normalization

`normalize_phone(raw)` returns a str or None:

1. If `raw` is None, return None.
2. Keep only the ASCII digits `0`-`9` of `raw`, in order.
3. If the result has 11 digits and starts with `1`, drop that leading `1`.
4. If the result has exactly 10 digits, return it; otherwise return None.

## Duplicates

Two records are *directly linked* if both have a non-None normalized email and the
normalized emails are equal, **or** both have a non-None normalized phone and the
normalized phones are equal. Duplicates are transitive: a *cluster* is a connected
component of the "directly linked" relation (a record with no links is a cluster of one).

## Merged records

For each cluster, rank its members by `updated` descending, ties broken by position
ascending. The first-ranked member is the *winner*. The merged record is a new dict with
exactly these keys:

| key          | value |
|--------------|-------|
| `id`         | the winner's `id` |
| `name`       | `name.strip()` of the first-ranked member whose `name.strip()` is not empty; `""` if there is none |
| `email`      | the normalized email of the first-ranked member whose normalized email is not None; None if there is none |
| `phone`      | the normalized phone of the first-ranked member whose normalized phone is not None; None if there is none |
| `updated`    | the winner's `updated` |
| `tags`       | the set of `t.strip().lower()` over all tags of all members, excluding empty strings, as a sorted list (plain `str` ordering) |
| `merged_ids` | the `id`s of all members except the winner, in position order (`[]` for a cluster of one) |

## Output order

The output contains one merged record per cluster, ordered by the smallest position among
each cluster's members.
