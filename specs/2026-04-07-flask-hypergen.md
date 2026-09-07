# Spec: Flask + SQLAlchemy support for Hypergen


## Goal

Build a standalone `flask_hypergen` library in this repo, with Flask integration, packaged
static assets, self-contained examples, and an implementation path that supports modern
SQLAlchemy 2.0 style models in those examples.


## Decisions confirmed

- The Flask Hypergen implementation will live in `src/flask_hypergen` as its own module.
- The importable Python package path uses `_`, even if the project/distribution name uses
  `-`.
- Preserve Hypergen API names such as `liveview`, `action`, and `callback`.
- Example apps should be self-contained and not Boothby-specific.
- Any example models should live with the example code, and represent Hypergen + Flask +
  SQLAlchemy usage.
- Example apps should live at `src/flask_hypergen/examples`.
- Defer a Flask `autourls` equivalent until after explicit-route examples are working.
- Static assets should ship as library assets from `src/flask_hypergen/static`, following
  normal Flask library packaging practices.


## Repo-hosting constraints

- `flask_hypergen` is library code hosted inside this repo for now.
- The library dependencies will be kept in a designated group in the main project's
  `pyproject.toml`.
- The importable package lives at `src/flask_hypergen`.
- Self-contained example apps live at `src/flask_hypergen/examples`.
- Static assets ship from `src/flask_hypergen/static`.
- Tests for the library and examples will also live in this repo.
- The operator has explicitly authorized the agent to run required `uv add` commands
  during implementation/testing without pausing for approval.


## Hypergen findings from reference context


### Likely framework-agnostic core

- `hypergen.context` provides the thread-local context store.
- `hypergen.template` provides HTML generation, HTML joining, and plugin execution.
- The client command protocol and JSON serialization are reusable concepts.
- The browser runtime in `hypergen.js` is not Django-specific.


### Django-coupled pieces to replace or isolate

- `hypergen.liveview` depends on Django `HttpResponse` classes, `request.META`, URL
  resolving, static URL helpers, and Django permission helpers.
- `hypergen.hypergen` depends on Django URL reversing/path registration and Django
  permission exceptions/decorators.
- `hypergen.templatetags` and `hypergen.apps` are Django-only.
- Example apps assume Django URL modules and Django request/response objects.


## Proposed direction

Treat this as an adapter project, not a Flask rewrite of all Hypergen internals.


### Adapter boundary

Keep or extract a framework-neutral Hypergen core for:

- context handling
- template rendering
- callback command serialization
- command response payload generation
- client JS runtime

Add a Flask integration layer for:

- request/context initialization
- full-page liveview responses
- action POST endpoints returning JSON command lists
- URL registration + reverse lookup
- static asset delivery
- optional auth/permission hooks


## Library package target

The library should provide:

- Flask integration for Hypergen-powered views and actions
- packaged static asset serving from the library static path
- request/context initialization during Flask request handling
- example apps that demonstrate the supported integration patterns


## SQLAlchemy direction

For this project, prefer modern typed SQLAlchemy mappings:

- `Mapped[...]`
- `mapped_column(...)`
- declarative models in SQLAlchemy 2.0 style

Do not model new examples after older untyped `db.Model` patterns from legacy reference
apps.


### Initial implication

Because the library examples should be self-contained, SQLAlchemy support should be
treated as:

1. framework compatibility with Flask request/app/session lifecycle
2. a small typed example model inside a self-contained example package once a DB-backed
   example is selected


## Phased implementation plan


### Phase 1: establish the Flask adapter

- define a Flask response contract for liveviews and actions
- provide request context initialization compatible with Hypergen core expectations
- provide a Flask-friendly `liveview` decorator
- provide a Flask-friendly `action` decorator
- support `callback(...)` posting JSON payloads to Flask endpoints
- serve/load the Hypergen JS bundle in Flask


### Phase 2: get one no-DB example working

Port the simplest examples first:

1. `hellocoreonly`
2. `hellohypergen`

Rationale:

- they validate the render pipeline and callback loop
- they keep scope small
- they separate “manual endpoint wiring” from “decorator ergonomics”


### Phase 3: add Flask ergonomics

- add URL reversing for Hypergen callbacks and links
- decide whether to support an `autourls` equivalent in Flask
- support base templates / target IDs / partial updates cleanly


### Phase 4: add one SQLAlchemy-backed example

After non-DB examples work, port one small example that proves DB mutation + re-rendering
under Flask.

Preferred shape:

- a deliberately small self-contained example package
- example-local typed SQLAlchemy models
- typed SQLAlchemy mappings
- simple create/update interaction from a Hypergen action

This is a better first SQLAlchemy target than porting a large Django example like
`booking` immediately.


## Example priorities


### First examples to port

- `hellocoreonly`: best first target because it avoids decorator magic and proves the
  minimal contract.
- `hellohypergen`: next target because it exercises `@liveview`, `@action`, and callback
  wiring.


### Smoke-test example suite

Use these five examples as the primary implementation smoke-test set, in roughly this
order:

1. `hellocoreonly`
    - proves the lowest-level Flask contract for `hypergen(...)`, manual action endpoints,
      JSON command responses, and DOM target updates
2. `hellohypergen`
    - proves preserved Hypergen API names and the basic Flask `liveview` + `action`
      decorator flow
3. `inputs`
    - proves client-to-server argument extraction, coercion, nested payload serialization,
      and input element coverage
4. `apptemplate`
    - proves base-template support, `target_id` conventions, `THIS` element value capture,
      and a realistic small app structure
    - **Goal:** The Flask port of this example should demonstrate the recommended Flask
      Blueprint structure for a `flask_hypergen` app, showing users the "right way" to
      organize their code.
5. `commands`
    - proves server-to-client command generation, command ordering, and the Flask
      adapter's JSON command response behavior

These five give broad coverage without pulling in Django-template integration, websockets,
or a large persistence-heavy app too early.


### Next wave after the smoke-test suite

- `partialload`
    - good follow-up once the explicit-route examples are stable, because it exercises
      partial navigation, history integration, and the `X-Hypergen-Partial` request flow


### Examples to defer

- `booking`
- websocket examples
- Django template integration examples

These should wait until the Flask adapter contract is stable.


## Architectural decisions to make during implementation


### 1. URL registration strategy

Start with explicit Flask routes if that reduces risk. The recommended API is to pass a
`Blueprint` or `Flask` app object to the decorators to preserve Hypergen API names (e.g.,
`@liveview(bp, perm=...)` or `@action(bp, ...)`).

Only add a Flask `autourls` equivalent after basic liveview/action behavior works.


### 2. Request context strategy

Hypergen currently expects `request` in its context store. For Flask, we likely need one
of:

- a blueprint/app `before_request` hook
- a small wrapper around the liveview/action decorators


### 3. Response types

Define Flask-native equivalents for:

- full HTML page response
- JSON command response
- redirect encoded as a Hypergen command response when needed


### 4. Static assets

Need a stable way to serve the Hypergen JS asset path expected by rendered pages. For
Phase 1, simply copying the existing built `hypergen.js` bundle from the reference context
(`src/hypergen/static/hypergen/hypergen.js`) into `src/flask_hypergen/static` is
sufficient.

Current direction:

- copy pre-built `hypergen.js` from `src/hypergen/static/hypergen/hypergen.js` to
  `src/flask_hypergen/static/hypergen.js`
- expose them using Flask library/static best practices
- avoid making assets Boothby-specific


## Testing plan

- unit tests for Flask liveview/action wrappers
    - Ensure you cover every test from hypergen/test_all.py
    - If a hypergen test doesn't apply b/c of flask/django differences, create the body
      anyway with an assert False and xfail it.
- request tests for the example routes using a library-owned Flask test app/client pattern
- callback/action tests that assert JSON command payloads
- one end-to-end-ish request cycle for the counter example
- playwright for end-to-end testing


## Risks / unknowns

- Existing Hypergen examples rely heavily on Django URL and response conventions.
- Partial loading/history support may require extra Flask-specific adaptation beyond the
  first example ports.


## Questions for follow-up

1. Should the example apps be written against plain Flask only, or is using `flask-flac`
   acceptable in examples if it keeps the implementation cleaner?
    - Examples should be flask only.
2. For the initial `perm` story on `liveview` / `action`, do you want unsupported
   Django-style permission behavior to be a hard error, or should Phase 1 treat
   permissions as an optional no-op hook?
    - You have SetHub in your context. It has flask authentication. See what libraries it
      uses for auth, I think it's flask-login, and build an authentication flow around
      that.
    - Ignore authorization/permissions for now. Provide a NO_PERM_REQUIRED constant and
      error out if anything else is given. Keep a task open for doing permissions.
3. For callback routing in the first working version, is endpoint-name-based reverse
   lookup via Flask `url_for(...)` sufficient, or do you want function-based
   `callback(my_action, ...)` ergonomics working in the first decorator milestone?
    - url_for() is sufficient but keep a task/todo open for improving the DevX
4. Should the first public Flask adapter expose only the preserved Hypergen decorators
   (`liveview`, `action`, `callback`), or do you also want lower-level helpers surfaced
   for explicit-route/manual wiring use cases?
    - If lower-level helpers seem like they would be useful, surface them.
    - But, for clarity, nothing should be "buried" either. I'm not a big fan of lots of
      private stuff in a library.
5. Is copying the current built `hypergen.js` file into
   `src/flask_hypergen/static/hypergen.js` manually acceptable for Phase 1, or do you want
   a repo task/script to keep that asset synced from the reference source?
    - Just copy for now. No sync/copy script needed.
6. Do you want the first example/test app fixtures to live under
   `tests/flask_hypergen_tests/` with Flask's built-in test client...
    - yes


## Initial recommended execution order

1. build `src/flask_hypergen` Flask integration scaffold
2. port `hellocoreonly` to Flask with explicit routes
3. add Flask `liveview` / `action` wrappers with preserved API names
4. port `hellohypergen`
5. add one small self-contained SQLAlchemy-backed example


## Implementation notes (2026-04-07)

- Implemented `src/flask_hypergen` with Flask-backed `context`, `template`, `hypergen`,
  `liveview`, `imports`, `plugins`, and package exports.
- Added `init_app(app)` that registers request-context setup and a packaged static
  blueprint for `/flask_hypergen/static/hypergen.js`.
- Copied the browser-ready Hypergen bundle from the reference repo path
  `src/hypergen/static/hypergen/dist/hypergen.js` into
  `src/flask_hypergen/static/hypergen.js`.
- Implemented `NO_PERM_REQUIRED`; any other `perm` currently raises `NotImplementedError`
  as directed.
- Implemented the initial smoke-test example suite under `src/flask_hypergen/examples`:
    - `hellocoreonly`
    - `hellohypergen`
    - `inputs`
    - `commands`
    - `apptemplate`
    - `sqlalchemy_counter`
- Added a shared Flask app factory at `src/flask_hypergen/examples/app.py`.
- Added adapted/copied Hypergen core tests, example request tests, and a Playwright e2e
  test under `tests/flask_hypergen_tests/`.
- Added supporting dependencies during implementation/testing: `pyrsistent`, `yattag`, and
  `pytest-playwright`.


## Review + follow-up implementation notes (2026-04-07)

- Moved Flask Hypergen-specific dependencies into dedicated dependency groups in
  `pyproject.toml`:
    - `flask-hypergen`
    - `flask-hypergen-test`
- Hooked the `pytest` dependency group up to include the Flask Hypergen runtime/test
  groups so the test env still installs what the library needs.
- Implemented `Context.__setitem__` instead of leaving the confusing `Exception('TODO')`
  path.
- Standardized the mixed action/liveview command access to attribute-style context access.
- Removed the `d = dict` alias usage from the Flask Hypergen modules touched by the
  review.
- Removed `tests/flask_hypergen_tests/test_dummy.py`.
- Strengthened the ported core tests to restore the dropped Django Hypergen sub-cases and
  tighter assertions:
    - `test_element`
    - `test_live_element`
    - `test_components2`
    - `test_js_value_func`
    - `test_plugins`
- Added a public API export test for `flask_hypergen.__init__`.
- Completed the auth/permission follow-up task by adding real Flask auth integration:
    - added `LOGIN_REQUIRED`
    - resolved users from Flask-Login when present
    - support login-required and string/iterable permission checks via `has_perm` /
      `has_perms`
    - action auth failures now return JSON redirect commands for Hypergen callbacks
- Added a self-contained `auth` example demonstrating login, logout, authenticated
  liveviews, and permission-protected actions.
- Completed the callback/reverse DevX follow-up by making
  `route_register(..., methods=['POST'])` mark explicit POST routes as callback-capable,
  and updated `hellocoreonly` to use function-based callback reverse wiring instead of raw
  `url_for()`.
- Completed the `partialload` follow-up by porting a Flask `partialload` example and
  adding request + Playwright coverage for partial navigation/history behavior.


## Style/architecture refactor notes (2026-04-07)

- Refactored the Flask Hypergen implementation toward the explicit, typed, modular style
  used by `tasks/agent.py`.
- Removed the Flask Hypergen file-level wildcard-import `# ruff: noqa` suppressions from
  the library core and examples.
- Reworked `src/flask_hypergen/imports.py` and `src/flask_hypergen/__init__.py` to use
  explicit module aggregation instead of star-import re-export chains.
- Replaced implicit cross-module name flow in the examples with explicit imports from
  `flask_hypergen`.
- Added stronger typing and clearer helper boundaries in the core modules:
    - `context.py` now has typed context helpers and a clearer request-context
      construction path.
    - `hypergen.py` now uses typed data structures for resolver and permission-check
      results.
    - `template.py` now uses `HypergenSettings` and `HypergenResult` dataclasses instead
      of ad-hoc settings/result dict shaping in the render pipeline.
    - `liveview.py` now uses explicit imports and smaller named helpers for callback
      redirect handling and namespace resolution.
- Kept the public Hypergen API intact while reducing the Django-carried architectural
  patterns that made the Flask port harder to read and maintain.


## Current status

- `ruff check src/flask_hypergen tests/flask_hypergen_tests --ignore COM812` passes.
- `ruff format src/flask_hypergen tests/flask_hypergen_tests` passes.
- `pytest tests/flask_hypergen_tests -q -ra` passes with `41 passed, 1 xfailed`.


## Open follow-up tasks

- None currently.


## Review Notes (by Gemini 3.1 Pro Preview)

I have reviewed the current code changes against the spec. The implementation successfully
completes all the objectives outlined in the initial phases:

1. **Code Organization:** The code is cleanly structured within `src/flask_hypergen` and
   `src/flask_hypergen/examples` as requested. The test suite correctly lives in
   `tests/flask_hypergen_tests`.
2. **API Compatibility:** The preserved API names (`liveview`, `action`, `callback`)
   correctly emulate the Django hypergen usage, wrapping the Flask-specific request
   handling logic elegantly. Permission hooks currently use the `NO_PERM_REQUIRED` stopgap
   correctly.
3. **SQLAlchemy 2.0:** The `sqlalchemy_counter` example perfectly conforms to the
   SQLAlchemy 2.0 standard typed models (`Mapped`, `mapped_column`, `DeclarativeBase`),
   avoiding legacy `db.Model` patterns.
4. **Testing:** Tests include porting the core assertions (e.g. `test_core_ported.py`),
   endpoint request assertions, and playwright usage for the `counter` E2E test.
5. **Deferred Items:** Websocket implementation was successfully omitted (`websocket.py`
   is an empty stub) keeping the scope limited as instructed.

**Minor Discrepancy Found:**

- The spec requested that "The library dependencies will be kept in a designated group in
  the main project's `pyproject.toml`." However, in `pyproject.toml`, the dependencies
  (`pyrsistent`, `yattag`, `pytest-playwright`, `playwright`) were either placed directly
  in the main `dependencies` list or scattered into the `pytest` and `tests` groups,
  rather than a single dedicated group for `flask_hypergen` (e.g.,
  `[dependency-groups.flask-hypergen]`).

Overall, excellent progress that aligns very well with the documented goals and strategy.


## Review Notes (by Claude Opus 4.6 via Augment Agent)

Verified: `pytest tests/flask_hypergen_tests -q` passes (32 passed, 1 xfailed).
`ruff check` and `ruff format` clean.


### Spec compliance

- All six smoke-test examples implemented: `hellocoreonly`, `hellohypergen`, `inputs`,
  `commands`, `apptemplate`, `sqlalchemy_counter`.
- API names `liveview`, `action`, `callback` preserved as specified.
- `NO_PERM_REQUIRED` implemented; other `perm` values raise `NotImplementedError` as
  directed.
- SQLAlchemy example uses `Mapped[...]`, `mapped_column(...)`, `DeclarativeBase` per spec.
- Static asset copied into `src/flask_hypergen/static/hypergen.js` and served via a Flask
  Blueprint.
- All 23 tests from `django-hypergen/src/hypergen/test_all.py` have corresponding tests in
  `test_core_ported.py` (1:1 match by name).
- The xfailed `test_context_middleware_old` correctly documents the intentional
  Django-only omission.


### Issues found

1. **`pyproject.toml` dependency placement (also noted by Gemini review):** Spec says
   "library dependencies will be kept in a designated group" but `pyrsistent` landed in
   the top-level `[project] dependencies` (making it a Boothby runtime dep), `yattag` and
   `pytest-playwright` landed in the `pytest` group, and `playwright` in a separate
   `tests` group. There is no `flask-hypergen` dependency group. `pyrsistent` and `yattag`
   are runtime deps of `flask_hypergen` specifically; `playwright`/`pytest-playwright` are
   test deps. All should be in dedicated group(s) to keep the Boothby app deps separate.

2. **`Context.__setitem__` raises `Exception('TODO')` (context.py:46):** This is a live
   code path that will produce a confusing error if anyone writes
   `context['key'] = value`. Should either implement it (as
   `self.ctx = self.ctx.set(key, value)`, mirroring `__setattr__`) or raise
   `NotImplementedError` with a clear message.

3. **Inconsistent context access in `action` fallback return (liveview.py:566):** The
   `action` decorator's final return path uses `full['context']['hypergen']['commands']`
   (dict-style bracket access on the Context clone), while the `liveview` partial path
   (line 460) uses `full['context'].hypergen.commands` (attribute access). Both work
   because `Context` supports both, but the mixed style is confusing and suggests one path
   wasn't tested as thoroughly. Should be consistent.

4. **`d = dict` alias used across multiple modules:** `context.py`, `hypergen.py`,
   `liveview.py`, and `template.py` each define `d = dict` at module scope. This is
   carried over from the Django codebase but hurts readability for anyone new to the code.
   Consider removing it in the Flask port or at least documenting it.

5. **Broad `# ruff: noqa` suppressions:** Multiple files suppress `F403` (wildcard
   imports) and `F405` (undefined names from star imports) at the file level. This is
   inherited from the Django hypergen style, but it means ruff can't catch actual
   missing-name errors in these files. Worth noting as a known tradeoff.

6. **`test_dummy.py` is dead weight:** Contains only `assert True`. Should be removed.

7. **`test_plugins` asserts on `html1.strip() == html2.strip()` but doesn't assert the actual expected HTML (test_core_ported.py:324):**
   The original Django test asserted against a known `HTML` constant string. The Flask
   port only asserts the two templates produce equal output and that certain substrings
   are present. This is weaker coverage — a regression in the liveview media injection
   could pass this test if both paths broke identically.

8. **`test_element` is missing two sub-cases from the original:** The Django
   `test_element` had two additional assertions at the end (a nested `div(…div(…ul(…)))`
   case and a deeply nested `ul(None, [li(…)])` case). These were dropped in the port
   without an xfail stub.

9. **`test_live_element` is simplified vs original:** The original had additional
   sub-cases after a `return` statement (textarea, autofocus, etc.) that were effectively
   dead code in the Django test too, but the spec says "If a hypergen test doesn't
   apply…create the body anyway with an assert False and xfail it." These unreachable
   cases weren't ported or xfailed.

10. **`test_components2` is missing a sub-case:** The original had a second
    `with tr(): with td(): comp1()` assertion block that was dropped.

11. **`test_js_value_func` is missing the `type_="weidewokvocxkokwoekvd"` (nonsense type)
    sub-case:** The original tested that an unknown input type yields
    `(js_value_func, None)`. Dropped without xfail.

12. **No `__init__.py` test for public API surface:** There's no test that verifies the
    names exported from `flask_hypergen.__init__` match an expected set. Given the heavy
    use of `__all__` and star imports, a simple
    `assert set(expected_names) <= set(dir(flask_hypergen))` test would catch import
    wiring regressions cheaply.


### Observations (not issues)

- The `appstate.py` plugin uses `pickle` for session serialization via `latin1`
  encode/decode. This is inherited from Django hypergen and works, but is a known security
  surface if Flask sessions are client-side (signed cookies). Worth documenting in the
  spec's risks section when auth integration happens.
- The `autourl_register` and `autourls` functions in `hypergen.py` are ported stubs that
  aren't used yet, consistent with the spec deferring `autourls`.
- The examples all share `common.py` for base templates, keeping them DRY. Good.
- The e2e test fixture (`live_server`) is well done — ephemeral port, daemon thread,
  proper shutdown.


## Review Notes (by Claude Opus 4.6 via Augment Agent, 2026-04-07 ~21:00 UTC)

Verified: `pytest tests/flask_hypergen_tests -q -ra` passes (41 passed, 1 xfailed).
`ruff check` and `ruff format` clean.


### Previous review issues addressed

The v2 and style/architecture refactor commits addressed the majority of issues from the
prior review:

- ✅ `pyproject.toml` dependencies now in dedicated `flask-hypergen` and
  `flask-hypergen-test` groups
- ✅ `Context.__setitem__` implemented properly
- ✅ Context access style is now consistent (attribute-style used throughout)
- ✅ `d = dict` alias removed
- ✅ `test_dummy.py` removed
- ✅ `test_plugins` now asserts against a full expected HTML constant
- ✅ `test_element` missing sub-cases restored
- ✅ `test_components2` missing sub-case restored
- ✅ `test_js_value_func` nonsense-type sub-case restored
- ✅ `test_live_element` textarea/autofocus sub-cases added
- ✅ Public API export test (`test_flask_hypergen_public_api`) added
- ✅ File-level `# ruff: noqa` removed from library core and examples (only remains on
  test file, acceptable)


### Issues found


#### 1. Use known types instead of `Any`; add missing annotations — `template.py`

**This should be fixed before moving on to new work.** Many public functions either have
no type annotations at all or use `Any` where the actual type is known. Using the real
type catches caller mistakes at IDE/mypy time and documents the API contract.

Functions with **no annotations at all** (need both parameter and return types):

- `add_class(a, b)` — line 52: `a` is `str | list | set | None`, `b` is `str`, returns
  `str | list | set`
- `on_url(url, value_on_url=True, value_not_on_url=False)` — line 69: `url` is `str`
- `hypergen(template, *args, **kwargs)` — line 156: `template` is `Callable[..., Any]`,
  return is `str | deque | HypergenResult`
- `hypergen_to_response(func, *args, **kwargs)` — line 188: `func` is
  `Callable[..., Any]`, returns `Response`
- `join_html(html)` — line 192: `html` is `list`, returns `str`
- `raw(*children)` — line 208: returns `None`
- `write(*children)` — line 212: returns `None`
- `rst(restructured_text, report_level=None)` — line 216: `restructured_text` is `str`
- `doctype(type_='html')` — line 503: `type_` is `str`, returns `None`
- `Component.__init__(self, into, i, j)` — line 425: `into` is `list`, `i` and `j` are
  `int`
- All `base_element` methods

**Suggested fix for `hypergen` (the most important one):**

```python
def hypergen(template: Callable[..., Any], *args: Any, **kwargs: Any) -> str | deque | HypergenResult:
```


#### 2. Use known types instead of `Any`; add missing annotations — `liveview.py` and `context.py`

**This should be fixed before moving on to new work.** Same problem across `liveview.py`
and `context.py` — many parameters typed `Any` where the concrete type is known.

Known-type `Any` parameters that should use the real type:

- `init_app(app: Any) -> Any` — line 101: should be `app: Flask` → `Flask`
- `context_init_app(app: Any)` — context.py line 129: should be `app: Flask`
- `check_perms(request: Any, ...)` — hypergen.py line 108: `request` is `Request` (from
  `flask`)
- `user_resolve(request: Any)` — context.py line 94: should be `Request`
- `context_values_build(request: Any)` — context.py line 108: should be `Request`
- `context_middleware(get_response: Callable[[Any], Any])` — context.py line 116: the
  `Any` args are `Request` and `Response`
- `ContextMiddleware.process_request(self, request: Any)` — context.py line 125: should be
  `Request`
- `context_teardown_request(exc: Any)` — context.py line 138: should be
  `BaseException | None`

Functions with **no annotations at all** that need them:

- `liveview(func, router=None, ...)` — line 432: `func` is `Callable`, `router` is
  `Blueprint | Flask | None`, `rule` is `str | None`, `perm` is
  `str | tuple[str, ...] | None`, etc.
- `action(func, router=None, ...)` — line 535: same known types as `liveview`
- `encoder(o)` — line 631: returns `list | dict`
- `decoder(o)` — line 654: `o` is `dict`, returns the decoded value
- `dumps(data, default=encoder, indent=None)` — line 665: `data` can stay `Any` (truly
  generic), but `default` is `Callable` and `indent` is `int | None`, returns `str`
- `loads(data, integer_keys=False)` — line 669: `data` is `str`, `integer_keys` is `bool`,
  return is `Any` (legitimately unknown)
- `LiveviewPlugin.process_html(self, html_output)` — line 226: `html_output` is `str`,
  returns `str`


#### 3. Bare `except Exception` in `user_resolve` (context.py:104)

```python
try:
    return current_user._get_current_object()
except Exception:
    return None
```

Per AGENTS.md: "Don't catch an exception just to catch it." This silently swallows any
error from Flask-Login (e.g. misconfigured app context, broken user loader). At minimum,
this should catch `RuntimeError` (which Flask-Login raises outside a request context)
rather than all exceptions. If a user loader raises `ValueError` or `TypeError`, the
developer should see that error.

**Suggested fix:**

```python
except RuntimeError:
    return None
```


#### 4–5. (Folded into issues #1 and #2 above)

`init_app(app: Any)` and `context_init_app(app: Any)` are called out in issue #2 as
known-type `Any` parameters that should use `Flask`.


#### 6. Missing test coverage for auth permission edge cases

The auth tests cover the happy paths well, but are missing:

- `any_perm=True` behavior (requesting any of several permissions)
- `raise_exception=True` behavior (should raise `Forbidden` instead of returning a
  redirect/403)
- Permission-protected action returning 403 (not redirect) for authenticated user without
  permission

These are all code paths in `check_perms()` that aren't exercised by any test.


#### 7. Missing test coverage for `command()` function options

The `command()` function in `liveview.py:322` supports `prepend=True` and `return_=True`
kwargs. The `return_=True` path is tested indirectly through
`test_commands_demo_returns_explicit_commands`, but `prepend=True` has no direct test.
Since command ordering is important for Hypergen's client-side execution model, a unit
test asserting prepend behavior would be valuable.


#### 8. Missing test for `loads()` with `integer_keys=True`

The `loads` function (liveview.py:669) has an `integer_keys` parameter with a dedicated
code path (`integer_keys_object_pairs_hook`). No test exercises this path.


#### 9. `examples/__init__.py` has untyped `create_app` wrapper

```python
def create_app(*args, **kwargs):
```

This is a minor convenience wrapper but should match the signature of the function it
delegates to for IDE support.


#### 10. `conftest.py` fixtures and helpers lack type annotations

`tests/flask_hypergen_tests/conftest.py` — `User`, `Request`, `HttpResponse`,
`hypergen_context()`, `mock_hypergen_callback()` all lack type annotations. While test
code is less critical, these are shared fixtures used across the test suite and
annotations would document the expected mock interfaces.


#### 11. `test_core_ported.py` still uses wildcard import

Line 1 has `# ruff: noqa: F403, F405, E501, C408, B011, B017, SIM117` and line 14 has
`from flask_hypergen.imports import *`. The library itself was cleaned up, but the test
file still relies on star imports. This makes it unclear which names the tests actually
depend on and prevents ruff from catching undefined name errors in the test file.

**Suggested fix:** Replace the star import with explicit imports for the ~20 names
actually used in the tests (`div`, `ul`, `li`, `input_`, `textarea`, `span`, `html`,
`head`, `body`, `title`, `h1`, `h2`, `p`, `tr`, `td`, `a`, `select`, `FULL`, `component`,
`doctype`, `THIS`, `callback`, `call_js`, `dumps`, `loads`, `hypergen`, `command`).


### Observations (not issues)

- The `HypergenSettings` and `HypergenResult` dataclasses in `template.py` are a nice
  improvement over the ad-hoc dict patterns. `HypergenResult.__getitem__` provides
  backward compatibility for dict-style access while enabling attribute access.
- The `_reverse_factory` / `route_register` pattern in `hypergen.py` is clean and provides
  good function-based callback ergonomics.
- The `PermissionCheck` and `ResolverMatch` frozen dataclasses in `hypergen.py` are
  well-structured and make the control flow in `check_perms` much more readable than the
  prior approach.
- The `contextlist` class is a clever solution for multi-target rendering, and the tests
  (`test_multilist`, `test_multitargets`) cover it well.
- The auth example is self-contained with its own `DemoUser` dataclass — good separation
  from the library code.
- Pickle-in-session observation from prior review still applies: `appstate.py` uses
  `pickle` for session serialization. This is a known security surface documented in the
  prior review and should be called out in user-facing docs when those are written.


## Review follow-up implementation notes (2026-04-07 late)

- Tightened library typing across the reviewed public surfaces:
    - `template.py` now annotates the previously untyped public helpers called out in
      review (`add_class`, `on_url`, `hypergen`, `hypergen_to_response`, `join_html`,
      `raw`, `write`, `rst`, `doctype`), plus `Component` and the `base_element` methods.
    - `liveview.py` now annotates `init_app`, `LiveviewPlugin.process_html`, `liveview`,
      `action`, `encoder`, `decoder`, `dumps`, and `loads` with concrete
      Flask/router/signature types instead of unhelpful `Any` placeholders.
    - `context.py` and `hypergen.py` now use concrete Flask types for app/request-facing
      functions (`context_init_app`, `context_values_build`, `context_middleware`,
      `ContextMiddleware.process_request`, `check_perms`, etc.).
- Narrowed `user_resolve()` exception handling to `RuntimeError` so real
  Flask-Login/user-loader bugs are no longer silently swallowed.
- Added the missing auth/permission coverage requested by review:
    - `any_perm=True` subset matching
    - `raise_exception=True` forbidden path
    - authenticated-but-unauthorized action requests returning `403` instead of redirect
      commands
- Added focused unit coverage for the remaining untested helper branches:
    - `command(..., prepend=True)` ordering
    - `loads(..., integer_keys=True)` integer-key decoding
- Typed the convenience app factory wrapper in `src/flask_hypergen/examples/__init__.py`
  to match the delegated signature.
- Added type annotations to the shared Flask Hypergen test fixtures/helpers in
  `tests/flask_hypergen_tests/conftest.py`.
- Replaced the remaining wildcard import in
  `tests/flask_hypergen_tests/test_core_ported.py` with explicit imports.


## Current status

- `ruff check src/flask_hypergen tests/flask_hypergen_tests --ignore COM812` passes.
- `ruff format src/flask_hypergen tests/flask_hypergen_tests` passes.
- `pytest tests/flask_hypergen_tests -q -ra` passes with `46 passed, 1 xfailed`.
