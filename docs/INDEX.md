# AI CLI Preparation - Documentation Index

**Version:** 1.0
**Last Updated:** 2025-10-09

## Overview

AI CLI Preparation is a specialized environment audit tool designed to ensure AI coding agents (like Claude Code) have access to all necessary developer tools. This documentation provides comprehensive technical details for developers, contributors, and integrators.

## Documentation Structure

### For Developers & Contributors

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

3. **[API_REFERENCE.md](API_REFERENCE.md)** - API Documentation
   - Tool dataclass specification
   - Core functions by category
   - Configuration via environment variables
   - Cache file formats and schemas

4. **[FUNCTION_REFERENCE.md](FUNCTION_REFERENCE.md)** - Function Reference Card
   - Categorized function quick lookup
   - Parameters and return types
   - Usage examples and patterns
   - Cross-references to detailed docs

5. **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** - Contributing Guide
   - How to add new tools
   - Testing strategies and validation
   - Code organization and style
   - Common contribution patterns

6. **[TOOL_ECOSYSTEM.md](TOOL_ECOSYSTEM.md)** - Tool Catalog
   - Complete 50+ tool reference
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

9. **[../scripts/README.md](../scripts/README.md)** - Installation Scripts
   - All 13+ installation scripts documented
   - Actions: install, update, uninstall, reconcile
   - Per-script usage and best practices
   - Troubleshooting script issues

### Planning & Specifications

10. **[PRD.md](PRD.md)** - Product Requirements Document
    - Phase 1 summary (detection and auditing)
    - Phase 2 specification (installation and upgrade management)
    - User stories and success criteria
    - Risk assessment and mitigation strategies

11. **[PHASE2_IMPLEMENTATION.md](PHASE2_IMPLEMENTATION.md)** - Implementation Roadmap
    - 5 implementation phases with timelines
    - Deliverables and success criteria per phase
    - Testing strategies and rollout plan
    - Risk mitigation and validation

12. **[CONFIGURATION_SPEC.md](CONFIGURATION_SPEC.md)** - Configuration Reference
    - .cli-audit.yml schema and syntax
    - File locations and precedence rules
    - Version specification syntax
    - Examples for all environments

13. **[adr/README.md](adr/README.md)** - Architecture Decision Records
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
Start with [QUICK_REFERENCE.md](QUICK_REFERENCE.md) ⭐ → [TOOL_ECOSYSTEM.md](TOOL_ECOSYSTEM.md) → [DEPLOYMENT.md](DEPLOYMENT.md)

**Contributors:**
Start with [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) → [ARCHITECTURE.md](ARCHITECTURE.md) → [API_REFERENCE.md](API_REFERENCE.md) → [FUNCTION_REFERENCE.md](FUNCTION_REFERENCE.md)

**Maintainers:**
Start with [ARCHITECTURE.md](ARCHITECTURE.md) → [TROUBLESHOOTING.md](TROUBLESHOOTING.md) → [DEPLOYMENT.md](DEPLOYMENT.md) → [adr/README.md](adr/README.md)

**Integrators:**
Start with [TOOL_ECOSYSTEM.md](TOOL_ECOSYSTEM.md) → [API_REFERENCE.md](API_REFERENCE.md) → [DEPLOYMENT.md](DEPLOYMENT.md)

**Product/Planning:**
Start with [PRD.md](PRD.md) → [adr/README.md](adr/README.md) → [PHASE2_IMPLEMENTATION.md](PHASE2_IMPLEMENTATION.md)

**AI Agent Developers:**
Start with [../claudedocs/](../claudedocs/) → [TOOL_ECOSYSTEM.md](TOOL_ECOSYSTEM.md) → [API_REFERENCE.md](API_REFERENCE.md)

**Operators/DevOps:**
Start with [QUICK_REFERENCE.md](QUICK_REFERENCE.md) → [DEPLOYMENT.md](DEPLOYMENT.md) → [../scripts/README.md](../scripts/README.md)

### By Task

**Quick Command Lookup:**
[QUICK_REFERENCE.md](QUICK_REFERENCE.md) ⭐ - Start here for common operations

**Adding a New Tool:**
[DEVELOPER_GUIDE.md#adding-tools](DEVELOPER_GUIDE.md#adding-tools) → [API_REFERENCE.md#tool-dataclass](API_REFERENCE.md#tool-dataclass)

**Understanding Architecture:**
[ARCHITECTURE.md#overview](ARCHITECTURE.md#overview) → [ARCHITECTURE.md#data-flow](ARCHITECTURE.md#data-flow)

**Using Functions:**
[FUNCTION_REFERENCE.md](FUNCTION_REFERENCE.md) → [API_REFERENCE.md](API_REFERENCE.md)

**Installing Tools:**
[../scripts/README.md](../scripts/README.md) → [DEPLOYMENT.md](DEPLOYMENT.md)

**Debugging Issues:**
[TROUBLESHOOTING.md#common-issues](TROUBLESHOOTING.md#common-issues) → [QUICK_REFERENCE.md](QUICK_REFERENCE.md) → [API_REFERENCE.md#environment-variables](API_REFERENCE.md#environment-variables)

**Running in Production:**
[DEPLOYMENT.md#makefile-targets](DEPLOYMENT.md#makefile-targets) → [DEPLOYMENT.md#offline-mode](DEPLOYMENT.md#offline-mode)

**Understanding Phase 2 Plans:**
[PRD.md](PRD.md) → [adr/README.md](adr/README.md) → [PHASE2_IMPLEMENTATION.md](PHASE2_IMPLEMENTATION.md) → [CONFIGURATION_SPEC.md](CONFIGURATION_SPEC.md)

**Configuring Tool Installation:**
[CONFIGURATION_SPEC.md](CONFIGURATION_SPEC.md) → [ADR-006](adr/ADR-006-configuration-file-format.md)

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
