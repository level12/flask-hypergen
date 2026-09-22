# Native form submission in flask-hypergen


## Goal

Allow a Hypergen action to submit a normal HTML form as `FormData`. This lets form
libraries render standard HTML inputs and process `request.form` without listing every
field as a callback argument.

This is a minimal first pass; avoid added complexity and defer edge cases until needed.


## Public API

Add a `form` option to `callback()`:

```python
with form(id_='profile-form', onsubmit=callback(save, form=True)):
    raw(wtform.hidden_tag())
    raw(wtform.name())
    button('Save', type_='submit')
```

`form=True` means the element receiving the callback must be a `<form>` with an explicit
ID. Submitting it invokes the action through Hypergen using the browser's `FormData`
collection behavior.


## Python changes

In `flask_hypergen.liveview.callback()`:

- Accept `form: bool = False`.
- When enabled, require the callback to be rendered on a form element with an explicit
  ID.
- Include that ID as `formId` in the generated callback options.
- Keep existing element-argument callbacks unchanged.

No special action decorator is needed. Form values remain available through Flask's
normal `request.form` and `request.files` interfaces; `hypergen_data` continues to carry
the callback arguments and metadata.


## Browser changes

In the readable JavaScript source:

- When `formId` is present, initialize the request body with
  `new FormData(document.getElementById(formId))` instead of an empty `FormData`.
- Append `hypergen_data` to that same object before posting.
- Preserve `preventDefault()`, callback blocking, error handling, headers, and timeout
  behavior.

Rebuild the generated JavaScript assets using the repository's existing build task; do
not edit minified assets directly.


## Required behavior

- Clicking a submit button and pressing Enter submit the form through the action.
- Repeated names remain repeated in `request.form`.
- Checkbox, radio, select, hidden, and CSRF inputs use native `FormData` behavior.
- File inputs appear in `request.files`.
- Existing callbacks without `form=True` behave exactly as before.


## Tests

Add focused tests covering:

- callback command rendering with `form=True`;
- rejection of `form=True` on a non-form element;
- JavaScript submission of representative fields, repeated names, and a file;
- coexistence of submitted form data and decoded Hypergen arguments;
- unchanged behavior for ordinary element callbacks.

Add one example using a standard HTML form. WTForms-specific integration code does not
belong in flask-hypergen.


## Implementation record

- Added `form=True` rendering validation and the `formId` callback option.
- Initialized browser requests from native `FormData` when `formId` is present.
- Added a standard HTML form example and focused unit, integration, and browser tests.
