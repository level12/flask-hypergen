from __future__ import annotations

from flask import Blueprint

from examples.common import make_base_template
from flask_hypergen import NO_PERM_REQUIRED, action, callback, liveview
from flask_hypergen.tags import button, form, h2, input_, label, option, p, select


bp = Blueprint('forms', __name__, url_prefix='/forms')
BASE_TEMPLATE = make_base_template('Native Form Submission')


def form_template(summary: str | None = None) -> None:
    h2('Submit standard HTML fields')
    with form(id_='native-form', onsubmit=callback(submit, 'callback argument', form=True)):
        input_(name='csrf_token', type_='hidden', value='example-token')
        label('Name', input_(id_='form-name', name='name', value='Ada'))
        label('First tag', input_(name='tag', value='python'))
        label('Second tag', input_(name='tag', value='flask'))
        label('Subscribed', input_(name='subscribed', type_='checkbox', value='yes'))
        label('Email', input_(name='contact', type_='radio', value='email', checked=True))
        label('Phone', input_(name='contact', type_='radio', value='phone'))
        with select(name='color'):
            option('Blue', value='blue')
            option('Green', value='green')
        label('Attachment', input_(id_='form-file', name='attachment', type_='file'))
        button('Save', id_='form-submit', type_='submit')
    p(summary or 'Submit the form to inspect its native fields.', id_='form-summary')


@liveview(bp, '/demo', perm=NO_PERM_REQUIRED, base_template=BASE_TEMPLATE)
def demo(request) -> None:
    form_template()


@action(bp, '/submit', perm=NO_PERM_REQUIRED, target_id='content', base_view=demo)
def submit(request, callback_argument: str) -> None:
    tags = ','.join(request.form.getlist('tag'))
    filename = request.files['attachment'].filename if 'attachment' in request.files else 'none'
    summary = (
        f'name={request.form.get("name", "")}; tags={tags}; '
        f'subscribed={request.form.get("subscribed", "no")}; '
        f'contact={request.form.get("contact", "")}; color={request.form.get("color", "")}; '
        f'csrf={request.form.get("csrf_token", "")}; file={filename}; arg={callback_argument}'
    )
    form_template(summary)
