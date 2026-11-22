from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

__all__ = [
    "ALLOW_ALL",
    "DISALLOW_ALL",
    "RobotsGroup",
    "RobotsRule",
    "RobotsRules",
    "RobotsTxt",
    "canonical_path",
    "parse_robots",
]

ANY_AGENT = "*"
WILDCARD = "*"
END_ANCHOR = "$"
PATH_START = "/"
COMMENT = "#"
AGENT_KEY = "user-agent"
RULE_KEYS = frozenset({"allow", "disallow"})
BYTE_ORDER_MARK = "\ufeff"
AGENT_TOKEN = re.compile(r"[A-Za-z_-]+")
ESCAPE = re.compile(r"%([0-9A-Fa-f]{2})|[^\x00-\x7f]")
PRINTABLE_ASCII = range(0x21, 0x7F)


@dataclass(frozen=True)
class RobotsRule:
    allow: bool
    pattern: str
    matcher: re.Pattern[str]

    @classmethod
    def of(cls, value: str, *, allow: bool) -> RobotsRule:
        anchored = value.endswith(END_ANCHOR)
        body = value.removesuffix(END_ANCHOR) if anchored else value
        if not body.startswith((PATH_START, WILDCARD)):
            body = PATH_START + body
        pieces = [canonical_path(piece) for piece in body.split(WILDCARD)]
        expression = ".*".join(re.escape(piece) for piece in pieces) + (r"\Z" if anchored else "")
        pattern = WILDCARD.join(pieces) + (END_ANCHOR if anchored else "")
        return cls(allow=allow, pattern=pattern, matcher=re.compile(expression, re.DOTALL))

    def matches(self, path: str) -> bool:
        return self.matcher.match(path) is not None


@dataclass(frozen=True)
class RobotsRules:
    rules: tuple[RobotsRule, ...] = ()

    def allows(self, path: str) -> bool:
        key = canonical_path(path)
        best: RobotsRule | None = None
        for rule in self.rules:
            if rule.matches(key) and (best is None or _outranks(rule, best)):
                best = rule
        return best is None or best.allow


@dataclass(frozen=True)
class RobotsGroup:
    agents: tuple[str, ...]
    rules: tuple[RobotsRule, ...]


@dataclass(frozen=True)
class RobotsTxt:
    groups: tuple[RobotsGroup, ...]

    def rules_for(self, product_token: str) -> RobotsRules:
        for agent in (product_token.casefold(), ANY_AGENT):
            matching = [group for group in self.groups if agent in group.agents]
            if matching:
                return RobotsRules(tuple(rule for group in matching for rule in group.rules))
        return ALLOW_ALL


def parse_robots(text: str) -> RobotsTxt:
    groups: list[tuple[list[str], list[RobotsRule]]] = []
    agents_open = False
    for key, value in _records(text.removeprefix(BYTE_ORDER_MARK)):
        if key == AGENT_KEY:
            if not agents_open:
                groups.append(([], []))
                agents_open = True
            groups[-1][0].append(_agent(value))
        elif key in RULE_KEYS and groups:
            agents_open = False
            if value:
                groups[-1][1].append(RobotsRule.of(value, allow=key == "allow"))
    return RobotsTxt(tuple(RobotsGroup(tuple(agents), tuple(rules)) for agents, rules in groups))


def canonical_path(text: str) -> str:
    return ESCAPE.sub(_canonical_escape, text)


def _canonical_escape(found: re.Match[str]) -> str:
    hex_digits = found.group(1)
    if hex_digits is None:
        return "".join(f"%{byte:02X}" for byte in found.group(0).encode("utf-8", "replace"))
    byte = int(hex_digits, 16)
    return chr(byte) if byte in PRINTABLE_ASCII else f"%{hex_digits.upper()}"


def _outranks(rule: RobotsRule, best: RobotsRule) -> bool:
    return (len(rule.pattern), rule.allow) > (len(best.pattern), best.allow)


def _records(text: str) -> Iterator[tuple[str, str]]:
    for line in text.splitlines():
        key, separator, value = line.split(COMMENT, 1)[0].partition(":")
        if separator:
            yield key.strip().casefold(), value.strip()


def _agent(value: str) -> str:
    if value.startswith(ANY_AGENT):
        return ANY_AGENT
    token = AGENT_TOKEN.match(value)
    return token.group(0).casefold() if token else ""


ALLOW_ALL = RobotsRules()
DISALLOW_ALL = RobotsRules((RobotsRule.of(PATH_START, allow=False),))
