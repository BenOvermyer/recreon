---
description: Port a Pascal unit to a faithful Python module
agent: porter
---
Port the Turbo Pascal unit `$1` to its Python counterpart under `src/recreon/`, following the project's porting conventions (CLAUDE.md §"Porting conventions").

Steps:
1. Read the Pascal unit in `original/` end to end.
2. Check `docs/ARCHITECTURE.md` for the target module's planned layout.
3. Reuse existing types/helpers from `types.py`, `datacnst.py`, `primintr.py`, etc. — don't redefine.
4. Write the Python module (name mirrors the `.PAS` filename). Keep 1-based lists, Pascal field names, IntEnum ordinals, and `_table` for constant tables.
5. Route RNG through `int_utils.rnd`, `DIV` through `pascal_div` where dividends can be negative, `Round` through `pascal_round`, `Val` through `pascal_val`.
6. Add a test under `tests/` if one is expected and missing, following `tests/conftest.py`.
7. Verify with `uv run pytest -k "$1"`.

Port original bugs faithfully and document them at the call site; flag any new defect for `@bug-filer`.