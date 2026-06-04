# Test Coverage Notes

This document records the deliberate gaps in `flask_hypergen`'s test coverage: one
`xfail` placeholder carried over from the original `django-hypergen` test suite, and a
small number of source lines/branches that are intentionally left uncovered.

These are documented (rather than tested) because exercising them would require
behavior that flask_hypergen does not implement, or contrived environments (optional
dependencies uninstalled, internal invariants forced into impossible states) that would
add maintenance cost without testing anything meaningful.

## Intentional `xfail`: Django legacy middleware placeholder

`tests/flask_hypergen_tests/test_core_ported.py` contains:

```python
@pytest.mark.xfail(
    reason='Django legacy middleware compatibility is intentionally not part of flask_hypergen',
)
def test_context_middleware_old():
    raise AssertionError()
```

### Background

The upstream `django-hypergen` project supported Django's *old-style* middleware via
`django.utils.deprecation.MiddlewareMixin`. Its `context.py` did:

```python
try:
    from django.utils.deprecation import MiddlewareMixin
except ImportError:
    MiddlewareMixin = object  # Backwards compatibility.

class ContextMiddleware(MiddlewareMixin):
    def process_request(self, request):
        context.replace(**_init_context(request))
```

The corresponding upstream test (`test_context_middleware_old`) only ran on Django 3 or
earlier and asserted that the legacy `MiddlewareMixin`-based path populated the context:

```python
def test_context_middleware_old():
    if int(django.get_version()[0]) > 3:
        return
    middleware = ContextMiddleware()
    middleware.process_request(Request())
    assert context.request.user.pk == 1
```

### Why it is an `xfail` placeholder here

flask_hypergen is a Flask port and has **no dependency on Django**, so the
`MiddlewareMixin` deprecation-compatibility shim does not apply. The framework-agnostic
behavior it guarded *is* ported and tested:

- `ContextMiddleware.process_request` is covered by `test_context_middleware_class`.
- The functional `context_middleware` wrapper is covered by `test_context_middleware`.

The `test_context_middleware_old` placeholder is kept as a named `xfail` purely to
preserve a one-to-one mapping with the upstream test suite, making it obvious to future
readers that this Django-specific legacy path was considered and intentionally dropped
rather than overlooked. It is expected to remain `xfailed` indefinitely.

## Remaining uncovered source lines/branches

As of the latest run, total coverage is **99%**. The handful of uncovered
lines/branches below are intentional.

### `src/flask_hypergen/template.py`

Optional-dependency guards. These execute only when an optional package is absent (or
its lazy loader is invoked), which is not the case in the standard test environment.

- **Lines 62, 66** — `docutils_core_load()` / `docutils_utils_load()` bodies. These lazy
  `importlib.import_module('docutils.*')` loaders run only when `rst()` is actually used
  with `docutils` installed.
- **Lines 73-74** — the `except ImportError: yattag_ok = False` branch, which only runs
  when `yattag` is not installed. (The positive `yattag` path and the
  "yattag required" error path are both tested via mocking.)
- **Lines 268-271** — the `rst()` body that loads `docutils` and renders reStructuredText.
  The guard that raises when `docutils` is missing is tested; the success path requires
  `docutils` to be installed.

### `src/flask_hypergen/imports.py`

- **Line 22** — the `continue` in the flat-namespace dedup loop:

  ```python
  for name in getattr(module, '__all__', []):
      if name in __all__:
          continue  # only hit if two submodules export the same name
  ```

  This defensive branch fires only if two submodules export the *same* public name.
  Given the current module set and their `__all__` definitions, no such collision
  exists, so the line is unreachable today. It is retained to keep the re-export logic
  robust against future additions.

### `src/flask_hypergen/liveview.py`

Two negative branch-partials in `LiveviewPluginBase.template_after`:

- **`330->349`** — the path taken when an action `base_view` produces a resolver match
  whose `func` is `None` (so the isolated re-render is skipped). The positive case
  (a resolvable base view) is tested; this negative branch is a guard against an
  unresolvable referer.
- **`356->362`** — the path taken when `self.morph` is false or there is no `'into'` in
  the hypergen context, so the morph commands are not appended. The morph-enabled path
  is tested; this branch covers the non-morphing configuration.

Both are defensive negatives around the action/base_view re-render flow; forcing them
would require constructing an unresolvable or morph-disabled liveview state that does not
correspond to a real usage scenario.
