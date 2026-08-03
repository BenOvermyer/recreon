---
description: Verify a balance/constant table was transcribed exactly from Pascal
agent: transcriber
subtask: true
---
Verify that the balance/constant table `$1` in the Python port matches its declaration in the Turbo Pascal source exactly — same dimensions, same values, same key correspondence.

Source locations:
- `datacnst.py` tables → `original/DATACNST.PAS` (CombatTable, ThgAdj, RawM, ClassIndAdj, FuelCons, CargoSpace, ObjName).
- `attack.py` tables → `original/ATTACK.PAS` (CombatTechAdj, CombatClassAdj, CombatBaseAdj, CombatPower, GDMLaunch, GDMKill — declared inside ATTACK.PAS, not DATACNST).

Report any mismatch with Pascal file:line and Python file:line, expected vs. found value. For `CargoSpace` and `ObjName`, state that no Pascal source exists to check against.