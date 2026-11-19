from __future__ import annotations

from dataclasses import dataclass
from email.utils import parseaddr

from app.models import MailRule
from app.services.mail_parser import ParsedMessage


@dataclass(frozen=True)
class FilterDecision:
    accepted: bool
    reason: str | None = None


def sender_domain(sender: str) -> str:
    _, address = parseaddr(sender)
    if "@" not in address:
        return ""
    return address.rsplit("@", 1)[1].lower()


def _matches(rule: MailRule, parsed: ParsedMessage) -> bool:
    value = rule.value.strip().lower()
    if not value:
        return False

    if rule.kind == "domain":
        domain = sender_domain(parsed.sender)
        return bool(domain) and (domain == value or domain.endswith(f".{value}"))

    if rule.kind == "keyword":
        haystack = " ".join(
            [
                parsed.subject,
                parsed.body_text,
                " ".join(attachment.filename for attachment in parsed.attachments),
            ]
        ).lower()
        return value in haystack

    if rule.kind == "mime":
        if value.endswith("/*"):
            prefix = value[:-1]
            return any(attachment.mime.startswith(prefix) for attachment in parsed.attachments)
        return any(attachment.mime == value for attachment in parsed.attachments)

    return False


def evaluate_rules(parsed: ParsedMessage, rules: list[MailRule]) -> FilterDecision:
    enabled = [rule for rule in rules if rule.enabled]
    deny_rules = [rule for rule in enabled if rule.action == "deny"]
    allow_rules = [rule for rule in enabled if rule.action == "allow"]

    for rule in deny_rules:
        if _matches(rule, parsed):
            return FilterDecision(False, f"denied_by_{rule.kind}")

    if allow_rules and not any(_matches(rule, parsed) for rule in allow_rules):
        return FilterDecision(False, "no_allow_rule_matched")

    return FilterDecision(True)
