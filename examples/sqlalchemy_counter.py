from __future__ import annotations

from pathlib import Path

from flask import Blueprint
from sqlalchemy import create_engine
from sqlalchemy import select as sa_select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import NullPool

from examples.common import make_base_template
from flask_hypergen import NO_PERM_REQUIRED, action, callback, liveview
from flask_hypergen.tags import button, h2, p


class Base(DeclarativeBase):
    pass


class CounterState(Base):
    __tablename__ = 'counter_state'

    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[int] = mapped_column(default=0)


def make_blueprint(database_url: str) -> Blueprint:
    bp = Blueprint('sqlalchemy_counter', __name__, url_prefix='/sqlalchemy-counter')
    base_template = make_base_template('SQLAlchemy Counter')
    # Tests create many short-lived example apps, so do not retain SQLite connections in a pool
    # after their sessions close and leave them for garbage collection.
    engine = create_engine(database_url, future=True, poolclass=NullPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        state = session.get(CounterState, 1)
        if state is None:
            session.add(CounterState(id=1, value=0))
            session.commit()

    def current_value() -> int:
        with Session(engine) as session:
            return session.scalar(sa_select(CounterState.value).where(CounterState.id == 1)) or 0

    def update_value(delta: int) -> int:
        with Session(engine) as session:
            state = session.get(CounterState, 1)
            assert state is not None
            state.value += delta
            session.commit()
            return state.value

    def page_template(n: int) -> None:
        h2('SQLAlchemy-backed state')
        p('This example keeps a small counter in a local SQLite database.')
        p(f'Persisted value: {n}', id_='db-value')
        button('Increment persisted counter', id_='db-increment', onclick=callback(increment, 1))

    @liveview(bp, '/counter', perm=NO_PERM_REQUIRED, base_template=base_template)
    def counter(request) -> None:
        page_template(current_value())

    @action(bp, '/increment', perm=NO_PERM_REQUIRED, target_id='content', base_view=counter)
    def increment(request, delta: int) -> None:
        page_template(update_value(delta))

    return bp


def default_database_url(root: str | Path | None = None) -> str:
    root = Path(root or '.').resolve()
    return f'sqlite:///{root / ".flask_hypergen_example.sqlite3"}'
