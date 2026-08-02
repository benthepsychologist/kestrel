"""kestrel collectors — stateless, provenance-out, buffer-only writes.

Contract (README.md §Contracts): collect(watch, since) -> (items, provenance).
Modules self-register into REGISTRY via @register(name) from collectors.base;
this package auto-imports every sibling module so `import collectors` alone
yields a full REGISTRY (fixes the wiring gap all five build agents flagged,
2026-07-28).

Known cross-module quirks (accepted, logged 2026-07-28):
- ts formats vary slightly (Z vs +00:00 vs date-only) — all ISO-prefixed, so
  lexicographic sort stays correct; normalize if a consumer ever needs more.
- GDELT rejects bare short keywords ("AI") — quote multi-word phrases; the
  module documents it.
"""
import pkgutil as _pkgutil
import importlib as _importlib

REGISTRY = {}


def register(name):
    def deco(fn):
        REGISTRY[name] = fn
        return fn
    return deco


# auto-import every collector module (skip private + base)
for _m in _pkgutil.iter_modules(__path__):
    if _m.name.startswith("_") or _m.name == "base":
        continue
    _importlib.import_module(f"{__name__}.{_m.name}")
