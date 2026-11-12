"""Normalization of contact fields (SPEC.md, "Email normalization" / "Phone normalization")."""

GMAIL_DOMAINS = {"gmail.com", "googlemail.com"}
PLUS_DOMAINS = {"outlook.com", "hotmail.com", "fastmail.com"}
DIGITS = "0123456789"


def normalize_email(raw):
    if raw is None:
        return None
    s = raw.strip().lower()
    if s.count("@") != 1:
        return None
    local, domain = s.split("@")
    if not local or not domain:
        return None
    if domain == "googlemail.com":
        domain = "gmail.com"
    if domain == "gmail.com":
        local = local.split("+", 1)[0].replace(".", "")
    elif domain in PLUS_DOMAINS:
        local = local.split("+", 1)[0]
    if not local:
        return None
    return local + "@" + domain


def normalize_phone(raw):
    if raw is None:
        return None
    digits = "".join(c for c in raw if c in DIGITS)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return digits
    return None


def normalize_tag(tag):
    return tag.strip().lower()
