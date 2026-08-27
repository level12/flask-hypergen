from __future__ import annotations

from flask import Blueprint

from examples.common import counter_fragment, make_base_template
from flask_hypergen import (
    NO_PERM_REQUIRED,
    ActionOptions,
    HypergenMethodView,
    LiveviewOptions,
    callback,
)
from flask_hypergen.tags import h2, p


bp = Blueprint('classviews', __name__, url_prefix='/classviews')
BASE_TEMPLATE = make_base_template('Class-Based Views')


def counter_template(n: int) -> None:
    h2('Class-based view wiring')
    p('The page is a liveview class, and its callback target is an action class.')
    counter_fragment(n, callback(increment, n))


class CounterView(HypergenMethodView):
    hypergen_options = LiveviewOptions(
        perm=NO_PERM_REQUIRED,
        base_template=BASE_TEMPLATE,
    )

    def get(self) -> None:
        counter_template(0)


counter = CounterView.register(bp, '/counter', endpoint='counter')


class IncrementAction(HypergenMethodView):
    hypergen_options = ActionOptions(
        perm=NO_PERM_REQUIRED,
        target_id='content',
        base_view=counter,
    )

    def post(self, n: int) -> None:
        counter_template(n + 1)


increment = IncrementAction.register(bp, '/increment', endpoint='increment')
