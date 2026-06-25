from __future__ import annotations

import importlib
import pkgutil

from secretary.router import Router


def load_commands(router: Router) -> None:
    for module_info in pkgutil.iter_modules(__path__):
        module = importlib.import_module(f"{__name__}.{module_info.name}")
        register = getattr(module, "register", None)
        if callable(register):
            register(router)

