from functools import wraps
from typing import ClassVar

from flask import Flask
from flask.testing import FlaskClient

from flask_hypergen import (
    NO_PERM_REQUIRED,
    ActionOptions,
    HypergenEndpointKind,
    HypergenMethodView,
    LiveviewOptions,
    callback,
    dumps,
    loads,
)
from flask_hypergen.tags import button, div, p


class TestHypergenMethodView:
    def test_liveview_and_action_protocols(self, app: Flask, client: FlaskClient) -> None:
        class Page(HypergenMethodView):
            hypergen_options = LiveviewOptions(perm=NO_PERM_REQUIRED)
            render_count = 0

            def get(self) -> None:
                type(self).render_count += 1
                div('Counter page', id_='page')

        page_view = Page.register(app, '/class-counter', endpoint='class-counter')

        class Increment(HypergenMethodView):
            hypergen_options = ActionOptions(
                perm=NO_PERM_REQUIRED,
                target_id='counter',
                base_view=page_view,
            )

            def post(self, amount: int) -> None:
                div(f'Value: {amount}', id_='counter')

        action_view = Increment.register(
            app,
            '/class-counter/increment',
            endpoint='class-counter-increment',
        )

        response = client.get('/class-counter')

        assert response.status_code == 200
        assert b'Counter page' in response.data
        assert b'/flask_hypergen/static/hypergen.js' in response.data
        assert page_view.is_hypergen_liveview is True
        assert page_view.supports_hypergen_callback is False
        assert page_view.hypergen_kind is HypergenEndpointKind.LIVEVIEW

        response = client.post(
            '/class-counter/increment',
            data={'hypergen_data': dumps({'args': [3]})},
            headers={'Referer': '/class-counter'},
        )

        assert response.status_code == 200
        assert ['hypergen.morph', 'counter', '<div id="counter">Value: 3</div>'] in (
            loads(response.data)
        )
        assert action_view.is_hypergen_liveview is False
        assert action_view.supports_hypergen_callback is True
        assert action_view.hypergen_kind is HypergenEndpointKind.ACTION
        assert Page.render_count == 2

        with app.test_request_context():
            assert page_view.reverse() == '/class-counter'
            assert action_view.reverse() == '/class-counter/increment'

    def test_callback_accepts_registered_action(self, app: Flask, client: FlaskClient) -> None:
        class Save(HypergenMethodView):
            hypergen_options = ActionOptions(perm=NO_PERM_REQUIRED, target_id='result')

            def post(self, value: str) -> None:
                p(value, id_='result')

        save_view = Save.register(app, '/class-save', endpoint='class-save')

        class Form(HypergenMethodView):
            hypergen_options = LiveviewOptions(perm=NO_PERM_REQUIRED)

            def get(self) -> None:
                button('Save', id_='save', onclick=callback(save_view, 'saved'))

        Form.register(app, '/class-form', endpoint='class-form')

        response = client.get('/class-form')

        assert response.status_code == 200
        assert b'hypergen.event' in response.data
        assert b'/class-save' in response.data

    def test_standard_class_decorators_are_preserved(
        self,
        app: Flask,
        client: FlaskClient,
    ) -> None:
        calls = []

        def record(view):
            @wraps(view)
            def decorated(**kwargs):
                calls.append('decorated')
                return view(**kwargs)

            return decorated

        class DecoratedView(HypergenMethodView):
            decorators: ClassVar = [record]
            hypergen_options = LiveviewOptions(perm=NO_PERM_REQUIRED)

            def get(self) -> None:
                p('view')

        DecoratedView.register(app, '/decorated-class-view', endpoint='decorated-class-view')

        response = client.get('/decorated-class-view')

        assert response.status_code == 200
        assert calls == ['decorated']

    def test_partial_load_post_uses_get_handler(
        self,
        app: Flask,
        client: FlaskClient,
    ) -> None:
        calls = []

        class Page(HypergenMethodView):
            hypergen_options = LiveviewOptions(
                perm=NO_PERM_REQUIRED,
                target_id='content',
            )

            def get(self) -> None:
                calls.append('get')
                div('Partial page', id_='content')

            def post(self) -> None:
                calls.append('post')
                div('Ordinary POST', id_='content')

        Page.register(app, '/partial-class-view', endpoint='partial-class-view')

        response = client.post(
            '/partial-class-view',
            headers={'X-Hypergen-Partial': '1'},
        )

        assert response.status_code == 200
        assert ['hypergen.morph', 'content', '<div id="content">Partial page</div>'] in loads(
            response.data,
        )
        assert calls == ['get']

        response = client.post('/partial-class-view')

        assert response.status_code == 200
        assert b'Ordinary POST' in response.data
        assert calls == ['get', 'post']

    def test_partial_load_adds_post_to_get_only_view(
        self,
        app: Flask,
        client: FlaskClient,
    ) -> None:
        class Page(HypergenMethodView):
            hypergen_options = LiveviewOptions(
                perm=NO_PERM_REQUIRED,
                target_id='content',
            )

            def get(self) -> None:
                div('Partial page', id_='content')

        Page.register(app, '/get-only-class-view', endpoint='get-only-class-view')

        response = client.post(
            '/get-only-class-view',
            headers={'X-Hypergen-Partial': '1'},
        )

        assert response.status_code == 200
        assert ['hypergen.morph', 'content', '<div id="content">Partial page</div>'] in loads(
            response.data,
        )

    def test_reverse_positional_url_argument(self, app: Flask) -> None:
        class Detail(HypergenMethodView):
            hypergen_options = LiveviewOptions(perm=NO_PERM_REQUIRED)

            def get(self, item_id: int) -> None:
                p(f'Item {item_id}')

        detail_view = Detail.register(
            app,
            '/class-items/<int:item_id>',
            endpoint='class-item-detail',
        )

        with app.test_request_context():
            assert detail_view.reverse(5) == '/class-items/5'

    def test_register_options_override_class_options(
        self,
        app: Flask,
        client: FlaskClient,
    ) -> None:
        class Configurable(HypergenMethodView):
            hypergen_options = ActionOptions(perm=NO_PERM_REQUIRED, target_id='unused')

            def get(self) -> None:
                p('Overridden to liveview')

        view = Configurable.register(
            app,
            '/overridden-class-view',
            endpoint='overridden-class-view',
            options=LiveviewOptions(perm=NO_PERM_REQUIRED),
        )

        response = client.get('/overridden-class-view')

        assert response.status_code == 200
        assert b'Overridden to liveview' in response.data
        assert view.hypergen_kind is HypergenEndpointKind.LIVEVIEW
