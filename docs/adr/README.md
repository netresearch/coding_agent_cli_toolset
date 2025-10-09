# Architecture Decision Records (ADRs)

**Purpose:** Document significant architectural decisions for AI CLI Preparation Phase 2

## What is an ADR?

An Architecture Decision Record (ADR) captures a single architectural decision along with its context, consequences, and rationale. ADRs help teams:

- Understand why decisions were made
- Avoid revisiting settled decisions
- Onboard new contributors quickly
- Track architectural evolution over time

## ADR Process

### When to Create an ADR

Create an ADR when making decisions that:

- Impact system architecture or design patterns
- Affect multiple components or modules
- Have long-term consequences
- Involve trade-offs between competing approaches
- May be questioned or revisited in the future

### ADR Template

```markdown
# ADR-NNN: Title

**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-XXX
**Date:** YYYY-MM-DD
**Deciders:** List of people involved in decision
**Tags:** keyword1, keyword2

## Context

What is the issue we're trying to solve? What are the constraints? What alternatives did we consider?

## Decision

What decision did we make? Be specific and actionable.

## Rationale

Why did we choose this approach? What factors influenced the decision?

## Consequences

### Positive
- What benefits does this decision bring?

### Negative
- What downsides or trade-offs exist?

### Neutral
- What side effects are neither good nor bad?

## Alternatives Considered

### Alternative 1: Name
- Description
- Pros
- Cons
- Why rejected

## Implementation Notes

Any specific guidance for implementation?

## References

- Links to related docs, RFCs, issues, etc.
```

### ADR Lifecycle

1. **Proposed**: Draft created, under discussion
2. **Accepted**: Decision finalized, ready for implementation
3. **Deprecated**: No longer valid but kept for historical context
4. **Superseded**: Replaced by newer ADR (link to replacement)

### Modifying ADRs

ADRs are **immutable** once accepted. To change a decision:

1. Create a new ADR that supersedes the old one
2. Update the old ADR's status: `Superseded by ADR-XXX`
3. Link the new ADR back to the old one in References

---

## Index of ADRs

### Phase 2: Installation and Upgrade Management

| ADR | Title | Status | Date | Tags |
|-----|-------|--------|------|------|
| [001](ADR-001-context-aware-installation.md) | Context-Aware Installation Modes | Accepted | 2025-10-09 | installation, environment-detection |
| [002](ADR-002-package-manager-hierarchy.md) | Package Manager Preference Hierarchy | Accepted | 2025-10-09 | package-managers, installation |
| [003](ADR-003-parallel-installation-approach.md) | Parallel Installation Approach | Accepted | 2025-10-09 | reconciliation, installation |
| [004](ADR-004-always-latest-version-policy.md) | Always-Latest Version Policy | Accepted | 2025-10-09 | versioning, upgrades |
| [005](ADR-005-environment-detection.md) | Environment Detection Logic | Accepted | 2025-10-09 | environment-detection, context-aware |
| [006](ADR-006-configuration-file-format.md) | Configuration File Format | Accepted | 2025-10-09 | configuration, yaml |

---

## Quick Reference

### By Category

**Installation Strategy:**
- ADR-001: Context-Aware Installation Modes
- ADR-002: Package Manager Preference Hierarchy
- ADR-003: Parallel Installation Approach

**Version Management:**
- ADR-004: Always-Latest Version Policy

**Environment and Configuration:**
- ADR-005: Environment Detection Logic
- ADR-006: Configuration File Format

### By Tag

**installation:** ADR-001, ADR-002, ADR-003
**environment-detection:** ADR-001, ADR-005
**versioning:** ADR-004
**configuration:** ADR-006
**reconciliation:** ADR-003
**package-managers:** ADR-002

---

## Contributing ADRs

### Propose a New ADR

1. Copy the ADR template above
2. Number it sequentially (e.g., ADR-007)
3. Write the ADR in `docs/adr/ADR-NNN-title.md`
4. Set status to "Proposed"
5. Submit for review (PR or discussion)
6. Update this README index after acceptance

### Review Process

1. **Technical Review**: Validate technical soundness
2. **Stakeholder Review**: Ensure alignment with project goals
3. **Consensus**: Reach agreement among deciders
4. **Acceptance**: Update status to "Accepted", merge

### Best Practices

- **Be Specific**: Avoid vague decisions like "use best practices"
- **Document Trade-offs**: Explain what you're giving up
- **Link Evidence**: Reference benchmarks, docs, RFCs
- **Keep Concise**: Aim for 1-2 pages per ADR
- **Use Examples**: Concrete examples clarify abstract decisions

---

## Related Documentation

- **[PRD.md](../PRD.md)** - Product Requirements Document
- **[PHASE2_IMPLEMENTATION.md](../PHASE2_IMPLEMENTATION.md)** - Implementation roadmap
- **[CONFIGURATION_SPEC.md](../CONFIGURATION_SPEC.md)** - Configuration file specification
- **[ARCHITECTURE.md](../ARCHITECTURE.md)** - System architecture overview

---

**Last Updated:** 2025-10-09
**Maintainer:** AI CLI Preparation Team
