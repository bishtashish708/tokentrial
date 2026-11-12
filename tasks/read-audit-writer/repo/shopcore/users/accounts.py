"""User accounts."""

from dataclasses import dataclass


@dataclass
class Account:
    id: str
    email: str
    tier: str = "standard"


ACCOUNTS: dict[str, Account] = {}


def register(user_id: str, email: str) -> Account:
    acct = Account(user_id, email)
    ACCOUNTS[user_id] = acct
    return acct
