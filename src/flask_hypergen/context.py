from __future__ import annotations

from collections import UserList, defaultdict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
import threading
from typing import Any

from flask import Flask, Request
from flask import request as flask_request
from pyrsistent import m, pmap


__all__ = [
    'Context',
    'ContextMiddleware',
    'c',
    'context',
    'context_init_app',
    'context_middleware',
    'contextlist',
]


class Context(threading.local):
    def __init__(self) -> None:
        self.ctx = pmap()
        super().__init__()

    def replace(self, **items: Any) -> None:
        self.ctx = m(**items)

    def __getattr__(self, key: str) -> Any:
        try:
            return self.__dict__['ctx'][key]
        except KeyError as exc:
            raise AttributeError(f'No such attribute: {key}') from exc

    def __setattr__(self, key: str, value: Any) -> None:
        if key == 'ctx':
            super().__setattr__(key, value)
            return
        self.ctx = self.ctx.set(key, value)

    def __getitem__(self, key: str) -> Any:
        return self.__dict__['ctx'][key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.ctx = self.ctx.set(key, value)

    def __contains__(self, key: str) -> bool:
        return key in self.ctx

    def clone(self) -> Context:
        clone = Context()
        clone.ctx = self.ctx
        return clone

    @contextmanager
    def __call__(
        self,
        transformer: Callable[[Any], Any] | None = None,
        at: str | None = None,
        **items: Any,
    ) -> Iterator[None]:
        previous = self.ctx
        try:
            if at is None:
                if transformer is not None:
                    self.ctx = transformer(self.ctx)
                self.ctx = self.ctx.update(m(**items))
            else:
                if at not in self.ctx:
                    self.ctx = self.ctx.set(at, pmap(items))
                else:
                    new_value_at = self.ctx[at].update(pmap(items))
                    if new_value_at is None:
                        raise TypeError(
                            'Not immutable context variable attempted updated. If you want to '
                            'nest with context() statements you must use a pmap() or another '
                            'immutable hashmap type.',
                        )
                    self.ctx = self.ctx.set(at, new_value_at)
                if transformer is not None:
                    self.ctx = self.ctx.set(at, transformer(self.ctx[at]))
            yield
        finally:
            self.ctx = previous


context = Context()
c = context


def user_resolve(request: Request) -> Any:
    user = getattr(request, 'user', None)
    if user is not None:
        return user
    try:
        from flask_login import current_user
    except ImportError:
        return None
    try:
        return current_user._get_current_object()
    except (RuntimeError, AttributeError):
        return None


def context_values_build(request: Request) -> dict[str, Any]:
    values = {'request': request}
    user = user_resolve(request)
    if user is not None:
        values['user'] = user
    return values


def context_middleware[ResponseT](
    get_response: Callable[[Request], ResponseT],
) -> Callable[[Request], ResponseT]:
    def middleware(request: Request) -> ResponseT:
        with context(**context_values_build(request)):
            return get_response(request)

    return middleware


class ContextMiddleware:
    def process_request(self, request: Request) -> None:
        context.replace(**context_values_build(request))


def context_init_app(app: Flask) -> None:
    if app.extensions.get('flask_hypergen_context_init'):
        return

    @app.before_request
    def context_before_request() -> None:
        context.replace(**context_values_build(flask_request))

    @app.teardown_request
    def context_teardown_request(exc: BaseException | None) -> None:
        del exc
        context.replace()

    app.extensions['flask_hypergen_context_init'] = True


class contextlist(UserList):
    def __init__(self, context_key: str, *args: Any, **kwargs: Any) -> None:
        self.context_key = context_key
        self.contexts = defaultdict(list)
        super().__init__(*args, **kwargs)

    def _get_context_value(self) -> str:
        if 'hypergen' not in context:
            return '__default_context__'
        target_id = context.hypergen.get(self.context_key, None)
        return target_id if target_id else '__default_context__'

    @property
    def data(self) -> list[Any]:
        return self.contexts[self._get_context_value()]

    @data.setter
    def data(self, value: list[Any]) -> None:
        self.contexts[self._get_context_value()] = value
