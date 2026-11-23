from __future__ import annotations

from pathlib import PurePosixPath

import pytest

from hygiene.register import REGISTER_FILE, RegisterError, count_entries, register_entries

REGISTER = """# Technical debt register

Intro with a ### in the middle of a line.

```mermaid
### not an entry inside a fence
```

## Infrastructure

### CloudFront to origin is plain HTTP

- **What:** an entry.

#### A deeper heading is not an entry

### Python code over budget

  ### an indented heading is not an entry

## How this document is kept true
"""


def test_only_level_three_headings_outside_fences_are_entries() -> None:
    assert count_entries(REGISTER) == 2


def test_an_empty_register_has_no_entries() -> None:
    assert count_entries("# Technical debt register\n") == 0


def test_the_register_is_read_from_its_own_path() -> None:
    contents = {REGISTER_FILE: REGISTER.encode("utf-8"), PurePosixPath("docs/notes.md"): b"### not here\n"}
    assert register_entries(contents) == 2


def test_a_missing_register_fails_loudly() -> None:
    with pytest.raises(RegisterError, match=r"docs/TECH_DEBT.md"):
        register_entries({PurePosixPath("docs/notes.md"): b"### not here\n"})
