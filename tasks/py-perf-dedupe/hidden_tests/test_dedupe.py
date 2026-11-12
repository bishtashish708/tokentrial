import copy
import unittest

from contactdedupe import dedupe


def rec(id, name="", email=None, phone=None, updated=0, tags=()):
    return {"id": id, "name": name, "email": email, "phone": phone, "updated": updated,
            "tags": list(tags)}


class TestDedupe(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(dedupe([]), [])

    def test_singletons_keep_order(self):
        records = [rec("b", "Bo", "bo@example.com"), rec("a", "Al", phone="555 000 1111")]
        self.assertEqual(dedupe(records), [
            {"id": "b", "name": "Bo", "email": "bo@example.com", "phone": None, "updated": 0,
             "tags": [], "merged_ids": []},
            {"id": "a", "name": "Al", "email": None, "phone": "5550001111", "updated": 0,
             "tags": [], "merged_ids": []},
        ])

    def test_merge_by_gmail_rules(self):
        records = [
            rec("1", "Ann", "ann.lee@gmail.com", updated=10, tags=["VIP"]),
            rec("2", " Ann Lee ", "AnnLee+shop@googlemail.com", updated=20, tags=[" vip ", "Shop"]),
        ]
        self.assertEqual(dedupe(records), [
            {"id": "2", "name": "Ann Lee", "email": "annlee@gmail.com", "phone": None,
             "updated": 20, "tags": ["shop", "vip"], "merged_ids": ["1"]},
        ])

    def test_transitive_and_order(self):
        records = [
            rec("x", "X", "x@example.com"),
            rec("a", "", "a@example.com", updated=5),
            rec("b", "Bee", "b@example.com", "555-222-3333", updated=5),
            rec("c", "", "A@Example.com", "+1 (555) 222-3333", updated=7),
        ]
        # a~c by email, b~c by phone -> {a, b, c}; c wins (newest) but has no name
        self.assertEqual(dedupe(records), [
            {"id": "x", "name": "X", "email": "x@example.com", "phone": None, "updated": 0,
             "tags": [], "merged_ids": []},
            {"id": "c", "name": "Bee", "email": "a@example.com", "phone": "5552223333",
             "updated": 7, "tags": [], "merged_ids": ["a", "b"]},
        ])

    def test_tie_goes_to_earlier_position(self):
        records = [rec("p", "P", phone="5551112222", updated=3),
                   rec("q", "Q", phone="555.111.2222", updated=3)]
        self.assertEqual(dedupe(records)[0]["id"], "p")
        self.assertEqual(dedupe(records)[0]["merged_ids"], ["q"])

    def test_plus_not_stripped_for_other_domains(self):
        records = [rec("1", email="a+b@example.com"), rec("2", email="a@example.com")]
        self.assertEqual(len(dedupe(records)), 2)

    def test_input_not_modified(self):
        records = [rec("1", " N ", "N@gmail.com", tags=["T"]), rec("2", email="n@gmail.com")]
        before = copy.deepcopy(records)
        dedupe(records)
        self.assertEqual(records, before)


if __name__ == "__main__":
    unittest.main()
