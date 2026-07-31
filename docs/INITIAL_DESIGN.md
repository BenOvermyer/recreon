# Re:creon - Initial Design Document

## Project Overview

Re:creon is a faithful Python recreation of **Anacreon: Reconstruction 4021**, a classic 4X space strategy game originally written in Turbo Pascal. This project aims to preserve the gameplay mechanics and strategic depth of the original while modernizing the codebase and user interface.

## Original Game Summary

Anacreon is a turn-based galactic empire simulation where players manage worlds, fleets, technology, and diplomacy across a sector-based star map. Each turn represents one year of galactic history.

### Core Gameplay Elements

- **Economic Management**: Designate worlds for specific roles (agricultural, mining, shipyard, research, etc.). Worlds produce raw materials consumed by production industries.
- **Technology Progression**: 11 tech levels from Pre-Tech to Gate. Research is probabilistic based on capital and university worlds.
- **Fleet Operations**: Deploy fleets with scripted orders. Fleets consume trillum fuel and move at different speeds (warp=1/yr, jump=10/yr).
- **Multi-Layered Combat**: 5 orbital shells with targeting priorities, tech advantages, escort mechanics, and ground assault.
- **Political Management**: Revolution indices can lead to rebellion. Military presence affects unrest.
- **Construction**: Build starbases, stargates, SRM mines, and other structures over multiple years.
- **AI Opponents**: 5 distinct AI types with personality traits and diplomatic policies.

## Technical Approach

### Architecture Philosophy

**Faithful Port**: The Python architecture mirrors the original Pascal code structure to ensure correctness and maintainability. Each Pascal module maps to a corresponding Python module.

### Technology Stack

- **Language**: Python 3.10+ (for pattern matching and modern features)
- **UI Framework**: Textual (Rich TUI) - modern terminal UI framework
- **Package Management**: uv - fast Python package installer and resolver
- **Testing**: pytest for unit and integration tests

### Key Design Decisions

1. **Data Structures**: Use Python `dataclass` for records, `Enum` for enumerated types
2. **Index Strategy**: Maintain 1-based indexing to match Pascal source (index 0 unused)
3. **Global State**: Encapsulate in `GameEnvironment` class instead of global variables
4. **Memory Management**: Python's GC handles cleanup; no manual memory management needed
5. **UI Approach**: Textual provides modern TUI while maintaining text-mode aesthetic

## Documentation Structure

- **INITIAL_DESIGN.md** (this file): Project overview and high-level design
- **ARCHITECTURE.md**: Detailed module breakdown and file mappings
- **IMPLEMENTATION_PLAN.md**: Phased implementation roadmap with milestones
- **TRANSLATION_NOTES.md**: Pascal to Python translation patterns and gotchas
- **GAME_MECHANICS.md**: Detailed game mechanics reference (to be written)

## Success Criteria

The project is successful when:

- ✅ Can start new game with 1-8 empires
- ✅ Galaxy generates with planets, starbases, phenomena
- ✅ Planets produce resources, population grows, tech advances
- ✅ Can deploy fleets, set destinations, transfer cargo
- ✅ Fleets move, consume fuel, arrive at destinations
- ✅ Combat resolves with proper orbital mechanics
- ✅ Can conquer worlds
- ✅ Can build starbases, gates, SRM mines
- ✅ AI empires take turns and make decisions
- ✅ Can save/load games
- ✅ UI is functional and usable
- ✅ Game balance matches original

## Development Timeline

Estimated 26 weeks for complete implementation:

- **Weeks 1-4**: Foundation (types, data structures, galaxy, basic UI)
- **Weeks 5-8**: Economy, then galaxy generation from scenario files
- **Weeks 9-12**: Fleets, orders and combat
- **Weeks 13-14**: Construction and advanced features
- **Weeks 15-18**: AI system
- **Weeks 19-22**: UI polish, save/load, scenario front end
- **Weeks 23-26**: Testing and validation

## Risk Mitigation

1. **Complexity**: Incremental development with clear milestones
2. **Correctness**: Validate against Pascal source, write tests early
3. **Performance**: Optimize later if needed (consider numpy for arrays)
4. **UI Fidelity**: Focus on functionality over exact visual replication
5. **Scope Creep**: Stick to original features until base is complete

## Next Steps

Begin Phase 1: Project setup and core data structures. See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for detailed phases.
