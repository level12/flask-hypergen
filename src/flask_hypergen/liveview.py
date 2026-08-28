from __future__ import annotations

from collections import deque
from collections.abc import Callable, Collection
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from datetime import time as dt_time
from enum import StrEnum
from functools import wraps
import json
from typing import Any, ClassVar, Protocol, TypeGuard, cast

from flask import Blueprint, Flask, Response, abort, current_app, has_app_context
from flask import request as flask_request
from flask.views import MethodView

from flask_hypergen.context import c, context, context_init_app, contextlist
import flask_hypergen.hypergen as hypergen_mod
from flask_hypergen.hypergen import (
    NamedCallable,
    ResolverMatch,
    RoutableCallable,
    check_perms,
    compare_funcs,
    metastr,
    resolve_url,
    route_register,
    t,
    wrap2,
)
from flask_hypergen.template import (
    FULL,
    HypergenResult,
    a,
    base_element,
    hypergen,
    input_,
    join_html,
    raw,
    script,
    select,
)


__all__ = sorted(
    [
        'ASSETS_BLUEPRINT',
        'ActionPlugin',
        'COERCE',
        'EVENT',
        'JS_COERCE_FUNCS',
        'JS_VALUE_FUNCS',
        'LOGIN_REQUIRED',
        'ActionOptions',
        'HypergenEndpointKind',
        'HypergenOptions',
        'HypergenMethodView',
        'LiveviewPlugin',
        'LiveviewOptions',
        'NO_PERM_REQUIRED',
        'THIS',
        'action',
        'call_js',
        'callback',
        'command',
        'decoder',
        'dumps',
        'encoder',
        'init_app',
        'json_commands_response',
        'liveview',
        'loads',
        'url_is_active',
    ],
)


class THIS:
    pass


class EVENT:
    pass


LOGIN_REQUIRED = '__LOGIN_REQUIRED__'
NO_PERM_REQUIRED = '__NO_PERM_REQUIRED__'
COERCE = {str: 'hypergen.coerce.str', int: 'hypergen.coerce.int', float: 'hypergen.coerce.float'}
JS_VALUE_FUNCS = {
    'checkbox': 'hypergen.read.checked',
    'radio': 'hypergen.read.radio',
    'file': 'hypergen.read.file',
}
JS_COERCE_FUNCS = {
    'month': 'hypergen.coerce.month',
    'number': 'hypergen.coerce.int',
    'range': 'hypergen.coerce.float',
    'week': 'hypergen.coerce.week',
    'date': 'hypergen.coerce.date',
    'time': 'hypergen.coerce.time',
}
JS_COERCE_FUNCS['datetime-local'] = 'hypergen.coerce.datetime'
ASSETS_BLUEPRINT = Blueprint(
    'flask_hypergen',
    __name__,
    static_folder='static',
    static_url_path='/flask_hypergen/static',
)


def init_app(app: Flask) -> Flask:
    context_init_app(app)
    if ASSETS_BLUEPRINT.name not in app.blueprints:
        app.register_blueprint(ASSETS_BLUEPRINT)
    app.extensions['flask_hypergen'] = True
    return app


def _request_header(request: Any, key: str) -> Any:
    if hasattr(request, 'headers'):
        value = request.headers.get(key)
        if value:
            return value
    meta = getattr(request, 'META', {})
    env_key = f'HTTP_{key.upper().replace("-", "_")}'
    if env_key in meta:
        return meta[env_key]
    environ = getattr(request, 'environ', {})
    return environ.get(env_key)


def _request_path(request: Any) -> str:
    if hasattr(request, 'full_path'):
        return request.full_path.rstrip('?')
    if hasattr(request, 'get_full_path'):
        return request.get_full_path()
    return getattr(request, 'path', '/')


def _static_hypergen_path() -> str:
    if has_app_context() and 'flask_hypergen' in current_app.blueprints:
        assert ASSETS_BLUEPRINT.static_url_path is not None
        return ASSETS_BLUEPRINT.static_url_path + '/hypergen.js'
    return '/flask_hypergen/static/hypergen.js'


def liveview_resolver_match(for_action: bool = False) -> ResolverMatch | None:
    if not for_action:
        endpoint = getattr(c.request, 'endpoint', None)
        kwargs = getattr(c.request, 'view_args', {}) or {}
        kwargs_dict = kwargs if isinstance(kwargs, dict) else {}
        if isinstance(endpoint, str):
            return ResolverMatch(func=hypergen_mod._ENDPOINTS.get(endpoint), kwargs=kwargs_dict)
        return ResolverMatch(func=None, kwargs=kwargs_dict)
    for header in ['X-Pathname', 'Referer']:
        value = _request_header(c.request, header)
        if value:
            return resolve_url(value)
    return None


def url_is_active(url: str) -> bool:
    current = context.hypergen.liveview_resolver_match
    target = resolve_url(url)
    return bool(current and target and current.func is target.func)


def callback_redirect_response(response: Response) -> Response:
    return json_commands_response(
        [['hypergen.redirect', response.location]],
        status=response.status_code,
    )


def namespace_resolve(func: Callable[..., Any]) -> str:
    return getattr(func, 'hypergen_endpoint', getattr(func, '__name__', 'hypergen'))


class BaseViewCallable(RoutableCallable, Protocol):
    original_func: Callable[..., Any]
    hypergen_render: Callable[..., Any]
    hypergen_kind: HypergenEndpointKind


class LiveviewCallable(BaseViewCallable, Protocol):
    is_hypergen_liveview: bool


class ActionCallable(BaseViewCallable, Protocol):
    pass


class CallbackTarget(NamedCallable, Protocol):
    supports_hypergen_callback: bool

    def reverse(self) -> str: ...


class CallbackRenderer(Protocol):
    hypergen_callback_signature: tuple[str, tuple[Any, ...], dict[str, Any]]

    def __call__(self, element: base_element, key: str, value: Any) -> list[Any]: ...


class HypergenEndpointKind(StrEnum):
    LIVEVIEW = 'liveview'
    ACTION = 'action'


@dataclass(frozen=True, kw_only=True)
class HypergenOptions:
    """Options shared by liveviews and actions."""

    base_template: Callable[..., Any] | None = None
    target_id: str | None = None
    perm: str | tuple[str, ...] | None = None
    any_perm: bool = False
    login_url: str | None = None
    raise_exception: bool = False
    redirect_field_name: str | None = None
    partial: bool = True
    appstate: Any = None
    user_plugins: tuple[object, ...] = ()

    def resolve_rendering(
        self,
        func: Callable[..., Any],
    ) -> tuple[str | None, Callable[..., Any] | None]:
        """Validate and resolve options shared by liveviews and actions."""
        if self.perm != NO_PERM_REQUIRED:
            assert self.perm, 'perm is a required keyword argument'
        target_id = self.target_id
        if target_id is None:
            target_id = getattr(self.base_template, 'target_id', None)
        if self.base_template and self.partial and not target_id:
            raise Exception(f'{func}: Partial loading requires a target_id.')
        partial_base_template = self.base_template if self.partial else None
        return target_id, partial_base_template


@dataclass(frozen=True, kw_only=True)
class LiveviewOptions(HypergenOptions):
    """Rendering options for a liveview function or ``HypergenMethodView``."""


@dataclass(frozen=True, kw_only=True)
class ActionOptions(HypergenOptions):
    """Rendering options for an action function or ``HypergenMethodView``."""

    base_view: BaseViewCallable | None = None


def _hypergen_html(template: Callable[..., Any]) -> str:
    html = hypergen(template)
    assert isinstance(html, str)
    return html


class LiveviewPluginBase:
    @contextmanager
    def wrap_element_init(
        self,
        element: base_element,
        children: list[Any],
        attrs: dict[str, Any],
    ):
        coerce_to = attrs.pop('coerce_to', None)
        if coerce_to is not None:
            try:
                element.js_coerce_func = COERCE[coerce_to]
            except KeyError as exc:
                raise Exception(f'coerce must be one of: {list(COERCE.keys())}') from exc
        else:
            element.js_coerce_func = attrs.pop('js_coerce_func', None)
        if isinstance(element, input_):
            element.js_value_func = attrs.pop(
                'js_value_func',
                JS_VALUE_FUNCS.get(attrs.get('type_', 'text'), 'hypergen.read.value'),
            )
            if not element.js_coerce_func:
                element.js_coerce_func = JS_COERCE_FUNCS.get(attrs.get('type_', 'text'))
        elif isinstance(element, select):
            if attrs.get('multiple') is True:
                element.js_value_func = attrs.pop('js_value_func', 'hypergen.read.selectMultiple')
                if coerce_to is str:
                    pass
                elif coerce_to is int:
                    element.js_coerce_func = 'hypergen.coerce.intlist'
                else:
                    raise Exception(
                        f'coerce_to={coerce_to} not yet implemented for multiple selects',
                    )
            else:
                element.js_value_func = attrs.pop('js_value_func', 'hypergen.read.value')
        else:
            element.js_value_func = attrs.pop(
                'js_value_func',
                'hypergen.read.contenteditable'
                if attrs.get('contenteditable', False) is True
                else 'hypergen.read.value',
            )
        if isinstance(element, a) and attrs.get('target') in (None, '_self'):
            href = attrs.get('href')
            partial = attrs.pop('partial', True)
            if partial and type(href) is metastr:
                base_template1 = href.meta.get('base_template')
                if base_template1 is not None:
                    base_template2 = c.hypergen.get('partial_base_template')
                    if base_template2 is not None and compare_funcs(base_template1, base_template2):
                        attrs['onclick'] = f"hypergen.partialLoad(event, '{href}', true)"
        yield


class LiveviewPlugin(LiveviewPluginBase):
    @contextmanager
    def context(self):
        with c(at='hypergen', event_handler_callbacks={}, commands=deque()):
            yield

    def process_html(self, html_output: str) -> str:
        def template() -> None:
            raw('<!--hypergen_liveview_media-->')
            script(src=_static_hypergen_path())
            script(
                dumps(c.hypergen.commands),
                type_='application/json',
                id_='hypergen-apply-commands-data',
            )
            script(
                """
                hypergen.ready(() => hypergen.applyCommands(JSON.parse(document.getElementById(
                    'hypergen-apply-commands-data').textContent, hypergen.reviver)))
            """,
            )

        command(
            'hypergen.setClientState',
            'hypergen.eventHandlerCallbacks',
            c.hypergen.event_handler_callbacks,
        )
        path = _request_path(c.request)
        command('history.replaceState', {'callback_url': path}, '', path)
        if '<head>' in html_output:
            assert html_output.count('<head>') == 1, (
                'Ooops, multiple <head> tags found. There can be only one!'
            )
            return html_output.replace('<head>', '<head>' + _hypergen_html(template))
        if '<html>' in html_output:
            assert html_output.count('<html>') == 1, (
                'Ooops, multiple <html> tags found. There can be only one!'
            )
            return html_output.replace(
                '<html>',
                '<html><head>' + _hypergen_html(template) + '</head>',
            )
        return _hypergen_html(template) + html_output


class ActionPlugin(LiveviewPluginBase):
    def __init__(
        self,
        target_id: str | None = None,
        base_view: BaseViewCallable | None = None,
        morph: bool = True,
        prepend_commands: bool = True,
    ) -> None:
        self.target_id = target_id
        self.base_view = base_view
        self.morph = morph
        self.prepend_commands = prepend_commands

    @contextmanager
    def context(self):
        with c(
            at='hypergen',
            event_handler_callbacks={},
            commands=deque(),
            target_id=self.target_id,
        ):
            yield

    def template_after(self, **kwargs: Any) -> None:
        extra_target_contexts = {}
        extra_event_handler_callbacks: dict[str, Any] = {}
        if self.base_view:
            referer_resolver_match = liveview_resolver_match(for_action=True)
            if referer_resolver_match is not None and referer_resolver_match.func is not None:
                isolated_into = contextlist('target_id')
                with c(
                    at='hypergen',
                    ids=set(),
                    into=isolated_into,
                    target_id=None,
                    event_handler_callbacks=extra_event_handler_callbacks,
                ):
                    self.base_view.hypergen_render(
                        *referer_resolver_match.args,
                        **referer_resolver_match.kwargs,
                    )
                extra_target_contexts = {
                    key: value
                    for key, value in isolated_into.contexts.items()
                    if key != '__default_context__' and value
                }
        commands = [
            [
                'hypergen.setClientState',
                'hypergen.eventHandlerCallbacks',
                {**extra_event_handler_callbacks, **c.hypergen.event_handler_callbacks},
            ],
        ]
        if self.morph and 'into' in c.hypergen:
            target_contexts = dict(c.hypergen.into.contexts)
            target_contexts.update(extra_target_contexts)
            for target_id, into in target_contexts.items():
                if into:
                    commands.append(['hypergen.morph', target_id, join_html(into)])
        commands.append(['hypergen.onpushstate'])
        if self.prepend_commands:
            c.hypergen.commands.extendleft(reversed(commands))
        else:
            c.hypergen.commands.extend(commands)


def command(javascript_func_path: str, *args: Any, **kwargs: Any) -> list[Any] | None:
    prepend = kwargs.pop('prepend', False)
    return_ = kwargs.pop('return_', False)
    item = [javascript_func_path, *args]
    if return_:
        return item
    if prepend:
        c.hypergen.commands.appendleft(item)
    else:
        c.hypergen.commands.append(item)


def callback(
    url: str | metastr | NamedCallable,
    *cb_args: Any,
    debounce: int = 0,
    confirm_: bool = False,
    confirm: bool = False,
    blocks: bool = False,
    upload_files: bool = False,
    clear: bool = False,
    headers: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
    when: Any = None,
    each_url_blocks: bool = True,
    timeout: int = 20000,
) -> CallbackRenderer:
    meta = meta or {}
    headers = headers or {}
    if confirm is not False:
        confirm_ = confirm
    assert getattr(url, 'is_hypergen_liveview', False) is not True, (
        "You can't callback to a @liveview, only an @action."
    )
    if getattr(url, 'supports_hypergen_callback', False) is True:
        url = cast(CallbackTarget, url).reverse()

    def to_html(element: base_element, key: str, value: Any) -> list[Any]:
        def fix_this(x: Any) -> Any:
            return element if x is THIS else x

        element.ensure_id()
        cmd = command(
            'hypergen.callback',
            url,
            [fix_this(x) for x in cb_args],
            {
                'debounce': debounce,
                'confirm_': confirm_,
                'blocks': blocks,
                'uploadFiles': upload_files,
                'clear': clear,
                'elementId': element.attrs['id_'],
                'debug': current_app.debug if has_app_context() else False,
                'meta': meta,
                'headers': headers,
                'blocksEachUrl': each_url_blocks,
                'timeout': timeout,
            },
            return_=True,
        )
        cmd_id = f'{element.attrs["id_"]}__{key}'
        c.hypergen.event_handler_callbacks[cmd_id] = cmd
        when_str = ', ' + dumps(when).replace('"', "'") if when else ''
        return [' ', t(key), '="', f"hypergen.event(event, '{cmd_id}'{when_str})", '"']

    signature = {
        key: value
        for key, value in {
            'debounce': debounce,
            'confirm_': confirm_,
            'blocks': blocks,
            'upload_files': upload_files,
            'clear': clear,
            'meta': meta,
            'when': when,
            'blocksEachUrl': each_url_blocks,
            'timeout': timeout,
        }.items()
        if value
    }
    renderer = cast(CallbackRenderer, to_html)
    renderer.hypergen_callback_signature = ('callback', (url, *cb_args), signature)
    return renderer


def call_js(command_path: str, *cb_args: Any):
    def to_html(element: base_element, key: str, value: Any):
        def fix_this(x: Any) -> Any:
            return element if x is THIS else x

        element.ensure_id()
        cmd = command(command_path, *[fix_this(x) for x in cb_args], return_=True)
        cmd_id = f'{element.attrs["id_"]}__{key}'
        c.hypergen.event_handler_callbacks[cmd_id] = cmd
        return [' ', t(key), '="', f"hypergen.event(event, '{cmd_id}')", '"']

    return to_html


def json_commands_response(commands: Any, status: int = 200) -> Response:
    return Response(dumps(commands), status=status, mimetype='application/json')


def _is_redirect_response(response: object) -> TypeGuard[Response]:
    return bool(
        isinstance(response, Response) and 300 <= response.status_code < 400 and response.location,
    )


@wrap2
def liveview(
    func: Callable[..., Any],
    router: Blueprint | Flask | None = None,
    rule: str | None = None,
    base_template: Callable[..., Any] | None = None,
    perm: str | tuple[str, ...] | None = None,
    any_perm: bool = False,
    login_url: str | None = None,
    raise_exception: bool = False,
    redirect_field_name: str | None = None,
    endpoint: str | None = None,
    methods: list[str] | tuple[str, ...] | None = None,
    partial: bool = True,
    target_id: str | None = None,
    appstate: Any = None,
    user_plugins: list[object] | None = None,
) -> LiveviewCallable:
    options = LiveviewOptions(
        base_template=base_template,
        perm=perm,
        any_perm=any_perm,
        login_url=login_url,
        raise_exception=raise_exception,
        redirect_field_name=redirect_field_name,
        partial=partial,
        target_id=target_id,
        appstate=appstate,
        user_plugins=tuple(user_plugins or ()),
    )
    wrapped = HypergenMethodView._liveview_wrap(func, options)
    return cast(
        LiveviewCallable,
        HypergenMethodView._route_finalize(
            router,
            wrapped,
            kind=HypergenEndpointKind.LIVEVIEW,
            rule=rule,
            methods=methods or (['GET', 'POST'] if partial else ['GET']),
            endpoint=endpoint,
            base_template=base_template,
        ),
    )


@wrap2
def action(
    func: Callable[..., Any],
    router: Blueprint | Flask | None = None,
    rule: str | None = None,
    base_template: Callable[..., Any] | None = None,
    target_id: str | None = None,
    perm: str | tuple[str, ...] | None = None,
    any_perm: bool = False,
    login_url: str | None = None,
    raise_exception: bool = False,
    redirect_field_name: str | None = None,
    endpoint: str | None = None,
    methods: list[str] | tuple[str, ...] | None = None,
    partial: bool = True,
    base_view: BaseViewCallable | None = None,
    appstate: Any = None,
    user_plugins: list[object] | None = None,
) -> ActionCallable:
    options = ActionOptions(
        base_template=base_template,
        target_id=target_id,
        perm=perm,
        any_perm=any_perm,
        login_url=login_url,
        raise_exception=raise_exception,
        redirect_field_name=redirect_field_name,
        partial=partial,
        base_view=base_view,
        appstate=appstate,
        user_plugins=tuple(user_plugins or ()),
    )
    wrapped = HypergenMethodView._action_wrap(func, options)
    return cast(
        ActionCallable,
        HypergenMethodView._route_finalize(
            router,
            wrapped,
            kind=HypergenEndpointKind.ACTION,
            rule=rule,
            methods=methods or ['POST'],
            endpoint=endpoint,
            base_template=base_template,
        ),
    )


class HypergenMethodView(MethodView):
    """A Flask ``MethodView`` registered as one Hypergen endpoint kind.

    Configure the endpoint with either ``LiveviewOptions`` or ``ActionOptions``, implement
    ``get()`` or ``post()``, then call ``register()``. The class methods in the registration
    pipeline and the handler/base-render methods are intentionally overridable independently.
    """

    hypergen_options: ClassVar[LiveviewOptions | ActionOptions | None] = None

    @staticmethod
    def _invoke_view(
        func: Callable[..., Any],
        request: Any,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        if getattr(func, 'is_hypergen_method_view', False):
            return func(**kwargs)
        return func(request, *args, **kwargs)

    @classmethod
    def _renderer_for(cls, func: Callable[..., Any]) -> Callable[..., Any]:
        def render(*args: Any, **kwargs: Any) -> Any:
            return cls._invoke_view(func, c.request, args, kwargs)

        return render

    @classmethod
    def _template_for(
        cls,
        func: Callable[..., Any],
        request: Any,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Callable[[], Any]:
        def template() -> Any:
            return cls._invoke_view(func, request, args, kwargs)

        return template

    @classmethod
    def _liveview_wrap(
        cls,
        func: Callable[..., Any],
        options: LiveviewOptions,
    ) -> LiveviewCallable:
        target_id, partial_base_template = options.resolve_rendering(func)

        @wraps(func)
        def _(*args, **kwargs):
            request = flask_request
            perm_check = check_perms(
                request,
                options.perm,
                login_url=options.login_url,
                raise_exception=options.raise_exception,
                any_perm=options.any_perm,
                redirect_field_name=options.redirect_field_name,
            )
            if not perm_check.ok:
                return perm_check.response
            template = cls._template_for(func, request, args, kwargs)
            if options.partial and _request_header(request, 'X-Hypergen-Partial') == '1':
                with c(
                    at='hypergen',
                    matched_perms=perm_check.matched_perms,
                    partial_base_template=partial_base_template,
                    liveview_resolver_match=liveview_resolver_match(),
                    partial_request=True,
                ):
                    full = hypergen(
                        template,
                        settings={
                            'action': True,
                            'returns': FULL,
                            'target_id': target_id,
                            'appstate': options.appstate,
                            'namespace': namespace_resolve(_),
                            'prepend_commands': False,
                            'user_plugins': list(options.user_plugins),
                        },
                    )
                    assert isinstance(full, HypergenResult)
                    if _is_redirect_response(full.template_result):
                        return callback_redirect_response(full.template_result)
                    return json_commands_response(full.context.hypergen.commands)
            with c(
                at='hypergen',
                matched_perms=perm_check.matched_perms,
                partial_base_template=partial_base_template,
                liveview_resolver_match=liveview_resolver_match(),
            ):
                full = hypergen(
                    template,
                    settings={
                        'liveview': True,
                        'returns': FULL,
                        'base_template': options.base_template,
                        'appstate': options.appstate,
                        'namespace': namespace_resolve(_),
                        'user_plugins': list(options.user_plugins),
                    },
                )
                assert isinstance(full, HypergenResult)
                if isinstance(full.template_result, Response):
                    return full.template_result
                return Response(full.html, mimetype='text/html')

        wrapped = cast(LiveviewCallable, _)
        wrapped.original_func = func
        wrapped.hypergen_render = cls._renderer_for(func)
        return wrapped

    @classmethod
    def _action_wrap(
        cls,
        func: Callable[..., Any],
        options: ActionOptions,
    ) -> ActionCallable:
        target_id, partial_base_template = options.resolve_rendering(func)

        @wraps(func)
        def _(*args, **kwargs):
            request = flask_request
            perm_check = check_perms(
                request,
                options.perm,
                login_url=options.login_url,
                raise_exception=options.raise_exception,
                any_perm=options.any_perm,
                redirect_field_name=options.redirect_field_name,
            )
            if not perm_check.ok:
                if _is_redirect_response(perm_check.response):
                    return callback_redirect_response(perm_check.response)
                return perm_check.response or Response(status=403)
            action_args = loads(request.form['hypergen_data'])['args']
            template = cls._template_for(func, request, tuple(action_args), kwargs)
            with c(
                at='hypergen',
                matched_perms=perm_check.matched_perms,
                partial_base_template=partial_base_template,
                liveview_resolver_match=liveview_resolver_match(for_action=True),
                action_args=tuple(action_args),
            ):
                full = hypergen(
                    template,
                    settings={
                        'action': True,
                        'returns': FULL,
                        'target_id': target_id,
                        'appstate': options.appstate,
                        'namespace': namespace_resolve(_),
                        'base_view': options.base_view,
                        'user_plugins': list(options.user_plugins),
                    },
                )
                assert isinstance(full, HypergenResult)
                if _is_redirect_response(full.template_result):
                    return callback_redirect_response(full.template_result)
                if isinstance(full.template_result, Response):
                    return full.template_result
                if type(full.template_result) is list:
                    return json_commands_response(full.template_result)
                return json_commands_response(full.context.hypergen.commands)

        wrapped = cast(ActionCallable, _)
        wrapped.original_func = func
        wrapped.hypergen_render = cls._renderer_for(func)
        return wrapped

    @staticmethod
    def _route_finalize(
        router: Blueprint | Flask | None,
        func: Callable[..., Any],
        *,
        kind: HypergenEndpointKind,
        rule: str | None,
        methods: Collection[str],
        endpoint: str | None,
        base_template: Callable[..., Any] | None,
    ) -> RoutableCallable:
        wrapped = route_register(
            router,
            cast(NamedCallable, func),
            rule=rule,
            methods=list(methods),
            endpoint=endpoint,
            base_template=base_template,
        )
        wrapped.hypergen_kind = kind
        wrapped.is_hypergen_liveview = kind is HypergenEndpointKind.LIVEVIEW
        wrapped.supports_hypergen_callback = kind is HypergenEndpointKind.ACTION
        return wrapped

    @classmethod
    def hypergen_options_get(cls) -> LiveviewOptions | ActionOptions:
        """Return this class's Hypergen behavior."""
        if cls.hypergen_options is None:
            raise TypeError(f'{cls.__name__}.hypergen_options must be configured')
        return cls.hypergen_options

    @classmethod
    def view_func_create(
        cls,
        endpoint: str,
        view_args: tuple[Any, ...],
        view_kwargs: dict[str, Any],
    ) -> Callable[..., Any]:
        """Create the ordinary Flask class-view dispatcher."""
        return cls.as_view(endpoint, *view_args, **view_kwargs)

    @classmethod
    def view_func_wrap(
        cls,
        view_func: Callable[..., Any],
        options: LiveviewOptions | ActionOptions,
    ) -> LiveviewCallable | ActionCallable:
        """Apply the shared Hypergen runtime wrapper."""
        view_func.is_hypergen_method_view = True
        if isinstance(options, LiveviewOptions):
            return cls._liveview_wrap(view_func, options)
        return cls._action_wrap(view_func, options)

    @classmethod
    def route_methods_get(
        cls,
        view_func: Callable[..., Any],
        options: LiveviewOptions | ActionOptions,
        methods: Collection[str] | None,
    ) -> Collection[str]:
        """Resolve HTTP methods for route registration."""
        if methods is not None:
            return methods
        if view_methods := getattr(view_func, 'methods', None):
            resolved_methods = list(view_methods)
            if (
                isinstance(options, LiveviewOptions)
                and options.partial
                and 'POST' not in {method.upper() for method in resolved_methods}
            ):
                resolved_methods.append('POST')
            return resolved_methods
        if isinstance(options, LiveviewOptions):
            return ['GET', 'POST'] if options.partial else ['GET']
        return ['POST']

    @classmethod
    def reverse_source_get(
        cls,
        options: LiveviewOptions | ActionOptions,
    ) -> Callable[..., Any] | None:
        """Return the handler signature used for positional ``reverse()`` arguments."""
        method_name = 'get' if isinstance(options, LiveviewOptions) else 'post'
        return getattr(cls, method_name, None)

    @classmethod
    def base_renderer_create(
        cls,
        view_args: tuple[Any, ...],
        view_kwargs: dict[str, Any],
    ) -> Callable[..., Any]:
        """Build the renderer actions use to refresh this liveview."""
        shared_instance = None if cls.init_every_request else cls(*view_args, **view_kwargs)

        def render(*args: Any, **kwargs: Any) -> Any:
            instance = (
                shared_instance if shared_instance is not None else cls(*view_args, **view_kwargs)
            )
            return instance.hypergen_render_base(*args, **kwargs)

        return render

    @classmethod
    def register(
        cls,
        router: Blueprint | Flask,
        rule: str,
        *,
        endpoint: str | None = None,
        methods: Collection[str] | None = None,
        options: LiveviewOptions | ActionOptions | None = None,
        view_args: tuple[Any, ...] = (),
        view_kwargs: dict[str, Any] | None = None,
    ) -> RoutableCallable:
        """Create, wrap, and register this class as a Hypergen route."""
        endpoint = endpoint or cls.__name__
        options = options or cls.hypergen_options_get()
        view_kwargs = dict(view_kwargs or {})
        view_func = cls.view_func_create(endpoint, view_args, view_kwargs)
        wrapped = cls.view_func_wrap(view_func, options)
        reverse_source = cls.reverse_source_get(options)
        if reverse_source is not None:
            wrapped.hypergen_reverse_source = reverse_source
        if isinstance(options, LiveviewOptions):
            wrapped.hypergen_render = cls.base_renderer_create(view_args, view_kwargs)
            kind = HypergenEndpointKind.LIVEVIEW
        else:
            kind = HypergenEndpointKind.ACTION
        return cls._route_finalize(
            router,
            wrapped,
            kind=kind,
            rule=rule,
            methods=cls.route_methods_get(view_func, options, methods),
            endpoint=endpoint,
            base_template=options.base_template,
        )

    def hypergen_handler_get(self) -> Callable[..., Any]:
        """Return the handler for the current HTTP request."""
        is_partial_request = 'hypergen' in c and c.hypergen.get('partial_request', False)
        method = 'get' if is_partial_request else flask_request.method.lower()
        handler = getattr(self, method, None)
        if handler is None and flask_request.method == 'HEAD':
            handler = getattr(self, 'get', None)
        if handler is None:
            abort(405)
        return handler

    def dispatch_request(self, **kwargs: Any) -> Any:
        """Dispatch URL and callback arguments to the selected method."""
        handler = self.hypergen_handler_get()
        callback_args: tuple[Any, ...] = ()
        if 'hypergen' in c:
            callback_args = tuple(c.hypergen.get('action_args', ()))
        return current_app.ensure_sync(handler)(*callback_args, **kwargs)

    def hypergen_render_base(self, *args: Any, **kwargs: Any) -> Any:
        """Render this class's GET handler independently of the current method."""
        handler = getattr(self, 'get', None)
        if handler is None:
            raise TypeError(f'{type(self).__name__} must define get() to be used as a base view')
        return current_app.ensure_sync(handler)(*args, **kwargs)


ENCODINGS = {
    date: lambda o: {'_': ['date', str(o)]},
    datetime: lambda o: {'_': ['datetime', str(o)]},
    dt_time: lambda o: {'_': ['time', str(o)]},
    tuple: lambda o: {'_': ['tuple', list(o)]},
    deque: lambda o: {'_': ['deque', list(o)]},
    set: lambda o: {'_': ['set', list(o)]},
    frozenset: lambda o: {'_': ['frozenset', list(o)]},
    range: lambda o: {'_': ['range', [o.start, o.stop, o.step]]},
    type(EVENT): lambda o: {'_': ['EVENT', None]},
}


def encoder(o: Any) -> list[Any] | dict[str, Any]:
    if issubclass(type(o), base_element):
        assert o.attrs.get('id_', False), 'Missing id_'
        return ['_', 'element_value', [o.js_value_func, o.js_coerce_func, o.attrs['id_']]]
    fn = ENCODINGS.get(type(o))
    if fn:
        return fn(o)
    raise TypeError(f'{o!r} is not JSON serializable')


DECODINGS = {
    'float': float,
    'date': date.fromisoformat,
    'datetime': datetime.fromisoformat,
    'time': dt_time.fromisoformat,
    'tuple': tuple,
    'deque': deque,
    'set': set,
    'frozenset': frozenset,
    'range': lambda v: range(*v),
}


def decoder(o: dict[str | int, Any]) -> Any:
    data = o.get('_')
    if data is None or type(data) is not list or len(data) != 2:
        return o
    datatype, value = data
    fn = DECODINGS.get(datatype)
    if fn:
        return fn(value)
    raise Exception(f'Unknown datatype, {datatype}')


def dumps(
    data: Any,
    default: Callable[[Any], Any] = encoder,
    indent: int | None = None,
) -> str:
    return json.dumps(data, default=default, separators=(',', ':'), indent=indent)


def loads(data: str, integer_keys: bool = False) -> Any:
    def integer_keys_object_pairs_hook(pairs: list[tuple[str, Any]]) -> Any:
        return decoder({int(k) if k.isdigit() else k: v for k, v in pairs})

    if integer_keys is True:
        return json.loads(data, object_pairs_hook=integer_keys_object_pairs_hook)
    return json.loads(data, object_hook=decoder)
