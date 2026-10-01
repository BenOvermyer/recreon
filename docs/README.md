# Re:creon Documentation

Documentation for the Python recreation of Anacreon: Reconstruction 4021.
For installation and play, start with the [project README](../README.md) and
the [player's manual](manual/chapters/02-getting-started.md).

## Documentation Index

### [INITIAL_DESIGN.md](INITIAL_DESIGN.md)
The project's original design proposal. It records early decisions and estimates,
so use the README and architecture guide for current behavior.

**Contents:**
- Project overview
- Original game summary
- Technical approach
- Success criteria
- Development timeline

### [ARCHITECTURE.md](ARCHITECTURE.md)
Detailed module breakdown and file mappings from Pascal source to Python implementation.

**Contents:**
- Complete project structure
- Module-by-module breakdown
- Data structures and types
- Module dependencies
- Key functions and their purposes

### [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
Historical implementation roadmap with completion notes. Phases 1–9 are complete;
the early sketches and estimates remain for context.

**Contents:**
- 10 implementation phases (1-9, plus 3.5 for galaxy generation)
- Week-by-week timeline
- Code examples for each phase
- Milestone definitions
- Testing strategy

### [TRANSLATION_NOTES.md](TRANSLATION_NOTES.md)
Pascal to Python translation patterns and common gotchas.

**Contents:**
- Data structure translations
- Control flow patterns
- Index adjustment strategies
- Memory management differences
- Common pitfalls
- Testing approach

## Quick Start

1. **Play the game**: Follow the [README](../README.md) and [player's manual](manual/chapters/02-getting-started.md).
2. **Understand the port**: Read [ARCHITECTURE.md](ARCHITECTURE.md) and [TRANSLATION_NOTES.md](TRANSLATION_NOTES.md).
3. **Understand its history**: Consult [INITIAL_DESIGN.md](INITIAL_DESIGN.md) and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).
4. **Check reuse terms**: Read [LICENSING.md](LICENSING.md) before distributing the project or its original-game material.

## Original Pascal Source

The original Pascal source code is available in the `original/` directory. Key files to reference:

- **TYPES.PAS** - All type definitions
- **DATASTRC.PAS** - Data structures
- **DATACNST.PAS** - Game constants
- **UPDATE.PAS** - Universe update logic
- **FLEET.PAS** - Fleet management
- **ATTACK.PAS** - Combat system
- **NPE.PAS** - AI system

## Development Status

**Phases 1–9 are complete.** The port runs from the prologue through the
turn loop, including the economy, fleets, combat, AI, menus and save/load.
The remaining work is play-testing, improvement of known original bugs and
release preparation; see [AGENTS.md](../AGENTS.md) for the port's fidelity
conventions and deliberate bug reproductions.

Fourteen scenarios are bundled: thirteen adapted from the recovered files in
`original/scenarios/` and one new scenario, `frontier.scn`. The adapted
files have revised titles and introductions; two also have structural repairs. The
[scenario provenance](../src/recreon/data/scenarios/README.md) records each
source and change. Galaxy randomness uses the ported Pascal generator, not
Python's default RNG.

## Contributing

When implementing features:

1. Reference the corresponding Pascal source file
2. Follow the translation patterns in TRANSLATION_NOTES.md
3. Write tests for critical calculations
4. Update this documentation if design changes

## License

See [LICENSING.md](LICENSING.md) for the MIT grant covering original Re:creon
work and the separate status of the original-game material.
