# AI CLI Preparation - Documentation Index

**Version:** 2.0.0
**Last Updated:** 2025-11-03

## Overview

AI CLI Preparation is a specialized environment audit tool designed to ensure AI coding agents (like Claude Code) have access to all necessary developer tools. This documentation provides comprehensive technical details for developers, contributors, and integrators.

**Architecture:** Modular design with 18 specialized Python modules and 73 JSON tool catalog entries, evolved from a 3,387-line monolith to a maintainable, extensible system.

**Project Status:**
- **Phase 1 (Detection & Auditing):** ✅ Complete - Modular refactoring complete (v2.0.0)
- **Phase 2 (Installation & Upgrade):** ✅ Complete - Full implementation with comprehensive testing

## Documentation Structure

### For Developers & Contributors

#### Core Architecture (Modular 2.0)

0. **[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)** - Migrating to Modular Architecture ⭐ **NEW**
   - Transition from monolithic to modular architecture
   - API compatibility and breaking changes
   - Entry point changes (cli_audit.py → audit.py)
   - Module-by-module migration strategies

1. **[ARCHITECTURE.md](ARCHITECTURE.md)** - System Design & Implementation
   - Modular architecture with 18 specialized modules
   - Component interaction and data flows
   - Threading model and synchronization
   - HTTP layer with retries and rate limiting
   - Cache hierarchy and resilience patterns

2. **[CATALOG_GUIDE.md](CATALOG_GUIDE.md)** - JSON Catalog System ⭐ **NEW**
   - Tool definition schema and structure
   - 73 JSON catalog entries
   - Creating and managing catalog entries
   - ToolCatalog API and usage patterns
   - Community contribution workflows

#### Phase 1: Detection & Auditing

3. **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Quick Lookup & Cheat Sheet ⭐
   - One-liners for common operations
   - Environment variable reference
   - Common workflows and patterns
   - jq queries and debugging commands

4. **[API_REFERENCE.md](API_REFERENCE.md)** - Comprehensive API Documentation
   - Complete API reference covering 100+ public APIs
   - All 18 modules with detailed examples
   - Detection, installation, upgrade, reconciliation APIs
   - Configuration and environment variables
   - Advanced usage patterns and integration examples

5. **[FUNCTION_REFERENCE.md](FUNCTION_REFERENCE.md)** - Function Reference Card
   - Categorized function quick lookup
   - Parameters and return types
   - Usage examples and patterns
   - Cross-references to detailed docs

6. **[TOOL_ECOSYSTEM.md](TOOL_ECOSYSTEM.md)** - Tool Catalog
   - Complete 70+ tool reference
   - Categories and use cases
   - Upgrade strategies per tool
   - Role-based presets

7. **[DEPLOYMENT.md](DEPLOYMENT.md)** - Operations Guide
   - Makefile target reference
   - Installation script usage
   - Snapshot workflow patterns
   - Offline mode configuration

8. **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Problem Solving
   - Common issues and solutions
   - Debugging techniques
   - Performance optimization
   - Network timeout handling

#### Phase 2: Installation & Upgrade Management

9. **[PHASE2_API_REFERENCE.md](PHASE2_API_REFERENCE.md)** - Phase 2 API Documentation ⭐
   - Installation, upgrade, and reconciliation APIs
   - Environment detection and configuration
   - Bulk operations and dependency resolution
   - Breaking change management
   - Package manager selection

10. **[CLI_REFERENCE.md](CLI_REFERENCE.md)** - Command-Line Reference
    - All CLI commands and options
    - Environment variable reference (60+ variables)
    - Output formats and usage patterns
    - Common workflows and examples

11. **[TESTING.md](TESTING.md)** - Testing Guide
    - Test organization and structure
    - Running tests (unit, integration, E2E)
    - Writing tests and fixtures
    - Mocking patterns and best practices
    - Coverage requirements and CI integration

12. **[ERROR_CATALOG.md](ERROR_CATALOG.md)** - Error Reference
    - Complete error categorization
    - Causes, resolutions, and troubleshooting
    - InstallError exception patterns
    - Retryable error detection
    - Exit codes and debugging

13. **[INTEGRATION_EXAMPLES.md](INTEGRATION_EXAMPLES.md)** - Integration Patterns
    - CI/CD integration (GitHub Actions, GitLab CI)
    - Development workflow automation
    - Custom toolchain management
    - Python API integration examples
    - Configuration patterns

#### Contributing

14. **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** - Contributing Guide
    - How to add new tools
    - Testing strategies and validation
    - Code organization and style
    - Common contribution patterns

15. **[../scripts/README.md](../scripts/README.md)** - Installation Scripts
    - All 14+ installation scripts documented
    - Actions: install, update, uninstall, reconcile
    - Per-script usage and best practices
    - Troubleshooting script issues

### Planning & Specifications

16. **[PRD.md](PRD.md)** - Product Requirements Document
    - Phase 1 summary (detection and auditing)
    - Phase 2 specification (installation and upgrade management)
    - User stories and success criteria
    - Risk assessment and mitigation strategies

17. **[PHASE2_IMPLEMENTATION.md](PHASE2_IMPLEMENTATION.md)** - Implementation Roadmap
    - 5 implementation phases with timelines
    - Deliverables and success criteria per phase
    - Testing strategies and rollout plan
    - Risk mitigation and validation

18. **[PHASE2_COMPLETION_REPORT.md](PHASE2_COMPLETION_REPORT.md)** - Phase 2 Completion
    - Implementation summary and metrics
    - Architectural achievements
    - Testing and quality validation
    - Future roadmap and Phase 3 planning

19. **[CONFIGURATION_SPEC.md](CONFIGURATION_SPEC.md)** - Configuration Reference
    - .cli-audit.yml schema and syntax
    - File locations and precedence rules
    - Version specification syntax
    - Examples for all environments

20. **[adr/README.md](adr/README.md)** - Architecture Decision Records
    - ADR process and templates
    - Index of all architectural decisions
    - Phase 2 decision rationale

### For AI Coding Agents

- **[../claudedocs/](../claudedocs/)** - AI Agent Context
  - Project analysis and technical summaries
  - Integration guides and patterns
  - Session context and memory

## Quick Navigation

### By Role

**First-Time Users:**
Start with [QUICK_REFERENCE.md](QUICK_REFERENCE.md) ⭐ → [CLI_REFERENCE.md](CLI_REFERENCE.md) → [TOOL_ECOSYSTEM.md](TOOL_ECOSYSTEM.md) → [DEPLOYMENT.md](DEPLOYMENT.md)

**Existing Users (Pre-v2.0):**
Start with [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) ⭐ → [ARCHITECTURE.md](ARCHITECTURE.md) → [CATALOG_GUIDE.md](CATALOG_GUIDE.md)

**Contributors:**
Start with [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) → [ARCHITECTURE.md](ARCHITECTURE.md) → [PHASE2_API_REFERENCE.md](PHASE2_API_REFERENCE.md) → [TESTING.md](TESTING.md)

**Maintainers:**
Start with [ARCHITECTURE.md](ARCHITECTURE.md) → [PHASE2_API_REFERENCE.md](PHASE2_API_REFERENCE.md) → [ERROR_CATALOG.md](ERROR_CATALOG.md) → [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

**Integrators:**
Start with [INTEGRATION_EXAMPLES.md](INTEGRATION_EXAMPLES.md) ⭐ → [PHASE2_API_REFERENCE.md](PHASE2_API_REFERENCE.md) → [CLI_REFERENCE.md](CLI_REFERENCE.md) → [CONFIGURATION_SPEC.md](CONFIGURATION_SPEC.md)

**Product/Planning:**
Start with [PRD.md](PRD.md) → [adr/README.md](adr/README.md) → [PHASE2_IMPLEMENTATION.md](PHASE2_IMPLEMENTATION.md) → [PHASE2_COMPLETION_REPORT.md](PHASE2_COMPLETION_REPORT.md)

**AI Agent Developers:**
Start with [../claudedocs/](../claudedocs/) → [INTEGRATION_EXAMPLES.md](INTEGRATION_EXAMPLES.md) → [PHASE2_API_REFERENCE.md](PHASE2_API_REFERENCE.md) → [TOOL_ECOSYSTEM.md](TOOL_ECOSYSTEM.md)

**Operators/DevOps:**
Start with [QUICK_REFERENCE.md](QUICK_REFERENCE.md) → [CLI_REFERENCE.md](CLI_REFERENCE.md) → [DEPLOYMENT.md](DEPLOYMENT.md) → [../scripts/README.md](../scripts/README.md)

### By Task

**Quick Command Lookup:**
[QUICK_REFERENCE.md](QUICK_REFERENCE.md) ⭐ → [CLI_REFERENCE.md](CLI_REFERENCE.md) - Start here for common operations

**Upgrading to v2.0:**
[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) ⭐ → [ARCHITECTURE.md#modular-design](ARCHITECTURE.md#modular-design)

**Adding a New Tool:**
[CATALOG_GUIDE.md](CATALOG_GUIDE.md) ⭐ → [DEVELOPER_GUIDE.md#adding-tools](DEVELOPER_GUIDE.md#adding-tools)

**Understanding Modular Architecture:**
[ARCHITECTURE.md#overview](ARCHITECTURE.md#overview) → [ARCHITECTURE.md#module-organization](ARCHITECTURE.md#module-organization)

**Using Phase 1 API (Audit):**
[FUNCTION_REFERENCE.md](FUNCTION_REFERENCE.md) → [API_REFERENCE.md](API_REFERENCE.md)

**Using Phase 2 API (Install/Upgrade):**
[PHASE2_API_REFERENCE.md](PHASE2_API_REFERENCE.md) ⭐ → [INTEGRATION_EXAMPLES.md](INTEGRATION_EXAMPLES.md)

**Installing Tools:**
[INTEGRATION_EXAMPLES.md](INTEGRATION_EXAMPLES.md) → [CLI_REFERENCE.md](CLI_REFERENCE.md) → [../scripts/README.md](../scripts/README.md)

**Debugging Issues:**
[ERROR_CATALOG.md](ERROR_CATALOG.md) ⭐ → [TROUBLESHOOTING.md](TROUBLESHOOTING.md) → [CLI_REFERENCE.md](CLI_REFERENCE.md)

**Writing Tests:**
[TESTING.md](TESTING.md) → [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)

**CI/CD Integration:**
[INTEGRATION_EXAMPLES.md#cicd-integration](INTEGRATION_EXAMPLES.md#cicd-integration) → [CLI_REFERENCE.md](CLI_REFERENCE.md)

**Running in Production:**
[DEPLOYMENT.md#makefile-targets](DEPLOYMENT.md#makefile-targets) → [DEPLOYMENT.md#offline-mode](DEPLOYMENT.md#offline-mode)

**Understanding Phase 2 Plans:**
[PRD.md](PRD.md) → [adr/README.md](adr/README.md) → [PHASE2_IMPLEMENTATION.md](PHASE2_IMPLEMENTATION.md) → [CONFIGURATION_SPEC.md](CONFIGURATION_SPEC.md)

**Configuring Tool Installation:**
[CONFIGURATION_SPEC.md](CONFIGURATION_SPEC.md) → [INTEGRATION_EXAMPLES.md#configuration-patterns](INTEGRATION_EXAMPLES.md#configuration-patterns)

**Understanding Architectural Decisions:**
[adr/README.md](adr/README.md) - Browse ADR index for specific decisions

**Working with Catalog System:**
[CATALOG_GUIDE.md](CATALOG_GUIDE.md) ⭐ → [API_REFERENCE.md#catalog-module](API_REFERENCE.md#catalog-module)

## External Resources

- **Main README:** [../README.md](../README.md) - User-focused documentation
- **Repository:** [github.com/netresearch/coding_agent_cli_toolset](https://github.com/netresearch/coding_agent_cli_toolset)
- **Claude Code:** [@anthropic-ai/claude-code](https://www.npmjs.com/package/@anthropic-ai/claude-code)

## Documentation Philosophy

This documentation follows these principles:

1. **Complementary to README** - Focuses on technical depth, not user instructions
2. **Developer-Focused** - Assumes technical proficiency
3. **Comprehensive** - Covers architecture, API, and implementation details
4. **Practical** - Includes examples, patterns, and real-world scenarios
5. **AI-Agent-Aware** - Separate context for AI coding agents
6. **Modular-First** - Documents the v2.0 modular architecture comprehensively

## Contributing to Documentation

Documentation improvements are welcome! Please:

1. Keep technical accuracy as the highest priority
2. Include code examples where relevant
3. Link to related sections for cross-referencing
4. Update INDEX.md when adding new documents
5. Follow the existing formatting style
6. Consider migration impact for architectural changes

## Version History

- **v2.0.0 (2025-11-03)**: Modular architecture release
  - 18 specialized Python modules
  - 73 JSON tool catalog entries
  - New entry point: audit.py
  - Backward-compatible API via __init__.py

- **v2.0.0-alpha.6 (2025-10-13)**: Phase 2 implementation complete
  - Installation and upgrade management
  - Configuration system
  - Breaking change detection

- **v1.0 (earlier)**: Phase 1 - Detection and auditing with monolithic design

---

**Quick Start:** If you're new to the project, start with the [main README](../README.md), then come back here for deep technical details. Existing users should review [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) for v2.0 changes.
