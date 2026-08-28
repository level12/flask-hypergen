from __future__ import annotations

from dataclasses import dataclass

from flask import Blueprint, Response, url_for

from flask_hypergen import hypergen_to_response
from flask_hypergen.tags import (
    a,
    body,
    h1,
    head,
    html,
    link,
    main,
    meta,
    p,
    style,
    table,
    tbody,
    td,
    th,
    thead,
    title,
    tr,
)


bp = Blueprint('index', __name__)


@dataclass(frozen=True)
class ExampleCard:
    title: str
    endpoint: str
    description: str
    category: str


EXAMPLES: tuple[ExampleCard, ...] = (
    ExampleCard(
        'Hello Core Only',
        'hellocoreonly.counter',
        'Lowest-level Hypergen wiring with explicit Flask routes.',
        'Core',
    ),
    ExampleCard(
        'Hello Hypergen',
        'hellohypergen.counter',
        'Decorator-based liveview and action wiring with the familiar API names.',
        'Liveview',
    ),
    ExampleCard(
        'Class-Based Views',
        'classviews.counter',
        'Use HypergenMethodView classes for both a liveview page and its action.',
        'Liveview',
    ),
    ExampleCard(
        'Inputs',
        'inputs.demo',
        'Read browser values, coerce input types, and render a summary.',
        'Forms',
    ),
    ExampleCard(
        'Commands',
        'commands.demo',
        'Return explicit client commands instead of a full fragment render.',
        'Commands',
    ),
    ExampleCard(
        'App Template',
        'apptemplate.counter',
        'Use a shared app shell and target partial updates into the content area.',
        'Templates',
    ),
    ExampleCard(
        'Partial Load',
        'partialload.page1',
        'Navigate between pages while exercising partial loading and history support.',
        'Navigation',
    ),
    ExampleCard(
        'Auth',
        'auth.demo',
        'Start unauthenticated, then sign in to try the protected Flask-Login example.',
        'Auth',
    ),
    ExampleCard(
        'SQLAlchemy Counter',
        'sqlalchemy_counter.counter',
        'Persist counter state with a small typed SQLAlchemy 2.0 model.',
        'Database',
    ),
)


def index_template() -> None:
    html(lang='en')
    with head():
        meta(charset='utf-8')
        meta(name='viewport', content='width=device-width, initial-scale=1')
        meta(name='color-scheme', content='light dark')
        title('Flask-Hypergen Examples')
        link(
            rel='stylesheet',
            href='https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.azure.min.css',
        )
        style(
            """
            table.examples-table {
                border-collapse: collapse;
            }
            table.examples-table th,
            table.examples-table td {
                padding: 0.65rem 0.85rem;
                border: 1px solid var(--pico-muted-border-color);
                vertical-align: top;
            }
            table.examples-table th {
                border-bottom-width: 2px;
            }
            """,
        )
    with body(class_='examples-index'), main(class_='container'):
        h1('Flask-Hypergen Examples')
        p('A simple index of the example views in this package.')
        with table(role='grid', class_='examples-table'):
            with thead(), tr():
                th('View')
                th('Category')
                th('Description')
            with tbody():
                for example in EXAMPLES:
                    with tr():
                        td(a(example.title, href=url_for(example.endpoint)))
                        td(example.category)
                        td(example.description)


@bp.get('/')
def index() -> Response:
    return hypergen_to_response(index_template, settings={'liveview': False})
