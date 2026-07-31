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

**Current Phase**: Phases 1-3 complete. On top of the Phase 1-2 foundation,
the world economy is ported: `update.py` (UPDATE.PAS), `design.py`,
`resource.py`, `news.py` and `intrface.py`. Worlds produce resources, grow
and starve, advance and regress in tech, and rebel.

**Next Steps**: Begin Phase 3.5 - Galaxy generation (NEWGAME.PAS). This must
come before Phase 4: until it is ported nothing populates a galaxy, and
worlds have to be placed by hand.

**Known gap**: the original `*.SCN` scenario files are not in this repo, and
NEWGAME.PAS is a scenario interpreter rather than a procedural generator. The
file format is recoverable from the parser, so scenarios can be authored, but
the galaxies the original shipped cannot be reproduced. See Phase 3.5.0.

## Contributing

When implementing features:

1. Reference the corresponding Pascal source file
2. Follow the translation patterns in TRANSLATION_NOTES.md
3. Write tests for critical calculations
4. Update this documentation if design changes

## License

See the main README.md for license information.
