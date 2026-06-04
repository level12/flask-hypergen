from __future__ import annotations

from collections import OrderedDict, deque
from collections.abc import Callable, Iterator
from contextlib import ContextDecorator, ExitStack, contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
import importlib
from importlib.util import find_spec
from pprint import pformat
from types import GeneratorType
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast, overload

from flask import Response

from flask_hypergen.context import Context, contextlist
from flask_hypergen.context import context as c
from flask_hypergen.hypergen import (
    make_string,
    plugins_exit_stack,
    plugins_method_call,
    plugins_pipeline,
    t,
)
from flask_hypergen.plugins.appstate import AppstatePlugin


if TYPE_CHECKING:
    from flask_hypergen.liveview import BaseViewCallable


def module_available(name: str) -> bool:
    try:
        return find_spec(name) is not None
    except ModuleNotFoundError:
        return False


docutils_ok = module_available('docutils.core') and module_available('docutils.utils')


class DocutilsReporter(Protocol):
    SEVERE_LEVEL: int


class DocutilsUtilsModule(Protocol):
    Reporter: DocutilsReporter


class DocutilsCoreModule(Protocol):
    def publish_parts(
        self,
        source: str,
        writer_name: str,
        settings_overrides: dict[str, bool | int],
    ) -> dict[str, str]: ...


def docutils_core_load() -> DocutilsCoreModule:
    return cast(DocutilsCoreModule, importlib.import_module('docutils.core'))


def docutils_utils_load() -> DocutilsUtilsModule:
    return cast(DocutilsUtilsModule, importlib.import_module('docutils.utils'))


try:
    from yattag import indent as indent_

    yattag_ok = True
except ImportError:
    yattag_ok = False

OMIT = '__OMIT__'
HTML = 'HTML'
FULL = 'FULL'
COMMANDS = 'COMMANDS'
HYPERGEN_RETURNS = {HTML, FULL, COMMANDS}
DELETED = ''

ClassValue = str | list[str] | set[str] | None


def add_class(a: ClassValue, b: str) -> str | list[str] | set[str]:
    assert type(b) is str, 'b must be string for now. PR?'
    if a in ('', OMIT, None):
        return b
    if type(a) is str:
        return a.strip() + ' ' + b
    if isinstance(a, list):
        a.append(b)
        return a
    if isinstance(a, set):
        a.add(b)
        return a
    raise Exception("I don't know how to add these variables together in the context of classes.")


def on_url(url: str, value_on_url: Any = True, value_not_on_url: Any = False) -> Any:
    from flask_hypergen.liveview import url_is_active

    return value_on_url if url_is_active(url) else value_not_on_url


class TemplatePlugin:
    @contextmanager
    def context(self):
        with c(at='hypergen', into=contextlist('target_id'), ids=set()):
            yield


@dataclass
class HypergenSettings:
    plugins: list[object] = field(default_factory=list)
    liveview: bool = False
    action: bool = False
    returns: str = HTML
    indent: bool = False
    base_template: Callable[..., Any] | None = None
    target_id: str | None = None
    appstate: Any = None
    namespace: str | None = None
    base_view: BaseViewCallable | None = None
    prepend_commands: bool = True
    user_plugins: list[object] = field(default_factory=list)


@dataclass(frozen=True)
class HypergenResult:
    html: str
    context: Context
    template_result: object

    @overload
    def __getitem__(self, key: Literal['html']) -> str: ...

    @overload
    def __getitem__(self, key: Literal['context']) -> Context: ...

    @overload
    def __getitem__(self, key: Literal['template_result']) -> object: ...

    def __getitem__(self, key: str) -> str | Context | object:
        return getattr(self, key)


def settings_load(settings: dict[str, Any] | None) -> HypergenSettings:
    data = dict(settings or {})
    return HypergenSettings(
        plugins=list(data.get('plugins', [])),
        liveview=bool(data.get('liveview', False)),
        action=bool(data.get('action', False)),
        returns=data.get('returns', HTML),
        indent=bool(data.get('indent', False)),
        base_template=data.get('base_template'),
        target_id=data.get('target_id'),
        appstate=data.get('appstate'),
        namespace=data.get('namespace'),
        base_view=data.get('base_view'),
        prepend_commands=bool(data.get('prepend_commands', True)),
        user_plugins=list(data.get('user_plugins', [])),
    )


def plugins_build(settings: HypergenSettings) -> list[object]:
    plugins: list[object] = list(settings.plugins)
    if not plugins:
        plugins.append(TemplatePlugin())
    if settings.liveview:
        from flask_hypergen.liveview import LiveviewPlugin

        plugins.append(LiveviewPlugin())
    if settings.action:
        from flask_hypergen.liveview import ActionPlugin

        plugins.append(
            ActionPlugin(
                target_id=settings.target_id,
                base_view=settings.base_view,
                prepend_commands=settings.prepend_commands,
            ),
        )
    if settings.appstate is not None:
        namespace = getattr(settings.appstate, 'namespace', settings.namespace)
        assert namespace, 'When appstate is set, namespace must be too.'
        plugins.append(AppstatePlugin(namespace, settings.appstate))
    plugins.extend(settings.user_plugins)
    return plugins


def html_indent(html: str) -> str:
    if not yattag_ok:
        raise Exception("Do 'pip install yattag' to use the indent feature.")
    return indent_(html, indentation='    ', newline='\n', indent_text=True)


def hypergen(
    template: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> str | deque[Any] | HypergenResult:
    assert 'request' in c, "The 'flask_hypergen.context.context_init_app' hook must be installed!"
    settings = settings_load(kwargs.pop('settings', None))
    plugins = plugins_build(settings)
    returns = settings.returns
    assert returns in HYPERGEN_RETURNS, (
        f"The 'returns' hypergen setting must be one of {HYPERGEN_RETURNS!r}"
    )
    with (
        c(at='hypergen', plugins=plugins, base_template=settings.base_template),
        plugins_exit_stack(
            'context',
        ),
    ):
        plugins_method_call('template_before')
        template_func = settings.base_template()(template) if settings.base_template else template
        template_result = template_func(
            *args,
            **kwargs,
        )
        plugins_method_call('template_after', template_result=template_result)
        html = join_html(c.hypergen.into) if 'into' in c.hypergen else ''
        html = plugins_pipeline('process_html', html)
        if settings.indent:
            html = html_indent(html)
        if returns == HTML:
            return html
        if returns == COMMANDS:
            return c.hypergen.commands
        return HypergenResult(html=html, context=c.clone(), template_result=template_result)


def hypergen_to_response(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Response:
    html = hypergen(func, *args, **kwargs)
    assert isinstance(html, str)
    return Response(html, mimetype='text/html')


def join_html(html: list[Any] | tuple[Any, ...] | GeneratorType) -> str:
    def fmt(items: list[Any] | tuple[Any, ...] | GeneratorType) -> Iterator[Any]:
        for item in items:
            if issubclass(type(item), base_element):
                yield item.as_string()
            elif callable(item):
                yield item()
            elif type(item) is GeneratorType:
                with c(at='hypergen', into=[]):
                    yield join_html(item)
            else:
                yield item

    return ''.join(make_string(x) for x in fmt(html))


def raw(*children: Any) -> None:
    c.hypergen.into.extend(children)


def write(*children: Any) -> None:
    c.hypergen.into.extend(t(x) for x in children)


def rst(restructured_text: str, report_level: int | None = None) -> None:
    if not docutils_ok:
        raise Exception("Please 'pip install docutils' to use the rst() function.")
    docutils_core = docutils_core_load()
    docutils_utils = docutils_utils_load()
    report_level = report_level or docutils_utils.Reporter.SEVERE_LEVEL + 1
    raw(
        docutils_core.publish_parts(
            restructured_text,
            writer_name='html',
            settings_overrides={'_disable_config': True, 'report_level': report_level},
        )['html_body'],
    )


def hprint(*args, **kwargs):
    div_tag = globals()['div']
    span_tag = globals()['span']
    pre_tag = globals()['pre']
    code_tag = globals()['code']
    bold_tag = globals()['b']

    @component
    def typeinfo(x):
        span_tag(
            ' (',
            x.__class__.__module__,
            '.',
            type(x).__name__,
            ')',
            style={'color': 'darkgrey'},
        )

    def fmt(x):
        pre_tag(code_tag(pformat(x, width=120)), style={})

    with div_tag(
        style={
            'padding': '8px',
            'margin': '4px 0 0 0',
            'background': '#ffc',
            'color': 'black',
            'font_family': 'sans-serif',
        },
    ):
        if len(args) == 1 and not kwargs:
            div_tag(typeinfo(args[0]))
            fmt(args[0])
        else:
            for i, arg in enumerate(args, 1):
                div_tag(bold_tag('arg', i, sep=' '), typeinfo(arg))
                fmt(arg)
        for key, value in kwargs.items():
            div_tag(bold_tag(key), typeinfo(value))
            fmt(value)


class base_element(ContextDecorator):
    tag: str = ''
    js_value_func: str | None = None
    js_coerce_func: str | None = None
    void = False
    auto_id = False

    def __new__(cls, *args: Any, **kwargs: Any) -> base_element:
        instance = ContextDecorator.__new__(cls)
        instance.tag = cls.__name__.rstrip('_')
        return instance

    def __init__(self, *children: Any, **attrs: Any) -> None:
        with ExitStack() as stack:
            children_list = list(children)
            for plugin in c.hypergen.plugins:
                if hasattr(plugin, 'wrap_element_init'):
                    stack.enter_context(plugin.wrap_element_init(self, children_list, attrs))
            children_tuple = tuple(children_list)
            assert 'hypergen' in c, 'Element called outside hypergen context.'
            self.t = attrs.pop('t', t)
            self.children = children_tuple
            self.attrs = attrs
            self.sep = attrs.pop('sep', '')
            self.end_char = attrs.pop('end', None)
            id_ = self.attrs.get('id_', self.attrs.pop('id', None))
            if type(id_) in (tuple, list):
                id_ = '-'.join(str(x) for x in id_)
            self.attrs['id_'] = id_
            if id_ is not None:
                assert id_ not in c.hypergen['ids'], f'Duplicate id: {id_}'
                c.hypergen['ids'].add(id_)
            self.i = len(c.hypergen.into)
            c.hypergen.into.extend(self.start())
            c.hypergen.into.extend(self.end())
            self.j = len(c.hypergen.into)
            super().__init__()

    def __enter__(self) -> base_element:
        c.hypergen.into.extend(self.start())
        self.delete()
        return self

    def __exit__(self, *exc: object) -> None:
        if not self.void:
            c.hypergen.into.extend(self.end())

    def __repr__(self) -> str:
        from flask_hypergen.liveview import THIS

        def value(v):
            if v is THIS:
                return 'THIS'
            if callable(v) and hasattr(v, 'hypergen_callback_signature'):
                name, a, kw = v.hypergen_callback_signature
                return f'{name}({signature(a, kw)})'
            if callable(v):
                if hasattr(v, '__name__'):
                    return '.'.join((v.__module__, v.__name__)).replace('builtins.', '')
                return repr(v)
            if type(v) is str:
                return f'"{v}"'
            return repr(v)

        def signature(a, kw):
            a, kw = deepcopy(a), deepcopy(kw)
            return ', '.join(
                [value(x) for x in a] + [f'{k}={value(v)}' for k, v in kw.items() if v is not None],
            )

        return f'{self.__class__.__name__}({signature(self.children, self.attrs)})'

    def as_string(self) -> str:
        into = self.start()
        into.extend(self.end())
        return join_html(into)

    def delete(self) -> None:
        for i in range(self.i, self.j):
            c.hypergen.into[i] = DELETED

    def format_children(
        self,
        children: list[Any] | tuple[Any, ...] | GeneratorType,
        nested: bool = False,
    ) -> list[Any]:
        into: list[Any] = []
        sep = self.t(self.sep)
        for x in children:
            if x in ('', None):
                continue
            if issubclass(type(x), base_element):
                x.delete()
                into.append(x)
            elif type(x) is Component:
                x.delete()
                into.extend(x.into)
            elif type(x) in (list, tuple, GeneratorType):
                into.extend(self.format_children(list(x), nested=True))
            elif callable(x):
                into.append(x)
            else:
                into.append(self.t(x))
            if sep:
                into.append(sep)
        if sep and children:
            into.pop()
        if self.end_char and not nested:
            into.append(self.t(self.end_char))
        return into

    def ensure_id(self) -> None:
        assert self.attrs['id_'] is not None, (
            f"This element needs an id_='myid' attribute: {self!r}"
        )

    def attribute(self, key: str, value: Any) -> list[Any]:
        key = t(key).rstrip('_').replace('_', '-')
        if value == OMIT or value is None:
            return []
        if callable(value):
            return value(self, key, value)
        if type(value) is bool:
            return [' ', key] if value is True else []
        if key == 'style' and type(value) in (dict, OrderedDict):
            return [
                ' ',
                key,
                '="',
                ';'.join(t(k.replace('_', '-')) + ':' + t(v) for k, v in value.items()),
                '"',
            ]
        if key == 'class' and type(value) in (list, tuple, set):
            return [' ', key, '="', t(' '.join(value)), '"']
        value = '' if value is None else t(value)
        return [' ', key, '="', value, '"']

    def start(self) -> list[Any]:
        cache = getattr(self, '_start_cache', None)
        if cache:
            return cache
        into = ['<', self.tag]
        for key, value in self.attrs.items():
            into.extend(self.attribute(key, value))
        if self.void:
            into.append('/')
        into.append('>')
        into.extend(self.format_children(self.children))
        self._start_cache = into
        return into

    def end(self) -> list[str]:
        return [f'</{self.tag}>'] if not self.void else ['']


class base_element_void(base_element):
    void = True


class Component:
    def __init__(self, into: list[Any] | contextlist, i: int, j: int) -> None:
        self.into = into
        self.i = i
        self.j = j

    def delete(self) -> None:
        for i in range(self.i, self.j):
            c.hypergen.into[i] = DELETED


def component(func):
    @wraps(func)
    def _(*args, **kwargs):
        with c(into=contextlist('target_id'), at='hypergen'):
            func(*args, **kwargs)
            into = c.hypergen.into
        i = len(c.hypergen.into)
        c.hypergen.into.extend(into)
        j = len(c.hypergen.into)
        return Component(into, i, j)

    return _


class input_(base_element_void):
    def __init__(self, *children, **attrs):
        type_ = attrs.get('type_', attrs.pop('type', None))
        if type_:
            attrs['type_'] = type_
        if type_ == 'radio':
            assert attrs.get('name'), 'Name must be set for radio buttons.'
        super().__init__(*children, **attrs)

    def attribute(self, key, value):
        if key != 'value':
            return super().attribute(key, value)
        type_ = self.attrs.get('type_', None)
        if type_ == 'datetime-local' and type(value) is datetime:
            return [' ', key, '="', value.strftime('%Y-%m-%dT%H:%M:%S'), '"']
        if type_ == 'month' and type(value) is dict:
            return [' ', key, '="', f'{value["year"]:04}-{value["month"]:02}', '"']
        if type_ == 'week' and type(value) is dict:
            return [' ', key, '="', f'{value["year"]:04}-W{value["week"]:02}', '"']
        return super().attribute(key, value)


class a(base_element):
    def __init__(self, *children, **attrs):
        class_active = attrs.pop('class_active', None)
        href = attrs.get('href')
        if class_active and href:
            from flask_hypergen.liveview import url_is_active

            if url_is_active(href):
                attrs['class'] = add_class(attrs.get('class'), class_active)
        super().__init__(*children, **attrs)


class link(base_element):
    def __init__(self, href=OMIT, rel='stylesheet', **attrs):
        type_ = attrs.get('type_', attrs.pop('type', 'text/css'))
        attrs['type_'] = type_
        attrs['href'] = href
        super().__init__(rel=rel, **attrs)


class script(base_element):
    def __init__(self, *children, **attrs):
        attrs['t'] = lambda x, **kwargs: x
        super().__init__(*children, **attrs)


class style(base_element):
    def __init__(self, *children, **attrs):
        attrs['t'] = lambda x, **kwargs: x
        super().__init__(*children, **attrs)


class abbr(base_element):
    pass


class acronym(base_element):
    pass


class address(base_element):
    pass


class applet(base_element):
    pass


class area(base_element_void):
    pass


class article(base_element):
    pass


class aside(base_element):
    pass


class audio(base_element):
    pass


class b(base_element):
    pass


class base(base_element_void):
    pass


class basefont(base_element):
    pass


class bdi(base_element):
    pass


class bdo(base_element):
    pass


class big(base_element):
    pass


class blockquote(base_element):
    pass


class body(base_element):
    pass


class br(base_element_void):
    pass


class button(base_element):
    pass


class canvas(base_element):
    pass


class caption(base_element):
    pass


class center(base_element):
    pass


class cite(base_element):
    pass


class code(base_element):
    pass


class col(base_element_void):
    pass


class colgroup(base_element):
    pass


class data(base_element):
    pass


class datalist(base_element):
    pass


class dd(base_element):
    pass


class del_(base_element):
    pass


class details(base_element):
    pass


class dfn(base_element):
    pass


class dialog(base_element):
    pass


class dir_(base_element):
    pass


class div(base_element):
    pass


class dl(base_element):
    pass


class dt(base_element):
    pass


class em(base_element):
    pass


class embed(base_element_void):
    pass


class fieldset(base_element):
    pass


class figcaption(base_element):
    pass


class figure(base_element):
    pass


class font(base_element):
    pass


class footer(base_element):
    pass


class form(base_element):
    pass


class frame(base_element):
    pass


class frameset(base_element):
    pass


class h1(base_element):
    pass


class h2(base_element):
    pass


class h3(base_element):
    pass


class h4(base_element):
    pass


class h5(base_element):
    pass


class h6(base_element):
    pass


class head(base_element):
    pass


class header(base_element):
    pass


class hr(base_element_void):
    pass


class html(base_element):
    pass


class i(base_element):
    pass


class iframe(base_element):
    pass


class img(base_element_void):
    pass


class ins(base_element):
    pass


class kbd(base_element):
    pass


class label(base_element):
    pass


class legend(base_element):
    pass


class li(base_element):
    pass


class main(base_element):
    pass


class map_(base_element):
    pass


class mark(base_element):
    pass


class meta(base_element_void):
    pass


class meter(base_element):
    pass


class nav(base_element):
    pass


class noframes(base_element):
    pass


class noscript(base_element):
    pass


class object_(base_element):
    pass


class ol(base_element):
    pass


class optgroup(base_element):
    pass


class option(base_element):
    pass


class output(base_element):
    pass


class p(base_element):
    pass


class param(base_element_void):
    pass


class picture(base_element):
    pass


class pre(base_element):
    pass


class progress(base_element):
    pass


class q(base_element):
    pass


class rp(base_element):
    pass


class rt(base_element):
    pass


class ruby(base_element):
    pass


class s(base_element):
    pass


class samp(base_element):
    pass


class section(base_element):
    pass


class select(base_element):
    pass


class small(base_element):
    pass


class source(base_element_void):
    pass


class span(base_element):
    pass


class strike(base_element):
    pass


class strong(base_element):
    pass


class sub(base_element):
    pass


class summary(base_element):
    pass


class sup(base_element):
    pass


class svg(base_element):
    pass


class table(base_element):
    pass


class tbody(base_element):
    pass


class td(base_element):
    pass


class template(base_element):
    pass


class textarea(base_element):
    pass


class tfoot(base_element):
    pass


class th(base_element):
    pass


class thead(base_element):
    pass


class time_(base_element):
    pass


class title(base_element):
    pass


class tr(base_element):
    pass


class track(base_element_void):
    pass


class tt(base_element):
    pass


class u(base_element):
    pass


class ul(base_element):
    pass


class var(base_element):
    pass


class video(base_element):
    pass


class wbr(base_element_void):
    pass


def doctype(type_: str = 'html') -> None:
    raw('<!DOCTYPE ', type_, '>')


_TAG_NAMES = [
    'abbr',
    'acronym',
    'address',
    'applet',
    'area',
    'article',
    'aside',
    'audio',
    'b',
    'base',
    'basefont',
    'bdi',
    'bdo',
    'big',
    'blockquote',
    'body',
    'br',
    'button',
    'canvas',
    'caption',
    'center',
    'cite',
    'code',
    'col',
    'colgroup',
    'data',
    'datalist',
    'dd',
    'del_',
    'details',
    'dfn',
    'dialog',
    'dir_',
    'div',
    'dl',
    'dt',
    'em',
    'embed',
    'fieldset',
    'figcaption',
    'figure',
    'font',
    'footer',
    'form',
    'frame',
    'frameset',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'head',
    'header',
    'hr',
    'html',
    'i',
    'iframe',
    'img',
    'ins',
    'kbd',
    'label',
    'legend',
    'li',
    'main',
    'map_',
    'mark',
    'meta',
    'meter',
    'nav',
    'noframes',
    'noscript',
    'object_',
    'ol',
    'optgroup',
    'option',
    'output',
    'p',
    'param',
    'picture',
    'pre',
    'progress',
    'q',
    'rp',
    'rt',
    'ruby',
    's',
    'samp',
    'section',
    'select',
    'small',
    'source',
    'span',
    'strike',
    'strong',
    'sub',
    'summary',
    'sup',
    'svg',
    'table',
    'tbody',
    'td',
    'template',
    'textarea',
    'tfoot',
    'th',
    'thead',
    'time_',
    'title',
    'tr',
    'track',
    'tt',
    'u',
    'ul',
    'var',
    'video',
    'wbr',
]
time = time_

__all__ = [
    *_TAG_NAMES,
    'COMMANDS',
    'Component',
    'FULL',
    'HTML',
    'HypergenResult',
    'HypergenSettings',
    'HYPERGEN_RETURNS',
    'OMIT',
    'TemplatePlugin',
    'a',
    'add_class',
    'base_element',
    'base_element_void',
    'component',
    'doctype',
    'hprint',
    'hypergen',
    'hypergen_to_response',
    'input_',
    'join_html',
    'link',
    'on_url',
    'plugins_build',
    'raw',
    'settings_load',
    'script',
    'style',
    'time',
    'write',
]
