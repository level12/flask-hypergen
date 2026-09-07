# Spec: Flask-Hypergen Day 2


## Background

See ./2026-04-07-flask-hypergen.md for the original spec and progress we've made.


## Task: Improve reviewing the examples

- [x] Add a readme to src/flask_hypergen with instructions on how to run the examples
- [x] Add an index view which lists all the examples with links to them. Add a CDN css
      framework and do some basic styling to make it look nice. Should work for light and
      dark modes, pick a color theme, maybe an electric blue or burnt orange.


## Task: Fix broken examples

- [x] `hellohypergen` and `apptemplate` examples won't increment past 1
- [x] `inputs` has summary <p> that has nothing in it
- [x] Examples reference "django-hypergen" in the header area, remove that entire tag, we
      don't need it
- [x] Auth example links to the /auth/protected which drops you into an already
      authenticated view which seems odd.
    - [x] Should start with unauthenticated and then give an "authenticate" link?
    - [x] "Log out" link seems to do nothing

Make sure you add tests to cover this functionality to avoid future regressions.


## Task: Refine flask-hypergen's usability and dev experience

- [ ] Don't import EVERYTHING into flask_hypergen/__init__.py. Evaluate the example usage
      patterns and let's figure out a sane import strategy for what's available at the top
      level.
- [ ] Don't import tags at the top level. Instead, require the dev to do an explicit
      import from of or from the tags module so the idiom can be
      `from flask_hypergen impor tags as t` or `from flask_hypergen.tags import p, div`
      depending on what the dev wants.


## Implementation notes (2026-04-07)

- Expanded `src/flask_hypergen/README.md` with direct example-run instructions for both
  `mise exec` and an already-activated `mise` shell.
- Reworked `src/flask_hypergen/examples/index.py` into a styled example index with
  generated links, Pico CSS via CDN, and light/dark-friendly azure theming.
- Simplified the examples index further into a plain table and made the view name itself
  the link.
- Added request-test coverage for the example index in
  `tests/flask_hypergen_tests/test_examples.py`.
- Fixed stale action callback state when rendering action responses with `base_view`,
  which unblocked the multi-click counter examples.
- Removed the shared example header blurb mentioning django-hypergen.
- Made the auth example start at a public unauthenticated page and send logout back there.
- Filled the inputs example summary paragraph with explicit placeholder/submitted text.
- Expanded regression coverage for the example routes, auth flow, callback payloads, and
  double-click counter e2e behavior.
