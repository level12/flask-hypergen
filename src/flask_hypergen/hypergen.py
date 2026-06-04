from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from functools import update_wrapper
from html import escape
import inspect
import logging
from typing import Any, Protocol, cast
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from flask import Blueprint, Flask, Request, Response, current_app, url_for
from werkzeug.exceptions import Forbidden

from flask_hypergen.context import context, user_resolve


logger = logging.getLogger(__name__)

__all__ = [
    'AUTOURL_WSGI_ERR_MSG',
    'PermissionCheck',
    'ResolverMatch',
    'autourl_register',
    'autourls',
    'check_perms',
    'compare_funcs',
    'is_collection',
    'make_string',
    'metastr',
    'plugins_exit_stack',
    'plugins_method_call',
    'plugins_pipeline',
    'resolve_url',
    'route_register',
    't',
    'wrap2',
]

AUTOURL_WSGI_ERR_MSG = (
    "Hypergen: I'm sorry, I can't auto reverse the url for this liveview/action. "
    'The attribute `hypergen_endpoint` should exist on the wrapped function. '
    'func: {}, module: {}'
)


class NamedCallable(Protocol):
    __name__: str
    __module__: str

    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


class ReverseCallable(Protocol):
    hypergen_endpoint: str

    def __call__(self, *view_args: Any, **view_kwargs: Any) -> metastr: ...


class RoutableCallable(NamedCallable, Protocol):
    reverse: ReverseCallable
    hypergen_endpoint: str
    supports_hypergen_callback: bool


_URLS: dict[str, set[tuple[NamedCallable, str | None, str | None, object | None]]] = {}
_ENDPOINTS: dict[str, RoutableCallable] = {}


@dataclass
class ResolverMatch:
    func: object | None
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PermissionCheck:
    ok: bool
    response: Response | None = None
    matched_perms: set[str] = field(default_factory=set)


def make_string(value: Any) -> str:
    return '' if value is None else str(value)


def t(value: Any, quote: bool = True) -> str:
    return escape(make_string(value), quote=quote)


def wrap2(func: Callable[..., Any]) -> Callable[..., Any]:
    def decorator(*args: Any, **kwargs: Any) -> Any:
        if len(args) == 1 and not kwargs and callable(args[0]):
            wrapped = func(args[0])
            update_wrapper(wrapped, args[0])
            return wrapped

        def wrapper(inner_func: Callable[..., Any]) -> Any:
            wrapped = func(inner_func, *args, **kwargs)
            update_wrapper(wrapped, inner_func)
            return wrapped

        return wrapper

    return decorator


def compare_funcs(a: Any, b: Any) -> bool:
    return all(
        getattr(a, key) == getattr(b, key)
        for key in ('__doc__', '__name__', '__module__', '__qualname__')
    )


def is_collection(value: Any) -> bool:
    if isinstance(value, (str, metastr)):
        return False
    try:
        iter(value)
        return True
    except TypeError:
        return False


def check_perms(
    request: Request,
    perm: str | tuple[str, ...],
    login_url: str | None = None,
    raise_exception: bool = False,
    any_perm: bool = False,
    redirect_field_name: str | None = None,
) -> PermissionCheck:
    from flask_hypergen.liveview import LOGIN_REQUIRED, NO_PERM_REQUIRED

    if perm == NO_PERM_REQUIRED:
        return PermissionCheck(ok=True)
    assert perm, 'perm= is required'

    def auth_failure_response() -> Response:
        if raise_exception:
            raise Forbidden()
        login_target = login_url
        if login_target is None:
            login_manager = getattr(
                current_app,
                'login_manager',
                None,
            ) or current_app.extensions.get(
                'login_manager',
            )
            login_target = getattr(login_manager, 'login_view', None)
        if not login_target:
            return Response(status=403)
        if not (str(login_target).startswith('/') or '://' in str(login_target)):
            login_target = url_for(login_target)
        redirect_name = redirect_field_name or 'next'
        next_value = getattr(request, 'url', None) or getattr(request, 'path', '/')
        split = urlsplit(login_target)
        query = dict(parse_qsl(split.query, keep_blank_values=True))
        query.setdefault(redirect_name, next_value)
        response = Response(status=302)
        response.location = urlunsplit(split._replace(query=urlencode(query)))
        return response

    def is_authenticated(user: Any) -> bool:
        return bool(user and getattr(user, 'is_authenticated', False))

    def has_perm(user: Any, name: str) -> bool:
        checker = getattr(user, 'has_perm', None)
        return checker(name) if checker else False

    def has_perms(user: Any, names: tuple[str, ...]) -> bool:
        checker = getattr(user, 'has_perms', None)
        if checker:
            return checker(names)
        return all(has_perm(user, name) for name in names)

    user = user_resolve(request) or getattr(context, 'user', None)
    if perm == LOGIN_REQUIRED:
        if is_authenticated(user):
            return PermissionCheck(ok=True)
        return PermissionCheck(ok=False, response=auth_failure_response())

    perms = (perm,) if isinstance(perm, str) else tuple(perm)
    if not is_authenticated(user):
        return PermissionCheck(ok=False, response=auth_failure_response())
    if any_perm is not True:
        if has_perms(user, perms):
            return PermissionCheck(ok=True, matched_perms=set(perms))
    else:
        matched_perms = {name for name in perms if has_perm(user, name)}
        if matched_perms:
            return PermissionCheck(ok=True, matched_perms=matched_perms)
    if raise_exception:
        raise Forbidden()
    return PermissionCheck(ok=False, response=Response(status=403))


class metastr(str):
    meta: dict[str, Any]

    @staticmethod
    def make(string: str, meta: dict[str, Any]) -> metastr:
        value = metastr(string)
        value.meta = meta
        return value


def _qualified_endpoint(router: Blueprint | Flask | None, endpoint: str) -> str:
    if router is None or isinstance(router, Flask):
        return endpoint
    return f'{router.name}.{endpoint}'


def _reverse_factory(
    func: NamedCallable,
    endpoint: str,
    base_template: object | None = None,
) -> ReverseCallable:
    signature = inspect.signature(getattr(func, 'original_func', func))
    param_names = [name for name in signature.parameters if name != 'request']
    func_name = getattr(func, '__name__', type(func).__name__)

    def reverse(*view_args: Any, **view_kwargs: Any) -> metastr:
        if len(view_args) > len(param_names):
            raise TypeError(f'Too many positional arguments for reverse() on {func_name}')
        params = dict(zip(param_names, view_args, strict=False))
        params.update(view_kwargs)
        return metastr.make(url_for(endpoint, **params), {'base_template': base_template})

    reverse_func = cast(ReverseCallable, reverse)
    reverse_func.hypergen_endpoint = endpoint
    return reverse_func


def autourl_register(
    func: NamedCallable,
    base_template: object | None = None,
    path: str | None = None,
    re_path: str | None = None,
) -> NamedCallable:
    module = func.__module__
    _URLS.setdefault(module, set())
    _URLS[module].add((func, path, re_path, base_template))
    return func


def autourls(module: Any, namespace: str) -> list[tuple[Any, Any, Any, Any]]:
    return [item for item in _URLS.get(module.__name__, []) if namespace]


def route_register(
    router: Blueprint | Flask | None,
    func: NamedCallable,
    *,
    rule: str | None = None,
    methods: list[str] | tuple[str, ...] | None = None,
    endpoint: str | None = None,
    base_template: object | None = None,
) -> RoutableCallable:
    methods = list(methods or ['GET'])
    func_name = getattr(func, '__name__', type(func).__name__)
    endpoint = endpoint or func_name
    qualified_endpoint = _qualified_endpoint(router, endpoint)
    func_obj = cast(RoutableCallable, func)
    func_obj.reverse = _reverse_factory(func, qualified_endpoint, base_template=base_template)
    func_obj.hypergen_endpoint = qualified_endpoint
    func_obj.supports_hypergen_callback = any(method.upper() == 'POST' for method in methods)
    _ENDPOINTS[qualified_endpoint] = func_obj
    if router is not None:
        router.add_url_rule(
            rule or f'/{func_name}/',
            endpoint,
            func_obj,
            methods=methods,
        )
    return func_obj


def resolve_url(url: str, method: str = 'GET') -> ResolverMatch:
    path = urlsplit(url).path or url
    adapter = current_app.url_map.bind('localhost')
    endpoint, kwargs = adapter.match(path, method=method)
    return ResolverMatch(func=_ENDPOINTS.get(endpoint), kwargs=dict(kwargs))


@contextmanager
def plugins_exit_stack(method_name: str) -> Iterator[None]:
    with ExitStack() as stack:
        for plugin in context.hypergen.plugins:
            if hasattr(plugin, method_name):
                stack.enter_context(getattr(plugin, method_name)())
        yield


def plugins_method_call(method_name: str, *args: Any, **kwargs: Any) -> None:
    for plugin in context.hypergen.plugins:
        method = getattr(plugin, method_name, None)
        if method:
            method(*args, **kwargs)


def plugins_pipeline(method_name: str, data: Any, kwargs: dict[str, Any] | None = None) -> Any:
    kwargs = kwargs or {}
    for plugin in context.hypergen.plugins:
        method = getattr(plugin, method_name, None)
        if method:
            data = method(data, **kwargs)
    return data
