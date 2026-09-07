from contextlib import contextmanager

from flask import Flask, request

import flask_hypergen
from flask_hypergen import call_js, region, write
from flask_hypergen.tags import a, body, button, head, html, input_, nav, p, title


PARTIAL_HEADER = 'X-Hypergen-Partial'


def create_region_test_app() -> Flask:
    app = Flask(__name__)
    app.config.update(SECRET_KEY='region-tests', TESTING=True)
    flask_hypergen.init_app(app)

    @app.get('/regions/<page_name>')
    def region_page(page_name: str):
        if page_name not in {'one', 'two', 'three'}:
            return 'Not found', 404

        base_template = region_base_template(page_name)

        def page_template():
            p(f'Current page: {page_name}', id_='current-page')
            input_(id_='focus-field', value=f'Value from {page_name}')
            button(
                f'Record {page_name}',
                id_='updated-callback',
                onclick=call_js('regionTest.record', f'updated-{page_name}'),
            )

        if flask_hypergen.is_hypergen_partial_request(request):
            return flask_hypergen.hypergen_partial_response(
                page_template,
                base_template=base_template,
            )
        return flask_hypergen.hypergen_to_response(
            page_template,
            settings={'base_template': base_template, 'liveview': True},
        )

    return app


def region_base_template(page_name: str):
    @contextmanager
    def base_template():
        flask_hypergen.doctype()
        with html():
            with head(), region('document-title', tag=title):
                write(f'Page {page_name} | Region tests')
            with body():
                with region('navigation'):
                    nav(
                        navigation_link('one', history='push'),
                        navigation_link('two', history='push'),
                        navigation_link('three', history='replace'),
                        navigation_link('three', history='none', link_id='no-history-three'),
                        button(
                            f'Record navigation {page_name}',
                            id_='navigation-callback',
                            onclick=call_js('regionTest.record', f'navigation-{page_name}'),
                        ),
                        data_active_page=page_name,
                    )
                with region('messages'):
                    if page_name == 'one':
                        p('Welcome from page one', id_='message')
                        button(
                            'Removed on navigation',
                            id_='removed-callback',
                            onclick=call_js('regionTest.record', 'removed'),
                        )
                if request.headers.get(PARTIAL_HEADER) != '1':
                    with region('untouched'):
                        button(
                            'Record untouched',
                            id_='untouched-callback',
                            onclick=call_js('regionTest.record', 'untouched'),
                        )
                with region('page-content'):
                    yield

    return base_template


def navigation_link(
    page_name: str,
    *,
    history: str,
    link_id: str | None = None,
):
    href = f'/regions/{page_name}'
    return a(
        f'Page {page_name}',
        href=href,
        id_=link_id or f'{history}-{page_name}',
        onclick=f"hypergen.navigate(event, this.href, '{history}')",
    )
