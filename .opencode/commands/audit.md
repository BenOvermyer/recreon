---
description: Faithfulness review of a ported module vs its Pascal source
agent: auditor
subtask: true
---
Audit the ported Python module `$1` against its Turbo Pascal source for faithfulness, applying the 10-rule checklist (RNG routing, DIV vs //, Round/Trunc/Val, subrange loop endpoints, 1-based indexing, enum ordinals, TechnologyTypes unity, original-bug preservation, const transcription, coordinates).

Match the module name to its Pascal unit via `docs/ARCHITECTURE.md`. For each deviation, report rule number, Pascal file:line, Python file:line, original behaviour, port behaviour, and gameplay consequence. Do not fix — hand off fixes to `@porter` and unfiled original-bug discoveries to `@bug-filer`.