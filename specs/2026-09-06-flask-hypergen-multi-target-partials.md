# Spec: Multi-target region updates for Flask-Hypergen

## Background

Flask-Hypergen currently supports partial page navigation and action responses by rendering HTML
into a single `target_id` and returning a `hypergen.morph` command. Applications often need one
request to refresh several independent areas of the document, such as:

- the main page content
- active navigation state
- flashed messages
- notification counts
- the document title

The desired workflow is similar to htmx 4's partial elements: the server declares multiple pieces
of response content, each piece identifies its destination, and the client applies all of them from
one response.

Reference: https://four.htmx.org/docs#partials-hx-partial

Hypergen should retain its JSON command protocol. It does not need to emit or parse literal
`<hx-partial>` elements. The Python renderer already knows which HTML belongs to which target and
can produce structured update commands directly.

## Existing foundation

The current implementation already has most of the low-level machinery:

- `TemplatePlugin` in `src/flask_hypergen/template.py` renders into a
  `contextlist('target_id')`.
- Changing `context.hypergen.target_id` routes generated HTML into a separate named buffer.
- `ActionPlugin.template_after()` in `src/flask_hypergen/liveview.py` iterates those buffers and
  emits a `hypergen.morph` command for each one.
- The browser runtime in `src/flask_hypergen/static/hypergen.js` can already morph, append,
  prepend, and remove DOM content.

This work should evolve those constructs rather than introduce a separate rendering system.

## Goal

Provide a first-class region API that allows the same page and layout code to:

1. render a complete HTML document for a normal request
2. render an ordered set of updates for multiple DOM targets on a partial request

This must work through the lower-level, explicit Flask route API. The `@liveview` decorator should
eventually use the same mechanism, but the core behavior must not depend on the decorator.

## Core rendering model

Hypergen should distinguish two rendering modes.

### Document mode

Document mode composes the base template and view and returns a complete HTML document. A declared
region emits a Hypergen-owned boundary around its normally rendered content.

Conceptually:

```python
with region('page-content'):
    with main(id_='page-content', class_='space-y-6'):
        accounts_page()
```

produces:

```html
<div data-hypergen-region="page-content" style="display: contents">
    <main id="page-content" class="space-y-6">
        <!-- accounts page -->
    </main>
</div>
```

The boundary is the stable update target and is owned entirely by Hypergen. Its
`data-hypergen-region` value is the logical region name. The inline `display: contents` makes the
default boundary layout-neutral, including when the region has no content. Content renderers remain
responsible only for application markup and do not need to know the region name or DOM locator.

### Partial-update mode

Partial-update mode must also compose and execute the base template and view. This differs from the
current partial liveview path, which renders only the view function.

When the renderer encounters the same `region()` declaration in partial-update mode, it captures
the complete generated region boundary as an update. The client finds the existing boundary by its
`data-hypergen-region` value and inner-morphs its children from the returned boundary. The returned
content may have zero, one, or multiple root elements.

Output outside declared regions is discarded unless the caller explicitly supplies a main
target. This allows document scaffolding such as `html`, `head`, `body`, and layout wrappers to run
without becoming part of the partial response.

Rendering the base template in both modes is essential. It allows layout-owned regions such as the
sidebar, messages, and title to be recalculated on every navigation without moving their rendering
logic into each page view.

## Terminology

- A `region` is a stable, named area of a document and an update boundary in a template.
- A `RegionUpdate` contains new content and an update strategy for a region.
- A partial request asks the server for incremental output rather than a complete document.
- A partial response contains one or more region updates.

Use `partial` only for request/response and rendering-mode terminology. Do not use it as the name
of the template primitive: regions also participate in full document rendering, and `partial`
commonly refers to a reusable subtemplate.

## Public region API

Add a public context-manager-style primitive named `region`. It must support:

- a stable logical name written to the boundary's `data-hypergen-region` attribute
- an optional boundary tag for HTML contexts where the default `div` is not valid
- an update strategy, designed for future expansion

Example layout:

```python
@contextmanager
def document(title_text):
    doctype()
    with html(lang='en'):
        with head():
            with region('document-title', tag=title):
                raw(f'{title_text} | ynabr')

        with body():
            with region('sidebar'):
                sidebar(active_endpoint=request.endpoint)

            with div(class_='page-shell'):
                with region('messages'):
                    messages()

                with region('page-content'):
                    yield
```

The view may emit any normal Hypergen content inside the page-content region. Functions such as
`sidebar()` and `messages()` may render zero, one, or multiple elements. They do not need to render
a particular outer element or ID. Applications must not need parallel `sidebar_content()` or
`message_content()` implementations for partial rendering.

The default boundary emitted by `region('messages')` is:

```html
<div data-hypergen-region="messages" style="display: contents">
    <!-- output from messages(), if any -->
</div>
```

`data-hypergen-region` is reserved for boundaries created by this feature. Region names must be
non-empty, and separate `region()` declarations must not use the same name in one document.

The optional `tag` argument lets Hypergen own an element that is valid in a restricted or semantic
HTML context. For example, `region('document-title', tag=title)` produces a `<title>` whose
`data-hypergen-region` value is `document-title`. The `display: contents` style is a property of the
default `div` boundary and should not automatically be added to an explicitly selected tag.

The default update strategy is an inner morph of the boundary. The boundary itself remains stable;
the component elements within it, including their attributes, are still reconciled by the morph.
A `RegionUpdate` carries the complete generated boundary so the client can validate the response
before extracting and morphing its children. The update representation should leave room for an
explicit outer morph or other strategies later, but they are not required initially.

The public primitive should not require callers to manipulate `context.hypergen.target_id`
directly.

## Update representation

Represent region updates as ordered records rather than only as a dictionary keyed by region name.
The model needs, at minimum:

```python
@dataclass
class RegionUpdate:
    region_name: str
    html: str
    swap: str
```

Ordering must follow declaration/render order. The representation should allow additional swap
strategies later without changing the overall response contract.

For the initial implementation, use the existing children-only morph behavior for region updates.
Design the API to accommodate outer morph, append, prepend, delete, replacement, and CSS selectors,
but do not implement all htmx swap behavior in the first version.

## Partial response contract

Return region updates using Hypergen's JSON command response. Prefer one batch command over a
sequence of unrelated morph commands:

```json
[
  [
    "hypergen.applyUpdates",
    [
      {
        "region": "document-title",
        "swap": "inner-morph",
        "html": "<generated document-title boundary>"
      },
      {
        "region": "sidebar",
        "swap": "inner-morph",
        "html": "<generated sidebar boundary>"
      },
      {
        "region": "messages",
        "swap": "inner-morph",
        "html": "<generated empty messages boundary>"
      },
      {
        "region": "page-content",
        "swap": "inner-morph",
        "html": "<generated page-content boundary>"
      }
    ]
  ]
]
```

The `html` values above are abbreviated for readability. Each actual value contains the complete
generated boundary, including its region name, marker, inline style when applicable, and rendered
children.

The exact serialized field naming should be consistent with the existing JavaScript API.

Before changing the DOM, the client should enumerate elements bearing `data-hypergen-region` and
build a map keyed by their exact attribute values. This avoids interpolating region names into CSS
selectors and makes duplicate detection explicit. It should parse and validate every update before
applying any of them so an invalid update does not leave the page half-updated.

Validation includes exactly one existing boundary for each requested name, exactly one returned
boundary element, a returned `data-hypergen-region` value matching `region`, and a returned tag
matching the existing boundary. The client should then apply updates in declaration order and emit
useful before/after events for the batch and, if helpful, individual regions.

Autofocus/focus restoration should happen once after the batch rather than once for every region.
Existing morph behavior for focused form controls and scripts should be preserved.

## Region semantics

The following behavior is required:

- A declared region is updated even when it has no children. Its update still contains the empty
  Hypergen-owned boundary, which clears the existing boundary's children while retaining the
  boundary itself.
- A region not declared during a partial-update render remains unchanged in the browser.
- Two updates for the same region in one render are an error unless a future swap mode explicitly
  defines useful repeated-region behavior.
- Nested region updates are rejected initially. Updating a parent and its descendant in one batch
  has ambiguous overwrite behavior.
- A region's content may render zero, one, or multiple root elements.
- Hypergen, rather than the region's content, must render the single boundary root in the response.
- Region names must be unique during document rendering and in the existing browser document.
- A partial render that produces neither a main update nor any declared regions should fail loudly
  in development rather than silently returning a no-op response.

The default boundary is layout-neutral, but it remains present in the DOM. CSS selectors such as
`:empty`, direct-child selectors, and structural pseudo-classes still observe it. Applications
should put presentation, semantics, accessibility attributes, and event handlers on region content
rather than relying on the default boundary as an application component.

The current `if into:` check in `ActionPlugin` is insufficient because it cannot distinguish an
absent region from a declared region with no children. The generated boundary and explicit
update record must retain that distinction.

## Main content plus additional regions

Support both of these response shapes:

1. Pure partial response: only explicitly declared regions are updated.
2. Main-plus-regions response: unmarked view output updates an explicitly supplied main target,
   while declared regions update additional targets.

When no main target is supplied, unmarked output is discarded in partial-update mode. This is the
mode expected for rendering a complete base template solely to collect its declared regions.

Existing single-target action behavior must remain backward compatible.

## Render settings and helpers

Add an explicit partial-update render mode rather than treating page navigation as an action. The
internal implementation may replace the current `liveview`/`action` booleans with a render-mode
enum or layer a compatible setting over them.

The lower-level API should support a flow equivalent to:

```python
if is_hypergen_partial_request(request):
    return hypergen_partial_response(
        page_template,
        base_template=document(title_text),
    )

return hypergen_to_response(
    page_template,
    settings={
        'liveview': True,
        'base_template': document(title_text),
    },
)
```

Names for convenience helpers can be chosen to fit the library, but request detection and response
construction should be available publicly. Users should not need to recreate private decorator
logic to use explicit Flask routes.

After the lower-level API is stable, refactor `@liveview` to delegate to it rather than maintaining
a second partial-rendering path.

## Navigation requests

Separate page navigation from action callbacks in the browser runtime.

- Partial page navigation should issue `GET` with the existing partial-request header.
- Hypergen callbacks/actions should remain `POST`.
- A new or revised navigation function should support push, replace, and no-history behavior.
- Popstate handling should request the historical URL without pushing another history entry.
- A normal anchor `href` must remain valid so navigation works without JavaScript and supports a
  full-page refresh.

The existing POST-based `hypergen.partialLoad()` should remain temporarily compatible, but new
partial links should use GET-based navigation. Applications should not have to declare POST support
on read-only page routes.

## Event-handler state

Rendering multiple regions must preserve correct Hypergen callback behavior:

- callbacks rendered into any updated region must be registered before users can invoke them
- callbacks belonging to untouched regions must remain registered
- callbacks removed from replaced regions should not accumulate indefinitely in client state

The implementation can choose how to scope or prune callback state, but tests must cover callbacks
in both updated and untouched regions.

## Example application

Update or add a partial-navigation example that uses explicit Flask routes before demonstrating the
decorator API. It should have at least these independent regions:

- document title
- navigation with active-page styling
- message/notification area that can be cleared with an empty region update
- main page content

Navigation should update all four regions in one response. Direct visits and refreshes must return
a valid complete document. Browser back and forward must restore the same visible state through
partial GET requests.

## Testing expectations

Add focused tests for:

- full document rendering of all declared region containers and content
- names, markers, tags, and inline styles on generated region boundaries
- partial-update rendering of complete region boundaries for multiple ordered targets
- inner morphs extracting zero, one, or multiple content roots from the returned boundary
- rejection of malformed boundaries, mismatched region names, missing markers, and tag mismatches
- rendering and applying an explicitly empty region
- region content that does not know or match the region name
- leaving an undeclared region unchanged
- duplicate and nested target validation
- missing-region batch validation without incomplete DOM mutation
- callbacks in multiple updated regions
- preservation of callbacks in untouched regions
- explicit Flask GET routes returning full or partial responses based on the request header
- GET-based link navigation and no-JavaScript-compatible `href` values
- push-state and back/forward navigation
- backward compatibility for existing single-target liveviews and actions

Use request-level tests for server contracts and Playwright coverage for DOM, focus, and history
behavior. Update existing command-payload assertions where the new batch command intentionally
changes the representation.

## Suggested implementation order

1. Formalize region update records and expose a minimal `region(name)` primitive that captures
   a fragment inside a generated, stable boundary.
2. Generate and apply an inner-morph batch of multiple updates, including regions with zero, one,
   or multiple content roots.
3. Add document versus partial-update rendering behavior to `region()`.
4. Support alternate Hypergen-owned boundary tags for restricted HTML contexts.
5. Execute the base template during partial-update rendering and discard unmarked document output.
6. Add public explicit-route request/response helpers.
7. Add GET-based client navigation and history handling.
8. Refactor `@liveview` to use the same core path.
9. Add richer swap strategies only after the multi-target morph workflow is stable.

## Out of scope for the first implementation

- complete parity with every htmx swap strategy
- arbitrary CSS selectors as targets
- streaming region-update batches
- nested region updates
- request-time selection of only a subset of declared regions

The internal model should leave room for these features without making them prerequisites for the
initial multi-target page-navigation workflow.
