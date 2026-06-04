from contextlib import contextmanager
from datetime import date, datetime, time
import re
from types import SimpleNamespace
from unittest import mock

from pyrsistent import pmap
import pytest
from werkzeug.exceptions import Forbidden

from examples.common import make_base_template
import flask_hypergen
from flask_hypergen import (
    FULL,
    LOGIN_REQUIRED,
    NO_PERM_REQUIRED,
    THIS,
    action,
    call_js,
    check_perms,
    command,
    component,
    doctype,
    dumps,
    hypergen,
    liveview,
    loads,
)
from flask_hypergen.context import (
    ContextMiddleware,
    context,
    context_init_app,
    context_middleware,
    context_values_build,
    contextlist,
    user_resolve,
)
from flask_hypergen.hypergen import (
    autourl_register,
    autourls,
    compare_funcs,
    is_collection,
    make_string,
    metastr,
    plugins_exit_stack,
    plugins_method_call,
    plugins_pipeline,
    resolve_url,
    route_register,
    wrap2,
)
from flask_hypergen.liveview import (
    LiveviewPlugin,
    LiveviewPluginBase,
    _request_header,
    _request_path,
    decoder,
    encoder,
    url_is_active,
)
from flask_hypergen.liveview import callback as cb
from flask_hypergen.tags import (
    a,
    body,
    div,
    h1,
    h2,
    head,
    html,
    input_,
    li,
    p,
    select,
    span,
    td,
    textarea,
    title,
    tr,
    ul,
)
from flask_hypergen.template import (
    OMIT,
    TemplatePlugin,
    add_class,
    hprint,
    join_html,
    on_url,
    raw,
    write,
)
from flask_hypergen.template import html_indent as html_indent_

from .conftest import (
    HttpResponse,
    Request,
    User,
    hypergen_context,
    mock_hypergen_callback,
    mock_middleware,
)


def normalized_html():
    return re.sub(r'[0-9]{5,}', '1234', join_html(context.hypergen.into))


def test_context():
    context.replace(request=Request(), user=User())
    assert context.request.user.id == 1
    assert 'request' in context
    context['feature_flag'] = True
    assert context.feature_flag is True


def test_context_cm():
    def inc(ctx):
        return ctx.set('i', ctx.get('i', 0) + 1)

    with context(inc):
        assert context['i'] == 1
        with context(inc, foo=9):
            assert context['foo'] == 9
            assert context['i'] == 2
            with context(bar=42):
                assert context['i'] == 2
                assert context['bar'] == 42
            assert context['i'] == 2
        assert context['i'] == 1
        assert 'foo' not in context


def test_context_immutable():
    with context(my_appname=pmap({'title': 'foo', 'items': [1, 2, 3]})):
        with context(at='my_appname', items=[4, 5]):
            assert context.my_appname['title'] == 'foo'
            assert context['my_appname']['items'] == [4, 5]
        assert context['my_appname']['items'] == [1, 2, 3]


def test_context_mutable_update_should_fail():
    with (
        context(my_appname={'title': 'foo', 'items': [1, 2, 3]}),
        pytest.raises(TypeError, match='Not immutable context variable attempted updated'),
        context(at='my_appname', items=[4, 5]),
    ):
        pass


def test_context_at_creation():
    with context(at='my_appname', title='foo', items=[1, 2, 3]):
        with context(at='my_appname', items=[4, 5]):
            assert context['my_appname']['title'] == 'foo'
            assert context['my_appname']['items'] == [4, 5]
        assert context['my_appname']['items'] == [1, 2, 3]


def test_context_at_empty_nesting():
    with context(at='my_appname'):
        with context(at='my_appname'):
            assert context['my_appname'] == pmap()
        assert context['my_appname'] == pmap()


def test_context_middleware():
    def view(request):
        assert context.user.pk == 1
        assert context['request'].user.pk == 1
        return HttpResponse()

    context_middleware(lambda request: view(request))(Request())


def test_check_perms_any_perm_matches_subset():
    request = Request()
    request.user.permissions = frozenset({'examples.view'})

    result = check_perms(request, ('examples.edit', 'examples.view'), any_perm=True)

    assert result.ok is True
    assert result.matched_perms == {'examples.view'}


def test_check_perms_raise_exception_for_login_required():
    request = Request()
    request.user.is_authenticated = False

    with pytest.raises(Forbidden):
        check_perms(request, LOGIN_REQUIRED, raise_exception=True)


@pytest.mark.xfail(
    reason='Django legacy middleware compatibility is intentionally not part of flask_hypergen',
)
def test_context_middleware_old():
    raise AssertionError()


def test_element():
    with context(at='hypergen', **hypergen_context()):
        div('hello world!')
        assert join_html(context.hypergen.into) == '<div>hello world!</div>'
    with context(at='hypergen', **hypergen_context()):
        with div('a', class_='foo'):
            div('b', x_foo=42)
        assert normalized_html() == '<div class="foo">a<div x-foo="42">b</div></div>'
    with context(at='hypergen', **hypergen_context()):

        @div('a', class_='foo')
        def f1():
            div('b', x_foo=42)

        f1()
        assert normalized_html() == '<div class="foo">a<div x-foo="42">b</div></div>'
    with context(at='hypergen', **hypergen_context()):
        div('a', None, div('b', x_foo=42), class_='foo')
        assert normalized_html() == '<div class="foo">a<div x-foo="42">b</div></div>'
    with context(at='hypergen', **hypergen_context()):
        div(None, [1, 2], sep='-')
        assert normalized_html() == '<div>1-2</div>'
    with context(at='hypergen', **hypergen_context()):
        ul([li([li(y) for y in range(3, 4)]) for _x in range(1, 2)])
        assert normalized_html() == '<ul><li><li>3</li></li></ul>'
    with context(at='hypergen', **hypergen_context()):
        ul(li(li(y) for y in range(3, 4)) for _x in range(1, 2))
        assert normalized_html() == '<ul><li><li>3</li></li></ul>'
    with context(at='hypergen', **hypergen_context()):
        div([1, 2], div(1, 2, div(1, None, 2, ul([li(x) for x in range(1, 3)]))))
        assert (
            normalized_html()
            == '<div>12<div>12<div>12<ul><li>1</li><li>2</li></ul></div></div></div>'
        )
    with context(at='hypergen', **hypergen_context()):
        ul(
            None,
            [
                li(None, (li(li(z) for z in range(1, 2)) for _y in range(3, 4)), None)
                for _x in range(5, 6)
            ],
            None,
        )
        assert normalized_html() == '<ul><li><li><li>1</li></li></li></ul>'


def test_live_element():
    with context(is_test=True):

        @mock_hypergen_callback
        def my_callback():
            pass

        with context(is_test=True, at='hypergen', **hypergen_context()):
            div('hello world!', onclick=cb('my_url', 42), id_='i1')
            assert (
                normalized_html() == '<div onclick="hypergen.event(event, \'i1__onclick\')" '
                'id="i1">hello world!</div>'
            )
        with context(is_test=True, at='hypergen', **hypergen_context()):
            source = input_(name='a', id_='field-a')
            input_(name='b', id_='field-b', onclick=cb(my_callback, source))
            assert normalized_html() == (
                '<input name="a" id="field-a"/><input name="b" id="field-b" '
                'onclick="hypergen.event(event, \'field-b__onclick\')"/>'
            )
        with context(is_test=True, at='hypergen', **hypergen_context()):
            message = textarea(placeholder='myplace', id_='message-input')
            with div(class_='message'):
                with div(class_='action-left'):
                    span('Annullér', class_='clickable')
                with div(class_='action-right'):
                    span(
                        'Send',
                        class_='clickable',
                        onclick=cb(my_callback, message),
                        id_='send-message',
                    )
                div(message, class_='form form-write')
            assert normalized_html() == (
                '<div class="message"><div class="action-left">'
                '<span class="clickable">Annullér</span></div>'
                '<div class="action-right"><span class="clickable" '
                'onclick="hypergen.event(event, \'send-message__onclick\')" '
                'id="send-message">Send</span></div>'
                '<div class="form form-write"><textarea placeholder="myplace" '
                'id="message-input"></textarea></div></div>'
            )
        with context(is_test=True, at='hypergen', **hypergen_context()):
            input_(autofocus=True)
            assert join_html(context.hypergen.into) == '<input autofocus/>'


def test_live_element2():
    with context(is_test=True):

        @mock_hypergen_callback
        def my_callback():
            pass

        with context(is_test=True, at='hypergen', **hypergen_context()):
            el1 = input_(
                id_='id_new_password',
                placeholder='Adgangskode',
                oninput=cb(my_callback, THIS, ''),
            )
            el2 = input_(
                id_='el2',
                placeholder='Gentag Adgangskode',
                oninput=cb(my_callback, THIS, el1),
            )
            h2('Skift Adgangskode')
            p('Rules:')
            with div(class_='form'), div():
                with ul(id_='password_verification_smartassness'):
                    div('TODO')
                with div(class_='form'):
                    div(el1, class_='form-field')
                    div(el2, class_='form-field')
                    div('Skift adgangskode', class_='button disabled')
            assert normalized_html() == (
                '<h2>Skift Adgangskode</h2><p>Rules:</p><div class="form"><div>'
                '<ul id="password_verification_smartassness"><div>TODO</div></ul>'
                '<div class="form"><div class="form-field"><input id="id_new_password" '
                'placeholder="Adgangskode" '
                'oninput="hypergen.event(event, \'id_new_password__oninput\')"/></div>'
                '<div class="form-field"><input id="el2" '
                'placeholder="Gentag Adgangskode" '
                'oninput="hypergen.event(event, \'el2__oninput\')"/></div>'
                '<div class="button disabled">'
                'Skift adgangskode</div></div></div></div>'
            )


def test_callback():
    with context(is_test=True, at='hypergen', **hypergen_context()):

        @mock_hypergen_callback
        def f1(foo, punk=300):
            pass

        element = input_(oninput=cb(f1, THIS, 200, debounce=500), id_='testcb')
        assert isinstance(cb('foo', 42, debounce=42)(element, 'oninput', 92), list)


def test_components():
    def f1():
        div('a')

    @component
    def f2():
        div('a')

    with context(is_test=True, at='hypergen', **hypergen_context()):
        div(1, f1(), 2)
        assert normalized_html() == '<div>a</div><div>12</div>'
    with context(is_test=True, at='hypergen', **hypergen_context()):
        div(1, f2(), 2)
        assert normalized_html() == '<div>1<div>a</div>2</div>'


def test_components2():
    @component
    def comp1():
        @component
        def comp2():
            input_(value='a')

        comp2()

    with context(is_test=True, at='hypergen', **hypergen_context()):
        with tr():
            td(comp1())
        assert normalized_html() == '<tr><td><input value="a"/></td></tr>'
    with context(is_test=True, at='hypergen', **hypergen_context()):
        with tr(), td():
            comp1()
        assert normalized_html() == '<tr><td><input value="a"/></td></tr>'


def test_js_value_func():
    @mock_middleware()
    def inner():
        def template():
            body()
            i = input_()
            assert (i.js_value_func, i.js_coerce_func) == ('hypergen.read.value', None)
            i = input_(js_value_func='a', js_coerce_func='b')
            assert (i.js_value_func, i.js_coerce_func) == ('a', 'b')
            i = input_(js_value_func='a', coerce_to=float)
            assert (i.js_value_func, i.js_coerce_func) == ('a', 'hypergen.coerce.float')
            i = input_(js_value_func='a', coerce_to=int)
            assert (i.js_value_func, i.js_coerce_func) == ('a', 'hypergen.coerce.int')
            i = input_(js_value_func='a', coerce_to=str)
            assert (i.js_value_func, i.js_coerce_func) == ('a', 'hypergen.coerce.str')
            i = input_(js_value_func='a', type='date')
            assert (i.js_value_func, i.js_coerce_func) == ('a', 'hypergen.coerce.date')
            i = input_(js_value_func='a', type_='datetime-local')
            assert (i.js_value_func, i.js_coerce_func) == ('a', 'hypergen.coerce.datetime')
            i = input_(js_value_func='a', type_='weidewokvocxkokwoekvd')
            assert (i.js_value_func, i.js_coerce_func) == ('a', None)

        hypergen(template, settings={'action': True, 'target_id': 'foo'})
        hypergen(template, settings={'liveview': True, 'target_id': 'foo'})

    inner()


def test_eventhandler_cache():
    @mock_middleware()
    def inner():
        def template():
            body()
            input_(onclick=cb('/path/to/cb/', THIS), id_='tec')
            handlers = dict(enumerate(context.hypergen.event_handler_callbacks.values()))
            assert dumps(handlers) == (
                '{"0":["hypergen.callback","/path/to/cb/",[["_","element_value",'
                '["hypergen.read.value",null,"tec"]]],{"debounce":0,"confirm_":false,'
                '"blocks":false,"uploadFiles":false,"clear":false,"elementId":"tec",'
                '"debug":false,"meta":{},"headers":{},"blocksEachUrl":true,"timeout":20000}]}'
            )

        hypergen(template, settings={'liveview': True, 'target_id': 'foo'})
        hypergen(template, settings={'action': True, 'target_id': 'foo'})

    inner()


def test_call_js():
    @mock_middleware()
    def inner():
        def template():
            body()
            a(onclick=call_js('hypergen.xyz', THIS), id_='tcj')
            assert dumps(list(context.hypergen.event_handler_callbacks.values())) == (
                '[["hypergen.xyz",["_","element_value",["hypergen.read.value",null,"tcj"]]]]'
            )

        hypergen(template, settings={'liveview': True, 'target_id': 'foo'})
        hypergen(template, settings={'action': True, 'target_id': 'foo'})

    inner()


def test_command_prepend():
    with context(at='hypergen', **hypergen_context()):
        command('hypergen.appended')
        command('hypergen.prepended', prepend=True)

        assert list(context.hypergen.commands) == [
            ['hypergen.prepended'],
            ['hypergen.appended'],
        ]


def test_repr():
    with context(is_test=True, at='hypergen', **hypergen_context()):
        el1 = input_(id_='el1')
        el2 = input_(onclick=cb('alert', el1), id_='el2')
        assert (
            repr(el2) == 'input_(onclick=callback("alert", input_(id_="el1"), '
            'blocksEachUrl=True, timeout=20000), id_="el2")'
        )


def test_attribute_escapes_double_quote():
    with context(at='hypergen', **hypergen_context()):
        div('hi', title='a "b" c')
        assert normalized_html() == '<div title="a &quot;b&quot; c">hi</div>'


def test_plugins_exit_stack_uses_method_name():
    entered = []

    class FakePlugin:
        @contextmanager
        def custom(self):
            entered.append('enter')
            yield
            entered.append('exit')

    ctx = hypergen_context()
    ctx['plugins'] = [FakePlugin()]
    with context(at='hypergen', **ctx), plugins_exit_stack('custom'):
        assert entered == ['enter']
    assert entered == ['enter', 'exit']


def test_action_sets_original_func():
    def my_action(request, foo, bar):
        return None

    decorated = action(perm=NO_PERM_REQUIRED)(my_action)
    assert decorated.original_func is my_action


def test_liveview_sets_original_func():
    def my_view(request, foo, bar):
        return None

    decorated = liveview(perm=NO_PERM_REQUIRED)(my_view)
    assert decorated.original_func is my_view


def test_serialization():
    payload = {
        'string': 'hi',
        'int': 42,
        'float': 9.9,
        'list': [1, 2, 3],
        'range': range(1, 10, 2),
        'dict': {'key': 'value'},
        'set': {1, 2, 3},
        'frozenset': frozenset({1, 2, 3}),
        'date': date(2022, 1, 1),
        'datetime': datetime(2022, 1, 1, 10, 11, 23),
        'time': time(10, 11, 23),
    }
    assert loads(dumps(payload)) == payload


def test_loads_integer_keys():
    assert loads('{"1":{"_":["tuple",[1,2]]},"two":2}', integer_keys=True) == {
        1: (1, 2),
        'two': 2,
    }


@mock_middleware()
def test_plugins():
    def template(n):
        with html():
            with head():
                title(2)
            with body():
                h1('4')

    def template2(n):
        html(head(title(2)), body(h1('4')))

    html1 = hypergen(
        template,
        2,
        settings={'plugins': [TemplatePlugin(), LiveviewPlugin()], 'indent': True},
    )
    html2 = hypergen(
        template2,
        2,
        settings={'plugins': [TemplatePlugin(), LiveviewPlugin()], 'indent': True},
    )
    expected_html = '\n'.join(
        [
            '<html>',
            '    <head>',
            '        <!--hypergen_liveview_media-->',
            '        <script src="/flask_hypergen/static/hypergen.js"></script>',
            '        <script type="application/json" id="hypergen-apply-commands-data">'
            '{"_":["deque",[["hypergen.setClientState","hypergen.eventHandlerCallbacks",{}],'
            '["history.replaceState",{"callback_url":"mock"},"","mock"]]]}</script>',
            '        <script>',
            '                hypergen.ready(() => hypergen.applyCommands('
            'JSON.parse(document.getElementById(',
            "                    'hypergen-apply-commands-data').textContent, hypergen.reviver)))",
            '            </script>',
            '        <title>',
            '            2',
            '        </title>',
            '    </head>',
            '    <body>',
            '        <h1>',
            '            4',
            '        </h1>',
            '    </body>',
            '</html>',
        ],
    )
    assert html1.strip() == html2.strip() == expected_html


def test_flask_hypergen_public_api():
    exported = set(dir(flask_hypergen))
    assert {
        'ContextMiddleware',
        'LOGIN_REQUIRED',
        'NO_PERM_REQUIRED',
        'TemplatePlugin',
        'action',
        'callback',
        'command',
        'context',
        'context_init_app',
        'context_middleware',
        'contextlist',
        'hypergen',
        'init_app',
        'liveview',
        'route_register',
    } <= exported


def test_multilist():
    with context(at='hypergen'):
        into = contextlist('target_id')
        into.append(1)
        assert into == [1]
    with context(at='hypergen', target_id='bar'):
        into.append(2)
        into.append(3)
    assert into.contexts == {'__default_context__': [1], 'bar': [2, 3]}


@mock_middleware()
def test_multitargets():
    def template():
        p('main')
        with context(at='hypergen', target_id='foo'):
            p('foo1')
        with context(at='hypergen', target_id='bar'):
            p('bar1')

    full = hypergen(template, settings={'returns': FULL})
    assert full['html'] == '<p>main</p>'
    assert {k: join_html(v) for k, v in full['context'].hypergen.into.contexts.items()} == {
        '__default_context__': '<p>main</p>',
        'foo': '<p>foo1</p>',
        'bar': '<p>bar1</p>',
    }


@mock_middleware()
def test_inject_html():
    def template1():
        doctype()
        with html():
            a('b')

    def template2():
        a('b')

    x = hypergen(template1, settings={'liveview': True, 'indent': True}).strip()
    y = hypergen(template2, settings={'liveview': True, 'indent': True}).strip()
    assert '<script src="/flask_hypergen/static/hypergen.js"></script>' in x
    assert '<head>' in x and '<a>' in x
    assert y.startswith('<!--hypergen_liveview_media-->')


def foo():
    def bar():
        pass

    return bar


def foz():
    def bar():
        pass

    return bar


def alt_template_factory():
    @contextmanager
    def alt_template():
        yield

    return alt_template


def test_function_equality():
    a, b, c = foo(), foo(), foz()
    assert not compare_funcs(make_base_template('one'), alt_template_factory())
    assert compare_funcs(a, b)
    assert not compare_funcs(a, foo)
    assert not compare_funcs(a, c)


def test_make_string():
    assert make_string(None) == ''
    assert make_string(42) == '42'
    assert make_string('x') == 'x'


def test_is_collection():
    assert is_collection('abc') is False
    assert is_collection(metastr('abc')) is False
    assert is_collection([1, 2]) is True
    assert is_collection((1,)) is True
    assert is_collection({1}) is True
    assert is_collection(5) is False


def test_metastr_make():
    value = metastr.make('hello', {'base_template': None})
    assert value == 'hello'
    assert value.meta == {'base_template': None}


def test_wrap2_both_forms():
    @wrap2
    def deco(func, suffix='!'):
        def inner(*a, **k):
            return func(*a, **k) + suffix

        return inner

    @deco
    def plain():
        return 'a'

    @deco(suffix='?')
    def configured():
        return 'b'

    assert plain() == 'a!'
    assert plain.__name__ == 'plain'
    assert configured() == 'b?'
    assert configured.__name__ == 'configured'


def test_check_perms_no_perm_required():
    assert check_perms(Request(), NO_PERM_REQUIRED).ok is True


def test_check_perms_all_perms_required():
    request = Request()
    request.user.permissions = frozenset({'a', 'b'})

    result = check_perms(request, ('a', 'b'))

    assert result.ok is True
    assert result.matched_perms == {'a', 'b'}


def test_check_perms_missing_perm_returns_403():
    request = Request()
    request.user.permissions = frozenset({'a'})

    result = check_perms(request, ('a', 'b'))

    assert result.ok is False
    assert result.response.status_code == 403


def test_check_perms_raise_exception_on_missing_perm():
    request = Request()
    request.user.permissions = frozenset()

    with pytest.raises(Forbidden):
        check_perms(request, 'a', raise_exception=True)


def test_check_perms_falls_back_to_has_perm():
    class SingleCheckUser:
        is_authenticated = True

        def has_perm(self, name):
            return name == 'a'

    request = Request()
    request.user = SingleCheckUser()

    assert check_perms(request, 'a').ok is True
    assert check_perms(request, 'b').ok is False


def test_check_perms_login_redirect_includes_next():
    request = Request()
    request.user.is_authenticated = False

    result = check_perms(request, LOGIN_REQUIRED, login_url='/login')

    assert result.ok is False
    assert result.response.status_code == 302
    assert 'next=' in result.response.location


def test_check_perms_empty_login_target_returns_403():
    request = Request()
    request.user.is_authenticated = False

    result = check_perms(request, LOGIN_REQUIRED, login_url='')

    assert result.response.status_code == 403


def test_autourl_register_and_autourls():
    def registered_view(request):
        return None

    autourl_register(registered_view, path='/x/')
    module = SimpleNamespace(__name__=registered_view.__module__)

    items = autourls(module, 'ns')
    assert any(item[0] is registered_view for item in items)
    assert autourls(module, '') == []


def test_route_register_resolve_and_reverse():
    from flask import Flask

    from flask_hypergen import init_app

    app = Flask(__name__)
    init_app(app)

    def my_view(request):
        return None

    func_obj = route_register(app, my_view, rule='/myview/', methods=['GET', 'POST'])

    assert func_obj.supports_hypergen_callback is True
    assert func_obj.hypergen_endpoint == 'my_view'

    with app.app_context():
        match = resolve_url('/myview/')
    assert match.func is func_obj
    assert match.kwargs == {}

    with app.test_request_context():
        url = func_obj.reverse()
    assert url == '/myview/'
    assert url.meta == {'base_template': None}

    with pytest.raises(TypeError, match='Too many positional'):
        func_obj.reverse('extra')


def test_plugins_method_call_and_pipeline():
    calls = []

    class Recorder:
        def note(self, msg):
            calls.append(msg)

        def process(self, data, suffix=''):
            return data + suffix

    class Empty:
        pass

    ctx = hypergen_context()
    ctx['plugins'] = [Recorder(), Empty()]
    with context(at='hypergen', **ctx):
        plugins_method_call('note', 'hi')
        result = plugins_pipeline('process', 'x', {'suffix': '!'})

    assert calls == ['hi']
    assert result == 'x!'


def test_context_at_with_transformer():
    def shout_title(m):
        return m.set('title', m['title'].upper())

    with context(at='app', title='foo'):
        with context(shout_title, at='app', items=[1]):
            assert context['app']['title'] == 'FOO'
            assert context['app']['items'] == [1]
        assert context['app']['title'] == 'foo'


def test_user_resolve_from_request():
    request = Request()
    assert user_resolve(request) is request.user


def test_context_values_build_omits_none_user():
    values = context_values_build(SimpleNamespace())
    assert 'user' not in values
    assert 'request' in values


def test_context_middleware_class():
    request = Request()
    ContextMiddleware().process_request(request)
    assert context.request is request
    assert context.user is request.user


def test_context_init_app_idempotent(app):
    assert app.extensions.get('flask_hypergen_context_init') is True
    context_init_app(app)
    assert app.extensions.get('flask_hypergen_context_init') is True


def test_contextlist_default_without_hypergen():
    context.replace()
    cl = contextlist('target_id')
    cl.append('x')
    assert cl.contexts['__default_context__'] == ['x']


def test_add_class():
    assert add_class('', 'a') == 'a'
    assert add_class(None, 'a') == 'a'
    assert add_class(OMIT, 'a') == 'a'
    assert add_class('a', 'b') == 'a b'
    assert add_class(' a ', 'b') == 'a b'
    assert add_class(['a'], 'b') == ['a', 'b']
    assert add_class({'a'}, 'b') == {'a', 'b'}


def test_add_class_invalid_type():
    with pytest.raises(Exception, match="don't know how to add"):
        add_class(42, 'b')


def test_write_escapes_and_raw_does_not():
    with context(at='hypergen', **hypergen_context()):
        write('<b>')
        assert join_html(context.hypergen.into) == '&lt;b&gt;'
    with context(at='hypergen', **hypergen_context()):
        raw('<b>')
        assert join_html(context.hypergen.into) == '<b>'


def test_input_datetime_value_formatting():
    with context(at='hypergen', **hypergen_context()):
        input_(type_='datetime-local', value=datetime(2022, 3, 4, 5, 6, 7), id_='dt')
        assert 'value="2022-03-04T05:06:07"' in normalized_html()
    with context(at='hypergen', **hypergen_context()):
        input_(type_='month', value={'year': 2022, 'month': 3}, id_='mo')
        assert 'value="2022-03"' in normalized_html()
    with context(at='hypergen', **hypergen_context()):
        input_(type_='week', value={'year': 2022, 'week': 9}, id_='wk')
        assert 'value="2022-W09"' in normalized_html()


def test_hprint_single_and_multi():
    with context(at='hypergen', **hypergen_context()):
        hprint({'a': 1})
        out = join_html(context.hypergen.into)
        assert '<div' in out and 'dict' in out
    with context(at='hypergen', **hypergen_context()):
        hprint(1, 2, key='v')
        out = join_html(context.hypergen.into)
        assert 'arg' in out and 'key' in out


def test_html_indent_requires_yattag():
    with (
        mock.patch('flask_hypergen.template.yattag_ok', False),
        pytest.raises(Exception, match='yattag'),
    ):
        html_indent_('<div></div>')


def test_request_header_sources():
    assert _request_header(SimpleNamespace(headers={'X-Test': 'h'}), 'X-Test') == 'h'
    assert _request_header(SimpleNamespace(META={'HTTP_X_TEST': 'm'}), 'X-Test') == 'm'
    assert _request_header(SimpleNamespace(environ={'HTTP_X_TEST': 'e'}), 'X-Test') == 'e'
    assert _request_header(SimpleNamespace(headers={}, environ={}), 'X-Test') is None


def test_request_path_sources():
    assert _request_path(SimpleNamespace(full_path='/a/b?')) == '/a/b'
    assert _request_path(SimpleNamespace(get_full_path=lambda: '/c')) == '/c'
    assert _request_path(SimpleNamespace(path='/d')) == '/d'


def test_command_return_form():
    item = command('hypergen.foo', 1, 2, return_=True)
    assert item == ['hypergen.foo', 1, 2]


def test_encoder_rejects_unknown_type():
    with pytest.raises(TypeError):
        encoder(object())


def test_decoder_passthrough_and_unknown():
    assert decoder({'x': 1}) == {'x': 1}
    assert decoder({'_': ['notalist']}) == {'_': ['notalist']}
    with pytest.raises(Exception, match='Unknown datatype'):
        decoder({'_': ['bogus', 1]})


def test_wrap_element_init_coerce_error():
    with context(at='hypergen', **hypergen_context()):
        element = input_(id_='ci')
        with (
            pytest.raises(Exception, match='coerce must be one of'),
            LiveviewPluginBase().wrap_element_init(element, [], {'coerce_to': object()}),
        ):
            pass


def test_wrap_element_init_select_multiple():
    with context(at='hypergen', **hypergen_context()):
        element = select(id_='s1', multiple=True)
        with LiveviewPluginBase().wrap_element_init(
            element,
            [],
            {'multiple': True, 'coerce_to': int},
        ):
            pass
        assert element.js_value_func == 'hypergen.read.selectMultiple'
        assert element.js_coerce_func == 'hypergen.coerce.intlist'


def test_wrap_element_init_select_multiple_unsupported_coerce():
    with context(at='hypergen', **hypergen_context()):
        element = select(id_='s2', multiple=True)
        with (
            pytest.raises(Exception, match='not yet implemented'),
            LiveviewPluginBase().wrap_element_init(
                element,
                [],
                {'multiple': True, 'coerce_to': float},
            ),
        ):
            pass


def test_wrap_element_init_a_partial_load():
    base_template = make_base_template('one')
    href = metastr.make('/x/', {'base_template': base_template})
    ctx = hypergen_context()
    ctx['partial_base_template'] = base_template
    with context(at='hypergen', **ctx):
        element = a('link', href=href, id_='ap')
        attrs = {'href': href}
        with LiveviewPluginBase().wrap_element_init(element, [], attrs):
            pass
        assert attrs['onclick'] == f"hypergen.partialLoad(event, '{href}', true)"


def test_url_is_active_on_url_and_a_class_active():
    from flask import Flask

    from flask_hypergen import init_app

    app = Flask(__name__)
    init_app(app)

    def active_view(request):
        return None

    def inactive_view(request):
        return None

    route_register(app, active_view, rule='/active/', methods=['GET'])
    route_register(app, inactive_view, rule='/inactive/', methods=['GET'])

    with app.test_request_context('/active/'):
        ctx = hypergen_context()
        ctx['liveview_resolver_match'] = resolve_url('/active/')
        with context(at='hypergen', **ctx):
            assert url_is_active('/active/') is True
            assert url_is_active('/inactive/') is False
            assert on_url('/active/') is True
            assert on_url('/inactive/', 'Y', 'N') == 'N'
            a('x', href='/active/', class_active='on', id_='lnk')
            a('y', href='/inactive/', class_active='on', id_='lnk2')
            html = normalized_html()
            assert 'class="on"' in html
            assert '<a href="/inactive/" id="lnk2">y</a>' in html


def test_context_setattr():
    context.replace()
    context.custom = 7
    assert context.custom == 7


def test_user_resolve_handles_missing_flask_login():
    import sys

    with mock.patch.dict(sys.modules, {'flask_login': None}):
        assert user_resolve(SimpleNamespace()) is None


def test_user_resolve_handles_runtime_error():
    fake = mock.Mock()
    fake._get_current_object.side_effect = RuntimeError
    with mock.patch('flask_login.current_user', fake):
        assert user_resolve(SimpleNamespace()) is None


def test_liveview_resolver_match_edges():
    from flask_hypergen.liveview import liveview_resolver_match

    context.replace(request=SimpleNamespace(endpoint=None, view_args={}))
    assert liveview_resolver_match().func is None

    context.replace(request=SimpleNamespace(headers={}, environ={}))
    assert liveview_resolver_match(for_action=True) is None


def test_liveview_partial_requires_target_id():
    def base(view):
        return view

    with pytest.raises(Exception, match='requires a target_id'):
        liveview(base_template=base, perm=NO_PERM_REQUIRED)(lambda request: None)


def test_action_partial_requires_target_id():
    def base(view):
        return view

    with pytest.raises(Exception, match='requires a target_id'):
        action(base_template=base, perm=NO_PERM_REQUIRED)(lambda request: None)


def test_element_id_from_tuple():
    with context(at='hypergen', **hypergen_context()):
        div('x', id_=('a', 'b'))
        assert 'id="a-b"' in normalized_html()


def test_element_class_list_attribute():
    with context(at='hypergen', **hypergen_context()):
        div('x', class_=['a', 'b'])
        assert 'class="a b"' in normalized_html()


def test_element_callable_child_and_end_char():
    with context(at='hypergen', **hypergen_context()):
        div(lambda: 'cb', end='!')
        assert normalized_html() == '<div>cb!</div>'


def test_join_html_callable_and_generator():
    with context(at='hypergen', **hypergen_context()):
        assert join_html([lambda: 'x', (str(i) for i in range(2))]) == 'x01'


def test_input_radio_requires_name():
    with (
        context(at='hypergen', **hypergen_context()),
        pytest.raises(AssertionError, match='Name must be set'),
    ):
        input_(type_='radio')


def test_repr_includes_this():
    with context(is_test=True, at='hypergen', **hypergen_context()):

        @mock_hypergen_callback
        def fn():
            pass

        element = input_(onclick=cb(fn, THIS), id_='rt')
        assert 'THIS' in repr(element)


def test_callback_confirm_alias():
    with context(is_test=True, at='hypergen', **hypergen_context()):

        @mock_hypergen_callback
        def fn():
            pass

        input_(onclick=cb(fn, confirm=True), id_='cc')
        handler = next(iter(context.hypergen.event_handler_callbacks.values()))
        assert handler[3]['confirm_'] is True


def test_wrap_element_init_select_multiple_str():
    with context(at='hypergen', **hypergen_context()):
        element = select(id_='s4', multiple=True)
        with LiveviewPluginBase().wrap_element_init(
            element,
            [],
            {'multiple': True, 'coerce_to': str},
        ):
            pass
        assert element.js_value_func == 'hypergen.read.selectMultiple'
        assert element.js_coerce_func == 'hypergen.coerce.str'


def test_wrap_element_init_select_single():
    with context(at='hypergen', **hypergen_context()):
        element = select(id_='s5')
        with LiveviewPluginBase().wrap_element_init(element, [], {}):
            pass
        assert element.js_value_func == 'hypergen.read.value'


def test_wrap_element_init_a_partial_no_base_template():
    href = metastr.make('/x/', {'base_template': None})
    with context(at='hypergen', **hypergen_context()):
        element = a('l', href=href, id_='ap2')
        attrs = {'href': href}
        with LiveviewPluginBase().wrap_element_init(element, [], attrs):
            pass
        assert 'onclick' not in attrs


def test_wrap_element_init_a_partial_mismatched_base_template():
    href = metastr.make('/x/', {'base_template': make_base_template('one')})
    with context(at='hypergen', **hypergen_context()):
        element = a('l', href=href, id_='ap3')
        attrs = {'href': href}
        with LiveviewPluginBase().wrap_element_init(element, [], attrs):
            pass
        assert 'onclick' not in attrs


def test_check_perms_any_perm_no_match_returns_403():
    request = Request()
    request.user.permissions = frozenset()

    result = check_perms(request, ('a', 'b'), any_perm=True)

    assert result.ok is False
    assert result.response.status_code == 403


def test_check_perms_redirects_to_login_manager_view(app):
    request = Request()
    request.user.is_authenticated = False
    with app.test_request_context('/protected'):
        result = check_perms(request, LOGIN_REQUIRED)
    assert result.response.status_code == 302
    assert 'login' in result.response.location.lower()


def test_plugins_exit_stack_skips_missing_method():
    class WithMethod:
        @contextmanager
        def custom(self):
            yield

    class WithoutMethod:
        pass

    ctx = hypergen_context()
    ctx['plugins'] = [WithoutMethod(), WithMethod()]
    with context(at='hypergen', **ctx), plugins_exit_stack('custom'):
        pass


def test_init_app_idempotent_blueprint(app):
    from flask_hypergen import init_app

    init_app(app)
    assert app.extensions['flask_hypergen'] is True


def test_void_element_as_context_manager():
    with context(at='hypergen', **hypergen_context()):
        with input_(id_='vd'):
            pass
        assert normalized_html() == '<input id="vd"/>'


def test_rst_requires_docutils():
    from flask_hypergen.template import rst

    with pytest.raises(Exception, match='docutils'):
        rst('hello')


def test_imports_flat_namespace():
    from flask_hypergen import imports as flat

    assert 'hypergen' in flat.__all__
    assert 'context' in flat.__all__
    assert flat.hypergen is hypergen
    for name in flat.__all__:
        assert hasattr(flat, name)


def test_appstate_plugin_persists_in_session(app):
    from flask_hypergen.plugins.appstate import AppstatePlugin

    plugin = AppstatePlugin('myns', lambda: {'count': 0})
    with app.test_request_context('/'):
        with plugin.context():
            assert context.hypergen.appstate == {'count': 0}
            context.hypergen.appstate['count'] = 5
        with plugin.context():
            assert context.hypergen.appstate['count'] == 5


def test_plugins_build_includes_appstate():
    from flask_hypergen.plugins.appstate import AppstatePlugin
    from flask_hypergen.template import plugins_build, settings_load

    settings = settings_load({'appstate': lambda: {'count': 0}, 'namespace': 'ns'})
    plugins = plugins_build(settings)

    assert any(isinstance(plugin, AppstatePlugin) for plugin in plugins)


def test_liveview_returns_response_via_client():
    from flask import Flask, Response

    from flask_hypergen import init_app

    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'x'
    init_app(app)

    def view(request):
        return Response('hi', status=201)

    liveview(app, rule='/lvresp/', perm=NO_PERM_REQUIRED, partial=False)(view)
    resp = app.test_client().get('/lvresp/')
    assert resp.status_code == 201
    assert resp.data == b'hi'


def test_liveview_partial_redirect_via_client():
    from flask import Flask, redirect

    from flask_hypergen import init_app

    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'x'
    init_app(app)

    def view(request):
        return redirect('/elsewhere/')

    liveview(app, rule='/lvredir/', perm=NO_PERM_REQUIRED, target_id='t')(view)
    resp = app.test_client().get('/lvredir/', headers={'X-Hypergen-Partial': '1'})
    assert resp.status_code == 302
    assert b'hypergen.redirect' in resp.data


def test_action_returns_response_via_client():
    from flask import Flask, Response

    from flask_hypergen import init_app

    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'x'
    init_app(app)

    def act(request):
        return Response('done', status=202)

    action(app, rule='/actresp/', perm=NO_PERM_REQUIRED, target_id='t')(act)
    resp = app.test_client().post('/actresp/', data={'hypergen_data': dumps({'args': []})})
    assert resp.status_code == 202
    assert resp.data == b'done'


def test_action_returns_redirect_via_client():
    from flask import Flask, redirect

    from flask_hypergen import init_app

    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'x'
    init_app(app)

    def act(request):
        return redirect('/elsewhere/')

    action(app, rule='/actredir/', perm=NO_PERM_REQUIRED, target_id='t')(act)
    resp = app.test_client().post('/actredir/', data={'hypergen_data': dumps({'args': []})})
    assert resp.status_code == 302
    assert b'hypergen.redirect' in resp.data


def test_action_with_base_view_via_client():
    from flask import Flask

    from flask_hypergen import init_app
    from flask_hypergen.tags import div

    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'x'
    init_app(app)

    def page(request):
        div('sidebar', id_='side')

    base = liveview(app, rule='/page/', perm=NO_PERM_REQUIRED, partial=False, target_id='side')(
        page,
    )

    def act(request):
        div('main', id_='main')

    action(app, rule='/act/', perm=NO_PERM_REQUIRED, target_id='main', base_view=base)(act)

    resp = app.test_client().post(
        '/act/',
        data={'hypergen_data': dumps({'args': []})},
        headers={'Referer': '/page/'},
    )
    assert resp.status_code == 200
    assert b'hypergen.morph' in resp.data
