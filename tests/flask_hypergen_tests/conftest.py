from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from threading import Thread
from typing import Any

from flask import Flask
from flask.testing import FlaskClient
import pytest
from werkzeug.serving import make_server

from examples.app import create_app
from flask_hypergen.context import context, contextlist

from tests.flask_hypergen_tests.region_test_app import create_region_test_app


class User:
    pk: int = 1
    id: int = 1
    is_authenticated: bool = True
    permissions: frozenset[str] = frozenset()

    def has_perm(self, permission: str) -> bool:
        return permission in self.permissions

    def has_perms(
        self,
        permissions: list[str] | tuple[str, ...] | set[str] | frozenset[str],
    ) -> bool:
        return set(permissions) <= set(self.permissions)


class Request:
    def __init__(self) -> None:
        self.user = User()
        self.session: dict[str, Any] = {}
        self.endpoint = 'tests.endpoint'
        self.view_args: dict[str, Any] = {}
        self.headers: dict[str, str] = {}

    def get_full_path(self) -> str:
        return 'mock'


class HttpResponse:
    pass


def hypergen_context() -> dict[str, Any]:
    return {
        'into': contextlist('target_id'),
        'ids': set(),
        'event_handler_callbacks': {},
        'commands': deque(),
        'plugins': [],
    }


def mock_hypergen_callback(func: Callable[..., Any]) -> Callable[..., Any]:
    func.reverse = lambda *a, **k: '/path/to/cb/'
    return func


@contextmanager
def mock_middleware() -> Iterator[None]:
    with context(request=Request(), user=User()):
        yield


@pytest.fixture
def renderer_context() -> Iterator[None]:
    with mock_middleware():
        yield


@pytest.fixture
def app(tmp_path) -> Flask:
    return create_app(testing=True, database_url=f'sqlite:///{tmp_path / "example.sqlite3"}')


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture
def region_app() -> Flask:
    return create_region_test_app()


@pytest.fixture
def region_client(region_app: Flask) -> FlaskClient:
    return region_app.test_client()


@pytest.fixture
def region_live_server(region_app: Flask) -> Iterator[str]:
    server = make_server('127.0.0.1', 0, region_app)
    port = server.socket.getsockname()[1]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        server.shutdown()
        thread.join(timeout=5)
