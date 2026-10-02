---
name: pytest
description: Use when writing or fixing Python tests with pytest — fixtures and scopes, conftest.py, parametrize, tmp_path/monkeypatch, marks, async tests, pytest-cov.
metadata:
  type: reference
---

<!-- navori:managed id="pytest" hash="c8cb8961" version="0.11.1" source="@navori/core" fmkeys="name,description,metadata" -->
# pytest — conventions

## When to use this skill

When authoring or debugging pytest tests: sharing setup with fixtures, table-driving cases, isolating files and environment, testing async code, or measuring coverage. Plain `assert` is the assertion API; pytest rewrites it to show values on failure.

## The pattern

Arrange–act–assert, one behavior per test, setup in fixtures, cases in `parametrize`.

```python
import pytest

@pytest.fixture
def cart():
    return Cart()

@pytest.mark.parametrize(
    ("qty", "total"),
    [(1, 10), (3, 30), pytest.param(0, 0, id="empty")],
)
def test_total(cart, qty, total):
    cart.add(price=10, qty=qty)
    assert cart.total() == total

def test_rejects_negative(cart):
    with pytest.raises(ValueError, match="qty"):
        cart.add(price=10, qty=-1)
```

## Gotchas that bite

- **Fixture scope defaults to `function`.** Use `scope="module"` or `"session"` only for costly, read-only setup; shared mutable state couples tests.
- **Shared fixtures go in `conftest.py`.** pytest discovers it automatically, with no import; keep it per directory, scoped to the tests beneath it.
- **Isolate the filesystem and environment.** Use `tmp_path` for files and `monkeypatch.setenv` / `monkeypatch.setattr` for env and attributes; pytest undoes them after each test.
- **Async tests need a plugin.** `pytest-asyncio` needs `@pytest.mark.asyncio` (or `asyncio_mode = "auto"` in config); `anyio` needs `@pytest.mark.anyio`. Without one, the coroutine is never awaited: the test is skipped with a warning (a failure in pytest 8.4+).
- **No network in unit tests.** Fake the client with `monkeypatch` or a fixture; reserve real I/O for a marked integration suite.
- **Register custom marks.** Declare them under `markers` in `pyproject.toml`, or `--strict-markers` fails on typos.

## Hard rules

1. Name files `test_*.py` and functions `test_*`.
2. Put setup in fixtures, not module-level state; use `yield` fixtures for teardown.
3. Table-drive similar cases with `parametrize` and readable `ids`.
4. Use `tmp_path` and `monkeypatch`; never write to the repo or leave env changed.
5. Pick one async marker style for the repo and configure it once.
6. Coverage via `pytest-cov`: `pytest --cov=<package> --cov-report=term-missing`. Assert behavior, not a line target.

## Quick table

| Need | Use |
|---|---|
| Shared setup | `@pytest.fixture` in `conftest.py` |
| Many inputs | `@pytest.mark.parametrize` |
| Temp files | `tmp_path` |
| Patch env/attr | `monkeypatch.setenv` / `setattr` |
| Expected error | `pytest.raises(Err, match=...)` |
| Skip / expected fail | `@pytest.mark.skip` / `xfail` |
| Run a subset | `pytest -k name` / `-m mark` |

## Before declaring done

- Each test fails for the right reason; no order dependence between tests.
- Async tests carry the marker their plugin requires.
- No real network, clock, or filesystem writes outside `tmp_path`.
- `ruff check .` green.
<!-- /navori:managed id="pytest" -->

## This repo's tests (your domain)

<!-- user: add here what only applies to THIS repo. Suggestions:
     - Where tests live and the naming convention.
     - What conftest.py provides (app, DB, client fixtures).
     - What is mocked by convention (network, clock, storage) and what is never mocked.
     - Coverage the repo requires and which areas are exempt.
-->
