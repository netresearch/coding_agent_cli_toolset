# ============================================================================
# AUTOMATIC COMMAND SHORTCUTS
# ============================================================================

# Catch-all for unknown targets - supports prefix and hyphenated abbreviations
# Examples:
#   make hel     → expands to "help" (prefix match)
#   make aa      → expands to "audit-auto" (hyphenated abbreviation)
#   make upd     → shows ambiguous matches: update, update-debug
#   make xyz     → error: No rule to make target
%:
	@bash -c ' \
		TARGET="$@"; \
		TARGETS=$$($(MAKE) -qp 2>/dev/null | awk -F: "/^[a-z][a-z0-9_-]+:/ {print \$$1}" | grep -v "^%" | sort -u); \
		\
		if [ -z "$$TARGETS" ]; then \
			echo "make: *** No rule to make target \"$$TARGET\". Stop." >&2; \
			exit 2; \
		fi; \
		\
		MATCHES=$$(echo "$$TARGETS" | grep "^$$TARGET" || true); \
		\
		if [ -z "$$MATCHES" ] && [ $${#TARGET} -ge 2 ]; then \
			PATTERN=$$(echo "$$TARGET" | sed "s/\(.\)/\1[^-]*-/g" | sed "s/-$$//"); \
			MATCHES=$$(echo "$$TARGETS" | grep -E "^$$PATTERN" || true); \
		fi; \
		\
		if [ -z "$$MATCHES" ]; then \
			COUNT=0; \
		else \
			COUNT=$$(echo "$$MATCHES" | wc -l); \
		fi; \
		\
		if [ $$COUNT -eq 1 ]; then \
			echo "→ Expanding \"$$TARGET\" to \"$$MATCHES\"" >&2; \
			$(MAKE) $$MATCHES; \
		elif [ $$COUNT -gt 1 ]; then \
			echo "Ambiguous shortcut \"$$TARGET\" matches:" >&2; \
			echo "$$MATCHES" | sed "s/^/  - /" >&2; \
			exit 1; \
		else \
			echo "make: *** No rule to make target \"$$TARGET\". Stop." >&2; \
			exit 2; \
		fi'
