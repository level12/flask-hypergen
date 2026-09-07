# flask-hypergen

[![nox](https://github.com/level12/flask-hypergen/actions/workflows/nox.yaml/badge.svg)](https://github.com/level12/flask-hypergen/actions/workflows/nox.yaml)

Flask integration for Hypergen, with a repo-root `examples/` app for local development.


## Run the examples

1. Sync the dev environment:

   `uv sync`

2. Start the example app:

   `flask --app examples/app.py run --debug`

3. Open `http://127.0.0.1:5000/`


## Dev


### Copier Template

Project structure and tooling mostly derives from
[Coppy](https://github.com/level12/coppy). See its documentation for context and
additional instructions.

This project can be updated from the upstream repo, see
[Updating a Project](https://github.com/level12/coppy?tab=readme-ov-file#template-updates).


### Project Setup

From zero to hero (passing tests that is):

1. Ensure [host dependencies](https://github.com/level12/coppy/wiki/Mise) are installed

2. Start docker service dependencies (if applicable):

   `docker compose up -d`

3. Sync [project](https://docs.astral.sh/uv/concepts/projects/) virtualenv w/ lock file:

   `uv sync`

4. Configure prek:

   `prek install`

5. Run tests:

   `nox`


### JavaScript Runtime

The readable Hypergen browser source lives in `src/flask_hypergen/static-src/`. The
minified files in `src/flask_hypergen/static/` are generated package assets; do not edit
them directly.

Install the pinned Node and Aube toolchain through `mise`, then build or watch the
runtime:

```shell
mise install
mise run build-js
mise run watch-js
```

Aube is the project's only JavaScript package installer and script runner. The generated
bundle and source map remain committed so Python package users do not need JavaScript
tooling. Watch mode produces development output directly in the static directory; run
`mise run build-js` before committing or packaging to apply the production finalization.
Prek automatically rebuilds and checks these assets when related files are committed.


### Versions

Versions are date based. A `version` task shows and bumps versions:

```shell

  # Show current version
  mise version show

  # Bump version based on date, tag, and push:
  mise version bump

  # See other options
  mise version -- --help
```


### Coverage Notes

See `docs/coverage-notes.md`.
