from __future__ import annotations

from importlib import import_module


MODULES = tuple(
    import_module(name)
    for name in (
        'flask_hypergen.context',
        'flask_hypergen.hypergen',
        'flask_hypergen.liveview',
        'flask_hypergen.template',
        'flask_hypergen.websocket',
    )
)

__all__: list[str] = []

for module in MODULES:
    for name in getattr(module, '__all__', []):
        if name in __all__:
            continue
        globals()[name] = getattr(module, name)
        __all__.append(name)
