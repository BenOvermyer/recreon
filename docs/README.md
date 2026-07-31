# Re:creon Documentation

Welcome to the Re:creon project documentation. This directory contains the complete design and implementation documentation for the Python recreation of Anacreon: Reconstruction 4021.

## Documentation Index

### [INITIAL_DESIGN.md](INITIAL_DESIGN.md)
Project overview and high-level design decisions. Start here for a quick understanding of what Re:creon is and how it's structured.

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
Phased implementation roadmap with clear milestones and deliverables.

**Contents:**
- 9 implementation phases
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

1. **Understand the project**: Read [INITIAL_DESIGN.md](INITIAL_DESIGN.md)
2. **Review architecture**: Skim [ARCHITECTURE.md](ARCHITECTURE.md)
3. **Check implementation plan**: Review [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
4. **Start coding**: Follow Phase 1 in the implementation plan
5. **Reference translation notes**: Keep [TRANSLATION_NOTES.md](TRANSLATION_NOTES.md) handy

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

**Current Phase**: Phases 1-2 complete. Core types and data structures are
ported (`types.py`, `datastrc.py`, `datacnst.py`, `cdetypes.py`,
`npe/types.py`), along with the galaxy grid (`galaxy.py`), global state
(`environ.py`), utility calculations (`misc.py`, `utils/`), a subset of the
interface layer (`primintr.py`), the turn loop (`main.py`) and a Textual UI
skeleton (`ui/`). A game starts, shows an empty galaxy map, and advances
turns.

**Next Steps**: Begin Phase 3 - Planet management and economy. This is also
where galaxy generation (NEWGAME.PAS) lands, so the map stops being empty.

## Contributing

When implementing features:

1. Reference the corresponding Pascal source file
2. Follow the translation patterns in TRANSLATION_NOTES.md
3. Write tests for critical calculations
4. Update this documentation if design changes

## License

See the main README.md for license information.
