# Spec: Maintainable Hypergen JavaScript source and Aube build


## Background

Flask-Hypergen currently commits only a generated browser bundle at
`src/flask_hypergen/static/hypergen.js`. The file was copied from Django-Hypergen during
the initial Flask port. On the current `main` branch, it remains byte-for-byte identical
to Django-Hypergen's generated `src/hypergen/static/hypergen/dist/hypergen.js` bundle.

Django-Hypergen keeps readable JavaScript source beside a small Parcel build
configuration. Its main `hypergen.js` source imports `morphdom`, its local `websocket.js`
module, and `sockette`; Parcel bundles those inputs into the browser-ready file.
Django-Hypergen also declares `mousetrap`, but the current source does not import it.

The original Flask-Hypergen spec intentionally deferred source ownership and copied the
generated asset. That was appropriate for the initial port, but it now makes the client
runtime difficult to review, maintain, debug, and extend.

This work will be performed from `main`, before the region-update work is reapplied. The
region branch modified the generated bundle directly; those changes are outside this spec
and will be ported onto the readable source separately.


## Goal

Make readable JavaScript source and a reproducible browser build first-class parts of this
repository without changing Flask-Hypergen's current client behavior or requiring
JavaScript tooling for Python package consumers.

The repository should:

- own readable source for the complete current browser runtime
- use Aube, never npm, to install JavaScript dependencies and run package scripts
- generate the existing packaged `hypergen.js` asset from that source
- keep the generated asset committed and included in Python distributions
- provide straightforward build and watch workflows through `mise`
- make stale generated assets detectable in automated validation


## Non-goals

- Do not implement or port region updates, multi-target partials, or GET navigation.
- Do not intentionally change the public `window.hypergen` API or browser behavior.
- Do not upgrade or redesign the Hypergen client while establishing the source/build
  pipeline.
- Do not require Node, Aube, or Parcel when installing or using the published Python
  package.
- Do not create an automated synchronization mechanism with Django-Hypergen.
  Flask-Hypergen will own its copied source after provenance is recorded.


## Source and artifact layout

Keep authored source separate from generated static assets:

```text
package.json
aube-lock.yaml
src/flask_hypergen/static-src/
    hypergen.js
    websocket.js
src/flask_hypergen/static/
    hypergen.js
    hypergen.js.map
```

The source directory is repository/build input. The static directory is packaged runtime
output. The existing `/flask_hypergen/static/hypergen.js` URL must not change.

The source map should be generated, committed, packaged, and reference the readable
sources. This also fixes the current bundle's dangling and duplicated `sourceMappingURL`
comments. If Parcel cannot produce a stable usable source map, disable source-map output
and remove the comment rather than shipping a broken reference; record that deviation in
this spec.


## Source baseline

Copy the readable `hypergen.js` and `websocket.js` inputs from the local Django-Hypergen
reference repository. Record the upstream commit used for the copy.

Preserve the upstream source initially, including behavior and exported names, except for
changes strictly required to make the local entry/output paths work. Avoid cleanup
refactors during the migration so differences between the old and new generated bundles
remain reviewable.

Do not carry the unused `mousetrap` dependency into Flask-Hypergen unless implementation
reveals an actual runtime use. `morphdom` and `sockette` are runtime inputs; Parcel is a
development/build dependency.

Preserve applicable upstream attribution and licensing notices when copying the source.
Add any repository-level notice or license material required for the copied MPL-2.0 source
rather than leaving provenance implicit in git history.


## Aube and toolchain policy

Aube is the only permitted package installer and package-script runner for this project.
Project documentation, `mise` tasks, CI, and contributor instructions must not direct
users to npm, npx, pnpm, Yarn, or Bun for this build.

Pin Node and Aube through the existing `mise` configuration and lock mechanism. Declare
Aube as the package manager in `package.json`. Use an Aube-native lockfile committed to
the repository.

The initial Aube lock graph should preserve the versions represented by the upstream build
used as the baseline. Dependency upgrades should happen only after the source migration is
verified, in a separate change where behavioral and supply-chain differences can be
reviewed independently.

Retain Aube's default-deny handling for dependency lifecycle scripts. The upstream Parcel
graph contains packages that declare install scripts, including native-support packages.
Start with no blanket approvals. If a clean build requires a dependency build:

- verify why the script is needed
- approve only the exact package or narrow package family required
- enable Aube's build jail where supported
- record the approval and rationale in the project configuration or adjacent documentation
- never enable all dependency lifecycle scripts globally

Retain or strengthen the repository's package-release cooling-period policy. A fresh or
updated resolution must also retain integrity verification and Aube's protections against
exotic transitive dependencies and trust downgrades.


## Build behavior

Provide project scripts and `mise` tasks for:

- a production build that writes the packaged bundle and source map
- a development watch build for client work
- a frozen clean install/build suitable for CI

The production build must have deterministic output for a fixed source, toolchain,
configuration, and lockfile. Running it twice should not change tracked files after the
first successful build.

Generated files must have a short header identifying them as generated and pointing
contributors to the readable source and build task, provided that adding the header does
not interfere with source-map correctness. Contributors should edit only `static-src`, not
the generated bundle.

The generated bundle remains committed because Python package builds and end-user
installations must not invoke a JavaScript toolchain. The Python packaging configuration
must continue to include the bundle and should include its source map when source maps are
enabled. Authored JavaScript source and JavaScript build dependencies do not need to be
installed into the runtime Python environment.


## Compatibility requirements

The migration must preserve:

- the `window.hypergen` namespace and its existing exports
- WebSocket support exposed at `window.hypergen.websocket`
- callback, command, morph, partial-load, history, form-value, coercion, file-upload, and
  readiness behavior
- the current Flask static asset URL and response content type
- current support for browsers exercised by the Playwright suite

Exact byte equality with the old bundle is desirable but not required because build
metadata, module ordering, or the source-map reference may change. Behavioral equivalence
is required. Any material generated-code difference must be attributable to the
source/build migration rather than an intentional feature change.


## Validation

Validate the migration with all of the following:

- install dependencies from the committed lockfile using Aube's frozen CI mode
- build from a clean checkout using the pinned `mise` toolchain
- rerun the production build and confirm that tracked generated files do not change
- run the existing Python request/unit test suite
- run the existing Playwright end-to-end tests, including callback increments and
  partial-load history navigation
- compare the old and new `window.hypergen` export names in a browser
- exercise WebSocket module loading sufficiently to confirm the bundle initializes without
  module or global-reference errors
- build both wheel and source distribution and inspect them for the required static assets
- load the source map in browser developer tools, when enabled, and confirm it resolves to
  the readable local source
- scan the final repository instructions and automation to confirm npm is not invoked

Add a CI or pre-commit-style validation that fails when authored JavaScript changes
without the generated asset being rebuilt. It should verify the build result rather than
duplicate the build implementation in a second script.


## Risks

- **Old Parcel graph:** The upstream Parcel 2.9.3 graph is old and contains several
  packages with install scripts. Aube may require narrow build approvals or expose
  compatibility problems.
- **Lockfile conversion:** Generating an Aube-native lockfile must not silently update the
  initial dependency versions. Compare the resolved graph with the upstream package lock.
- **Circular module structure:** The upstream main source imports its own module
  namespace. Preserve behavior during migration, but do not expand this pattern. A later
  client refactor can introduce a clearer entry module after equivalence is established.
- **Generated diff noise:** Parcel output may differ across tool versions or platforms.
  Pinning the toolchain and verifying clean rebuilds should make generated changes
  intentional.
- **Source-map packaging:** A source map can be much larger than the bundle. Correct
  debugging and provenance are preferred here, but a broken or irreproducible map should
  not be shipped.


## Completion criteria

This work is complete when readable source is committed, Aube can perform a frozen clean
install and reproducible Parcel build, the packaged static asset is generated from that
source, existing browser behavior passes automated tests, Python distributions contain the
required generated assets, and contributors no longer need to edit minified JavaScript.


## Implementation record

Update this section while executing the spec with:

- upstream commit copied
- chosen pinned Node, Aube, and Parcel versions
- dependency-script approvals and rationale, if any
- source-map decision
- validation commands and outcomes
- any intentional deviations from the source baseline
