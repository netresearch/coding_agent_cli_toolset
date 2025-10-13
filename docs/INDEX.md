# AI CLI Preparation - Documentation Index

**Version:** 2.0.0-alpha.6
**Last Updated:** 2025-10-13

## Overview

AI CLI Preparation is a specialized environment audit tool designed to ensure AI coding agents (like Claude Code) have access to all necessary developer tools. This documentation provides comprehensive technical details for developers, contributors, and integrators.

**Project Status:**
- **Phase 1 (Detection & Auditing):** ✅ Complete
- **Phase 2 (Installation & Upgrade):** ✅ Implementation Complete | 📝 Documentation Complete

## Documentation Structure

### For Developers & Contributors

#### Phase 1: Detection & Auditing

1. **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Quick Lookup & Cheat Sheet ⭐
   - One-liners for common operations
   - Environment variable reference
   - Common workflows and patterns
   - jq queries and debugging commands

2. **[ARCHITECTURE.md](ARCHITECTURE.md)** - System Design & Implementation
   - Component architecture and data flows
   - Threading model and synchronization
   - HTTP layer with retries and rate limiting
   - Cache hierarchy and resilience patterns

3. **[API_REFERENCE.md](API_REFERENCE.md)** - Phase 1 API Documentation
   - Tool dataclass specification
   - Core audit functions by category
   - Configuration via environment variables
   - Cache file formats and schemas

4. **[FUNCTION_REFERENCE.md](FUNCTION_REFERENCE.md)** - Function Reference Card
   - Categorized function quick lookup
   - Parameters and return types
   - Usage examples and patterns
   - Cross-references to detailed docs

5. **[TOOL_ECOSYSTEM.md](TOOL_ECOSYSTEM.md)** - Tool Catalog
   - Complete 50+ tool reference
   - Categories and use cases
   - Upgrade strategies per tool
   - Role-based presets

6. **[DEPLOYMENT.md](DEPLOYMENT.md)** - Operations Guide
   - Makefile target reference
   - Installation script usage
   - Snapshot workflow patterns
   - Offline mode configuration

7. **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Problem Solving
   - Common issues and solutions
   - Debugging techniques
   - Performance optimization
   - Network timeout handling

#### Phase 2: Installation & Upgrade Management

8. **[PHASE2_API_REFERENCE.md](PHASE2_API_REFERENCE.md)** - Phase 2 API Documentation ⭐
   - Installation, upgrade, and reconciliation APIs
   - Environment detection and configuration
   - Bulk operations and dependency resolution
   - Breaking change management
   - Package manager selection

9. **[CLI_REFERENCE.md](CLI_REFERENCE.md)** - Command-Line Reference
   - All CLI commands and options
   - Environment variable reference (60+ variables)
   - Output formats and usage patterns
   - Common workflows and examples

10. **[TESTING.md](TESTING.md)** - Testing Guide
    - Test organization and structure
    - Running tests (unit, integration, E2E)
    - Writing tests and fixtures
    - Mocking patterns and best practices
    - Coverage requirements and CI integration

11. **[ERROR_CATALOG.md](ERROR_CATALOG.md)** - Error Reference
    - Complete error categorization
    - Causes, resolutions, and troubleshooting
    - InstallError exception patterns
    - Retryable error detection
    - Exit codes and debugging

12. **[INTEGRATION_EXAMPLES.md](INTEGRATION_EXAMPLES.md)** - Integration Patterns
    - CI/CD integration (GitHub Actions, GitLab CI)
    - Development workflow automation
    - Custom toolchain management
    - Python API integration examples
    - Configuration patterns

#### Contributing

13. **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** - Contributing Guide
    - How to add new tools
    - Testing strategies and validation
    - Code organization and style
    - Common contribution patterns

14. **[../scripts/README.md](../scripts/README.md)** - Installation Scripts
    - All 13+ installation scripts documented
    - Actions: install, update, uninstall, reconcile
    - Per-script usage and best practices
    - Troubleshooting script issues

### Planning & Specifications

15. **[PRD.md](PRD.md)** - Product Requirements Document
    - Phase 1 summary (detection and auditing)
    - Phase 2 specification (installation and upgrade management)
    - User stories and success criteria
    - Risk assessment and mitigation strategies

16. **[PHASE2_IMPLEMENTATION.md](PHASE2_IMPLEMENTATION.md)** - Implementation Roadmap
    - 5 implementation phases with timelines
    - Deliverables and success criteria per phase
    - Testing strategies and rollout plan
    - Risk mitigation and validation

17. **[CONFIGURATION_SPEC.md](CONFIGURATION_SPEC.md)** - Configuration Reference
    - .cli-audit.yml schema and syntax
    - File locations and precedence rules
    - Version specification syntax
    - Examples for all environments

18. **[adr/README.md](adr/README.md)** - Architecture Decision Records
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

**Contributors:**
Start with [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) → [ARCHITECTURE.md](ARCHITECTURE.md) → [PHASE2_API_REFERENCE.md](PHASE2_API_REFERENCE.md) → [TESTING.md](TESTING.md)

**Maintainers:**
Start with [ARCHITECTURE.md](ARCHITECTURE.md) → [PHASE2_API_REFERENCE.md](PHASE2_API_REFERENCE.md) → [ERROR_CATALOG.md](ERROR_CATALOG.md) → [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

**Integrators:**
Start with [INTEGRATION_EXAMPLES.md](INTEGRATION_EXAMPLES.md) ⭐ → [PHASE2_API_REFERENCE.md](PHASE2_API_REFERENCE.md) → [CLI_REFERENCE.md](CLI_REFERENCE.md) → [CONFIGURATION_SPEC.md](CONFIGURATION_SPEC.md)

**Product/Planning:**
Start with [PRD.md](PRD.md) → [adr/README.md](adr/README.md) → [PHASE2_IMPLEMENTATION.md](PHASE2_IMPLEMENTATION.md)

**AI Agent Developers:**
Start with [../claudedocs/](../claudedocs/) → [INTEGRATION_EXAMPLES.md](INTEGRATION_EXAMPLES.md) → [PHASE2_API_REFERENCE.md](PHASE2_API_REFERENCE.md) → [TOOL_ECOSYSTEM.md](TOOL_ECOSYSTEM.md)

**Operators/DevOps:**
Start with [QUICK_REFERENCE.md](QUICK_REFERENCE.md) → [CLI_REFERENCE.md](CLI_REFERENCE.md) → [DEPLOYMENT.md](DEPLOYMENT.md) → [../scripts/README.md](../scripts/README.md)

### By Task

**Quick Command Lookup:**
[QUICK_REFERENCE.md](QUICK_REFERENCE.md) ⭐ → [CLI_REFERENCE.md](CLI_REFERENCE.md) - Start here for common operations

**Adding a New Tool:**
[DEVELOPER_GUIDE.md#adding-tools](DEVELOPER_GUIDE.md#adding-tools) → [API_REFERENCE.md#tool-dataclass](API_REFERENCE.md#tool-dataclass)

**Understanding Architecture:**
[ARCHITECTURE.md#overview](ARCHITECTURE.md#overview) → [ARCHITECTURE.md#data-flow](ARCHITECTURE.md#data-flow)

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

## Contributing to Documentation

Documentation improvements are welcome! Please:

1. Keep technical accuracy as the highest priority
2. Include code examples where relevant
3. Link to related sections for cross-referencing
4. Update INDEX.md when adding new documents
5. Follow the existing formatting style

---

**Quick Start:** If you're new to the project, start with the [main README](../README.md), then come back here for deep technical details.
