import time

import pytest

from app.fetcher.robots import ROBOTS_AGENT, rules_for_answer
from app.fetcher.robots_txt import parse_robots

HOSTILE_WILDCARDS = 16
LONGEST_PATH_CHARS = 2000
HOSTILE_RULE_SECONDS = 1.0

RFC_SIMPLE_EXAMPLE = """User-Agent: *
Disallow: *.gif$
Disallow: /example/
Allow: /publications/

User-Agent: foobot
Disallow:/
Allow:/example/page.html
Allow:/example/allowed.gif

User-Agent: barbot
User-Agent: bazbot
Disallow: /example/page.html

User-Agent: quxbot

EOF
"""

RFC_LONGEST_MATCH_EXAMPLE = """User-Agent: foobot
Allow: /example/page/
Disallow: /example/page/disallowed.gif
"""


def allowed(text: str, agent: str, path: str) -> bool:
    return parse_robots(text).rules_for(agent).allows(path)


@pytest.mark.parametrize(
    ("agent", "path", "expected"),
    [
        ("foobot", "/example/page.html", True),
        ("foobot", "/example/allowed.gif", True),
        ("foobot", "/example/other.html", False),
        ("foobot", "/publications/report.html", False),
        ("barbot", "/example/page.html", False),
        ("bazbot", "/example/page.html", False),
        ("barbot", "/example/other.html", True),
        ("barbot", "/pictures/shawl.gif", True),
        ("quxbot", "/example/page.html", True),
        ("quxbot", "/pictures/shawl.gif", True),
        (ROBOTS_AGENT, "/publications/report.html", True),
        (ROBOTS_AGENT, "/example/other.html", False),
        (ROBOTS_AGENT, "/pictures/shawl.gif", False),
        (ROBOTS_AGENT, "/pictures/shawl.gif?size=2", True),
        (ROBOTS_AGENT, "/publications/shawl.gif", True),
    ],
)
def test_the_rfc_simple_example_section_5_1(agent: str, path: str, expected: bool) -> None:
    assert allowed(RFC_SIMPLE_EXAMPLE, agent, path) is expected


@pytest.mark.parametrize(
    ("path", "expected"),
    [("/example/page/disallowed.gif", False), ("/example/page/allowed.gif", True), ("/example/page/", True)],
)
def test_the_rfc_longest_match_example_section_5_2(path: str, expected: bool) -> None:
    assert allowed(RFC_LONGEST_MATCH_EXAMPLE, "foobot", path) is expected


def test_an_allow_line_after_a_shorter_disallow_now_wins_by_length() -> None:
    text = "User-agent: KalaVigyan\nDisallow: /crafts/\nAllow: /crafts/ajrakh/\n"
    assert allowed(text, ROBOTS_AGENT, "/crafts/ajrakh/indigo") is True
    assert allowed(text, ROBOTS_AGENT, "/crafts/bagh/") is False


def test_an_allow_and_a_disallow_of_the_same_length_allow() -> None:
    text = "User-agent: *\nDisallow: /page\nAllow: /page\n"
    assert allowed(text, ROBOTS_AGENT, "/page") is True


def test_groups_naming_the_agent_are_merged_and_the_star_group_is_not_used() -> None:
    text = (
        "User-agent: KalaVigyan\nDisallow: /drafts/\n\n"
        "User-agent: *\nDisallow: /\n\n"
        "User-agent: kalavigyan/2.0\nAllow: /drafts/public/\n"
    )
    assert allowed(text, ROBOTS_AGENT, "/drafts/x") is False
    assert allowed(text, ROBOTS_AGENT, "/drafts/public/y") is True
    assert allowed(text, ROBOTS_AGENT, "/crafts") is True


def test_a_file_with_no_group_for_the_agent_and_no_star_group_allows_everything() -> None:
    assert allowed("User-agent: foobot\nDisallow: /\n", ROBOTS_AGENT, "/anything") is True


@pytest.mark.parametrize(
    ("rule", "path"),
    [
        ("/foo/bar?baz=quz", "/foo/bar?baz=quz"),
        ("/foo/bar?baz=https://foo.bar", "/foo/bar?baz=https%3A%2F%2Ffoo.bar"),
        ("/foo/bar/\u30c4", "/foo/bar/%E3%83%84"),
        ("/foo/bar/%E3%83%84", "/foo/bar/%e3%83%84"),
        ("/foo/bar/baz", "/foo/bar/%62%61%7A"),
    ],
)
def test_paths_are_compared_after_the_rfc_s_percent_encoding(rule: str, path: str) -> None:
    text = f"User-agent: *\nDisallow: {rule}\n"
    assert allowed(text, ROBOTS_AGENT, path) is False
    assert allowed(text, ROBOTS_AGENT, "/foo/qux") is True


def test_an_encoded_star_is_a_literal_star_not_a_wildcard() -> None:
    text = "User-agent: *\nDisallow: /path/file-with-a-%2A.html\n"
    assert allowed(text, ROBOTS_AGENT, "/path/file-with-a-*.html") is False
    assert allowed(text, ROBOTS_AGENT, "/path/file-with-a-b.html") is True


def test_the_wildcard_spans_slashes_and_the_end_anchor_ends_the_path() -> None:
    text = "User-agent: *\nDisallow: /this/*/exactly$\n"
    assert allowed(text, ROBOTS_AGENT, "/this/a/b/exactly") is False
    assert allowed(text, ROBOTS_AGENT, "/this/a/exactly/more") is True


@pytest.mark.parametrize(
    ("rule", "path", "expected"),
    [
        ("/a*a$", "/a", True),
        ("/a*a$", "/aa", False),
        ("/a*a$", "/ab", True),
        ("/a*a$", "/aba", False),
        ("/a*ab$", "/ab", True),
        ("/a*ab$", "/aab", False),
        ("/x*y*z", "/xzy", True),
        ("/x*y*z", "/xyz", False),
        ("/x*y*z", "/xyyz/more", False),
        ("/x*y$", "/xyxy", False),
        ("*", "/anything", False),
        ("/exact$", "/exact", False),
        ("/exact$", "/exact/more", True),
    ],
)
def test_each_wildcard_spans_any_run_and_the_pieces_keep_their_order(
    rule: str, path: str, expected: bool
) -> None:
    assert allowed(f"User-agent: *\nDisallow: {rule}\n", ROBOTS_AGENT, path) is expected


def test_a_hostile_run_of_wildcards_is_matched_in_time_linear_in_the_path() -> None:
    text = "User-agent: *\nDisallow: /" + "*a" * HOSTILE_WILDCARDS + "*!\n"
    path = "/" + "a" * LONGEST_PATH_CHARS
    started = time.perf_counter()
    verdicts = (allowed(text, ROBOTS_AGENT, path), allowed(text, ROBOTS_AGENT, path + "!"))
    assert time.perf_counter() - started < HOSTILE_RULE_SECONDS
    assert verdicts == (True, False)


def test_comments_and_other_lines_are_ignored_and_a_pattern_without_its_slash_keeps_its_intent() -> None:
    text = "# crawl rules\nUser-agent: * # everyone\nSitemap: https://crafts.example.org/map.xml\nDisallow: private/\n"
    assert allowed(text, ROBOTS_AGENT, "/private/x") is False
    assert allowed(text, ROBOTS_AGENT, "/public/x") is True


@pytest.mark.parametrize(
    ("status", "allowed_path"),
    [(404, True), (410, True), (401, True), (429, False), (500, False), (503, False)],
)
def test_robots_answers_without_a_file_follow_rfc_9309(status: int, allowed_path: bool) -> None:
    assert rules_for_answer(status, b"").allows("/") is allowed_path


def test_a_served_file_is_read_for_our_agent() -> None:
    rules = rules_for_answer(
        200, b"User-agent: *\nDisallow: /private/\n\nUser-agent: KalaVigyan\nDisallow: /drafts/\n"
    )
    assert (rules.allows("/ajrakh"), rules.allows("/drafts/x"), rules.allows("/private/x")) == (
        True,
        False,
        True,
    )
