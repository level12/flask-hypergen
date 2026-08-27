import examples.hellocoreonly as hellocoreonly
from flask_hypergen.liveview import dumps


def test_example_routes_render(client):
    checks = {
        '/auth/': 'Authentication example',
        '/hellocoreonly/counter': 'Core-only wiring',
        '/hellohypergen/counter': 'Decorator wiring',
        '/classviews/counter': 'Class-based view wiring',
        '/inputs/demo': 'Read values from the browser',
        '/commands/demo': 'Explicit command responses',
        '/apptemplate/counter': 'Context-manager base template',
        '/partialload/page1': 'Partial loading with history support',
        '/sqlalchemy-counter/counter': 'SQLAlchemy-backed state',
    }
    for path, marker in checks.items():
        response = client.get(path)
        body = response.get_data(as_text=True)
        assert response.status_code == 200
        assert marker in body
        assert '/flask_hypergen/static/hypergen.js' in body
        assert 'Flask adapter example for django-hypergen.' not in body


def test_example_index_lists_examples(client):
    response = client.get('/')
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'Flask-Hypergen Examples' in body
    assert '<table' in body
    assert '<th>Link</th>' not in body
    assert 'pico.azure.min.css' in body
    assert '><a href="/hellocoreonly/counter">Hello Core Only</a></td>' in body

    for href in (
        '/hellocoreonly/counter',
        '/hellohypergen/counter',
        '/classviews/counter',
        '/inputs/demo',
        '/commands/demo',
        '/apptemplate/counter',
        '/partialload/page1',
        '/auth/',
        '/sqlalchemy-counter/counter',
    ):
        assert f'href="{href}"' in body


def test_coreonly_increment_returns_commands(client):
    response = client.post('/hellocoreonly/increment', data={'hypergen_data': dumps({'args': [1]})})
    payload = response.get_data(as_text=True)
    assert response.status_code == 200
    assert response.mimetype == 'application/json'
    assert 'hypergen.morph' in payload
    assert 'Counter value' in payload


def test_coreonly_explicit_routes_support_function_reverse(app):
    with app.test_request_context():
        assert hellocoreonly.increment.reverse() == '/hellocoreonly/increment'


def test_hypergen_increment_returns_commands(client):
    response = client.post(
        '/hellohypergen/increment',
        data={'hypergen_data': dumps({'args': [1]})},
        headers={'Referer': 'http://localhost/hellohypergen/counter'},
    )
    payload = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'hypergen.morph' in payload
    assert 'Decorator wiring' in payload
    assert '/hellohypergen/increment",[2]' in payload


def test_classview_increment_returns_commands(client):
    response = client.post(
        '/classviews/increment',
        data={'hypergen_data': dumps({'args': [1]})},
        headers={'Referer': 'http://localhost/classviews/counter'},
    )
    payload = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'hypergen.morph' in payload
    assert 'Class-based view wiring' in payload
    assert '/classviews/increment",[2]' in payload


def test_classview_partial_load_returns_commands(client):
    response = client.post(
        '/classviews/counter',
        headers={'X-Hypergen-Partial': '1'},
    )
    payload = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'hypergen.morph' in payload
    assert 'Class-based view wiring' in payload


def test_inputs_submit_returns_summary(client):
    response = client.post(
        '/inputs/submit',
        data={'hypergen_data': dumps({'args': ['Ada', 37, True]})},
        headers={'Referer': 'http://localhost/inputs/demo'},
    )
    payload = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'Ada is 37 years old and subscribed=True' in payload


def test_inputs_demo_renders_non_empty_summary(client):
    response = client.get('/inputs/demo')
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert '<p id="summary">Submit the form to see a summary.</p>' in body


def test_commands_demo_returns_explicit_commands(client):
    response = client.post(
        '/commands/send-command',
        data={'hypergen_data': dumps({'args': []})},
        headers={'Referer': 'http://localhost/commands/demo'},
    )
    payload = response.get_data(as_text=True)
    assert response.status_code == 200
    assert payload.startswith('[[')
    assert 'Updated from an explicit command.' in payload


def test_apptemplate_increment_returns_commands(client):
    response = client.post(
        '/apptemplate/increment',
        data={'hypergen_data': dumps({'args': [1]})},
        headers={'Referer': 'http://localhost/apptemplate/counter'},
    )
    payload = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'Current value: 2' in payload
    assert '/apptemplate/increment",[2]' in payload


def test_sqlalchemy_counter_persists(client):
    first = client.get('/sqlalchemy-counter/counter').get_data(as_text=True)
    client.post(
        '/sqlalchemy-counter/increment',
        data={'hypergen_data': dumps({'args': [1]})},
        headers={'Referer': 'http://localhost/sqlalchemy-counter/counter'},
    )
    second = client.get('/sqlalchemy-counter/counter').get_data(as_text=True)
    assert 'Persisted value: 0' in first
    assert 'Persisted value: 1' in second


def test_liveview_partial_get_returns_json_commands(client):
    response = client.get('/hellohypergen/counter', headers={'X-Hypergen-Partial': '1'})
    assert response.status_code == 200
    assert response.mimetype == 'application/json'
    assert 'hypergen.morph' in response.get_data(as_text=True)


def test_partialload_links_enable_partial_navigation(client):
    response = client.get('/partialload/page1')
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'hypergen.partialLoad' in body
    assert 'Current page: page1' in body


def test_partialload_partial_get_returns_commands(client):
    response = client.get('/partialload/page2', headers={'X-Hypergen-Partial': '1'})
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert response.mimetype == 'application/json'
    assert 'hypergen.morph' in body
    assert 'Current page: page2' in body


def test_login_required_liveview_redirects_to_login(client):
    response = client.get('/auth/protected')
    assert response.status_code == 302
    assert '/auth/login' in response.headers['Location']
    assert 'next=' in response.headers['Location']


def test_login_route_and_protected_liveview(client):
    response = client.get('/auth/login?next=/auth/protected', follow_redirects=True)
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'This page requires an authenticated user.' in body
    assert 'Signed in as editor' in body


def test_auth_demo_starts_unauthenticated(client):
    response = client.get('/auth/')
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'Start here unauthenticated' in body
    assert 'Authenticate as editor' in body
    assert 'Signed in as editor' not in body


def test_logout_returns_to_public_auth_example(client):
    client.get('/auth/login?user=editor')
    response = client.get('/auth/logout', follow_redirects=True)
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'Start here unauthenticated' in body
    assert 'Authenticate as editor' in body
    assert 'Signed in as editor' not in body


def test_permission_protected_liveview_returns_403_for_authenticated_user_without_perm(client):
    client.get('/auth/login?user=viewer')
    response = client.get('/auth/editor')
    assert response.status_code == 403


def test_permission_protected_action_redirects_when_logged_out(client):
    response = client.post(
        '/auth/update',
        data={'hypergen_data': dumps({'args': ['Blocked']})},
        headers={'Referer': 'http://localhost/auth/editor'},
    )
    payload = response.get_data(as_text=True)
    assert response.status_code == 302
    assert response.mimetype == 'application/json'
    assert 'hypergen.redirect' in payload
    assert '/auth/login' in payload


def test_permission_protected_action_returns_403_for_authenticated_user_without_perm(client):
    client.get('/auth/login?user=viewer')
    response = client.post(
        '/auth/update',
        data={'hypergen_data': dumps({'args': ['Blocked']})},
        headers={'Referer': 'http://localhost/auth/editor'},
    )

    assert response.status_code == 403
    assert 'hypergen.redirect' not in response.get_data(as_text=True)


def test_permission_protected_action_succeeds_when_authorized(client):
    client.get('/auth/login?user=editor')
    response = client.post(
        '/auth/update',
        data={'hypergen_data': dumps({'args': ['Updated by an editor']})},
        headers={'Referer': 'http://localhost/auth/editor'},
    )
    payload = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'Updated by an editor' in payload
