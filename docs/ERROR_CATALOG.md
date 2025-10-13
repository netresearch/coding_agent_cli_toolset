# Error Catalog

**Version:** 2.0.0-alpha.6
**Last Updated:** 2025-10-13

Complete reference of errors, exceptions, and failure modes in CLI Audit tool, with causes, resolutions, and troubleshooting guidance.

---

## Table of Contents

- [Error Categories](#error-categories)
- [Configuration Errors](#configuration-errors)
- [Installation Errors](#installation-errors)
- [Environment Detection Errors](#environment-detection-errors)
- [Package Manager Errors](#package-manager-errors)
- [Validation Errors](#validation-errors)
- [Network Errors](#network-errors)
- [System Errors](#system-errors)
- [Exit Codes](#exit-codes)
- [Troubleshooting](#troubleshooting)

---

## Error Categories

| Category | Severity | Retryable | Examples |
|----------|----------|-----------|----------|
| **Configuration** | High | No | Invalid config values, unsupported versions |
| **Installation** | Medium | Sometimes | Network failures, lock contention, command failures |
| **Environment** | Low | No | Invalid override values |
| **Package Manager** | High | No | PM not available, no suitable PM found |
| **Validation** | Medium | No | Binary not found, version mismatch |
| **Network** | Medium | Yes | Timeouts, connection refused, DNS failures |
| **System** | High | Sometimes | Permission denied, disk full, command not found |

---

## Configuration Errors

### CONFIG-001: Unsupported Config Version

**Error Message:**
```
ValueError: Unsupported config version: X. Expected version 1
```

**Cause:**
- Configuration file specifies unsupported schema version
- Current supported version: 1

**Resolution:**
1. Update config file to use `version: 1`
2. Review [Configuration Files](CLI_REFERENCE.md#configuration-files) for current schema

**Example:**
```yaml
# ❌ Wrong
version: 2

# ✅ Correct
version: 1
```

### CONFIG-002: Invalid Environment Mode

**Error Message:**
```
ValueError: Invalid environment_mode: X. Must be one of: auto, ci, server, workstation
```

**Cause:**
- Configuration specifies invalid environment mode
- Valid modes: `auto`, `ci`, `server`, `workstation`

**Resolution:**
```yaml
# ❌ Wrong
environment:
  mode: production

# ✅ Correct
environment:
  mode: server
```

### CONFIG-003: Invalid Reconciliation Strategy

**Error Message:**
```
ValueError: Invalid reconciliation strategy: X. Must be 'parallel' or 'aggressive'
```

**Cause:**
- Invalid `reconciliation` preference value
- Valid values: `parallel` (keep all), `aggressive` (remove non-preferred)

**Resolution:**
```yaml
preferences:
  reconciliation: parallel  # or 'aggressive'
```

### CONFIG-004: Invalid Breaking Changes Policy

**Error Message:**
```
ValueError: Invalid breaking_changes setting: X. Must be 'accept', 'warn', or 'reject'
```

**Cause:**
- Invalid `breaking_changes` preference value
- Valid values: `accept`, `warn`, `reject`

**Resolution:**
```yaml
preferences:
  breaking_changes: warn  # accept, warn, or reject
```

### CONFIG-005: Invalid Timeout Value

**Error Message:**
```
ValueError: Invalid timeout_seconds: X. Must be between 1 and 60
```

**Cause:**
- Timeout value outside valid range (1-60 seconds)

**Resolution:**
```yaml
preferences:
  timeout_seconds: 10  # 1-60 seconds
```

### CONFIG-006: Invalid Max Workers

**Error Message:**
```
ValueError: Invalid max_workers: X. Must be between 1 and 32
```

**Cause:**
- Worker count outside valid range (1-32)

**Resolution:**
```yaml
preferences:
  max_workers: 16  # 1-32 workers
```

### CONFIG-007: Invalid Cache TTL

**Error Message:**
```
ValueError: Invalid cache_ttl_seconds: X. Must be between 60 and 86400 (1 minute to 1 day)
```

**Cause:**
- Cache TTL outside valid range (60-86400 seconds)

**Resolution:**
```yaml
preferences:
  cache_ttl_seconds: 3600  # 1 hour (60-86400 seconds)
```

### CONFIG-008: Config File Not Found

**Error Message:**
```
ValueError: Could not load config from specified path: /path/to/config.yml
```

**Cause:**
- Custom config path specified but file doesn't exist or can't be read
- YAML parser not available (PyYAML not installed)

**Resolution:**
1. Verify file exists: `ls -l /path/to/config.yml`
2. Check file permissions: `chmod 644 config.yml`
3. Install PyYAML: `pip install pyyaml`
4. Validate YAML syntax: `yamllint config.yml`

---

## Installation Errors

### INSTALL-001: Installation Failed at Step

**Error Message:**
```
Installation failed at step: <description>
<error_details>
```

**Cause:**
- Command execution failed during installation
- Network issues, permission problems, or package manager errors

**Resolution:**
1. Check error details for specific cause
2. For network errors: retry or check connectivity
3. For permission errors: ensure sudo access or use user-level PM
4. For lock errors: wait and retry

**Retry Logic:**
- Network errors: Auto-retry with exponential backoff
- Lock contention: Auto-retry with exponential backoff
- Other errors: No auto-retry (manual intervention required)

### INSTALL-002: Post-Install Validation Failed

**Error Message:**
```
Post-install validation failed for <tool_name>
```

**Cause:**
- Tool installed but binary not found in PATH
- Binary exists but version check failed
- Tool name differs from package name

**Resolution:**
1. Check PATH: `echo $PATH`
2. Find binary manually: `find ~/.local ~/.cargo /usr/local -name '<tool>'`
3. Verify installation: `<tool> --version`
4. Update PATH if needed:
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   ```

### INSTALL-003: Command Timeout

**Error Message:**
```
Command timed out after Xs
```

**Cause:**
- Installation command exceeded configured timeout
- Slow network, large download, or unresponsive package manager

**Resolution:**
1. Increase timeout:
   ```yaml
   preferences:
     timeout_seconds: 30  # Increase from default 5s
   ```
2. Check network connectivity
3. Try different package manager

### INSTALL-004: Command Not Found

**Error Message:**
```
Command not found: <command>
```

**Cause:**
- Package manager binary not in PATH
- Package manager not installed

**Resolution:**
1. Install package manager:
   ```bash
   # For cargo
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

   # For pipx
   python3 -m pip install --user pipx
   python3 -m pipx ensurepath
   ```
2. Verify installation: `which <command>`
3. Update PATH if needed

### INSTALL-005: Installation Error (Generic)

**Error Message:**
```
Installation error: <details>
```

**Cause:**
- Unexpected exception during installation
- Python errors, file system issues, or system problems

**Resolution:**
1. Check error details for specific cause
2. Enable debug mode: `CLI_AUDIT_DEBUG=1`
3. Check system logs: `journalctl -xe`
4. Report issue if persistent

---

## Installation Error (InstallError)

### Custom Exception: InstallError

**Properties:**
- `message`: Human-readable error message
- `retryable`: Whether error can be retried
- `remediation`: Suggested fix

**Usage:**
```python
try:
    result = install_tool(...)
except InstallError as e:
    print(f"Error: {e.message}")
    if e.retryable:
        print("This error can be retried")
    if e.remediation:
        print(f"Suggested fix: {e.remediation}")
```

**Retryable Errors:**

Network-related:
- `connection refused`
- `connection timed out`
- `connection reset`
- `temporary failure`
- `network unreachable`
- `could not resolve host`

Lock contention:
- `could not get lock`
- `lock file exists`
- `waiting for cache lock`
- `dpkg frontend lock`

Exit codes:
- `75` (EAGAIN - temporary failure)
- `111` (connection refused)
- `128` (git error)

---

## Environment Detection Errors

### ENV-001: Invalid Environment Override

**Error Message:**
```
ValueError: Invalid environment override: X. Must be one of: auto, ci, server, workstation
```

**Cause:**
- Invalid override value passed to `detect_environment()`
- Valid values: `auto`, `ci`, `server`, `workstation`

**Resolution:**
```python
# ❌ Wrong
env = detect_environment(override="production")

# ✅ Correct
env = detect_environment(override="server")
```

### ENV-002: Low Confidence Detection

**Warning Message:**
```
Environment detected with low confidence: <confidence>%
```

**Cause:**
- Ambiguous environment indicators
- Missing expected environment variables or system signals

**Resolution:**
1. Use explicit override:
   ```python
   env = detect_environment(override="ci")
   ```
2. Or in config:
   ```yaml
   environment:
     mode: ci  # Explicit mode
   ```
3. Set environment-specific variables (CI, DISPLAY, etc.)

---

## Package Manager Errors

### PM-001: No Suitable Package Manager Found

**Error Message:**
```
ValueError: No suitable package manager found for <tool>. Please install a package manager for <language>.
```

**Cause:**
- No package manager available for tool's language/ecosystem
- Package managers not in PATH

**Resolution:**
1. Install recommended package manager:

   **Python:**
   ```bash
   pip install --user pipx
   python -m pipx ensurepath
   ```

   **Rust:**
   ```bash
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   ```

   **Node:**
   ```bash
   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
   ```

2. Configure package manager hierarchy:
   ```yaml
   preferences:
     package_managers:
       python: [uv, pipx, pip]
       rust: [cargo]
       node: [npm, pnpm, yarn]
   ```

### PM-002: Package Manager Not Found

**Error Message:**
```
ValueError: Package manager not found: <pm_name>
```

**Cause:**
- Specified package manager not registered in system
- Typo in package manager name

**Resolution:**
1. Check available PMs: See [PHASE2_API_REFERENCE.md](PHASE2_API_REFERENCE.md#package_managerspy)
2. Verify spelling: `cargo`, `pipx`, `npm`, etc.
3. Install missing PM (see PM-001)

---

## Validation Errors

### VALID-001: Binary Not Found in PATH

**Error Message:**
```
Binary not found in PATH: <tool_name>
```

**Cause:**
- Installation succeeded but binary not in PATH
- Tool installed to unexpected location
- PATH not updated after installation

**Resolution:**
1. Find binary:
   ```bash
   find ~ -name '<tool>' 2>/dev/null
   ```
2. Update PATH:
   ```bash
   # Add to ~/.bashrc or ~/.zshrc
   export PATH="$HOME/.local/bin:$PATH"
   export PATH="$HOME/.cargo/bin:$PATH"
   ```
3. Reload shell: `source ~/.bashrc`

### VALID-002: Version Detection Failed

**Warning Message:**
```
Could not determine version for <tool_name>
```

**Cause:**
- Tool doesn't support standard version flags
- Version output format not recognized

**Resolution:**
1. Check manually:
   ```bash
   <tool> --version
   <tool> -V
   <tool> version
   ```
2. Tool still functional despite version detection failure
3. Report issue if version should be detectable

### VALID-003: Version Mismatch

**Warning Message:**
```
Installed version <actual> differs from target <expected>
```

**Cause:**
- Package manager installed different version than requested
- Latest version changed between plan generation and execution

**Resolution:**
1. Check if acceptable: minor version differences usually OK
2. For exact version, specify in config:
   ```yaml
   tools:
     tool_name:
       version: "1.2.3"  # Exact version
   ```

---

## Network Errors

### NET-001: Connection Timeout

**Error Message:**
```
connection timed out
```

**Cause:**
- Network latency or package repository unresponsive
- Firewall blocking connections

**Resolution:**
1. Check network: `ping pypi.org`
2. Increase timeout:
   ```yaml
   preferences:
     timeout_seconds: 30
   ```
3. Configure proxy if needed:
   ```bash
   export HTTP_PROXY=http://proxy:8080
   export HTTPS_PROXY=http://proxy:8080
   ```

### NET-002: Connection Refused

**Error Message:**
```
connection refused
```

**Cause:**
- Package repository temporarily unavailable
- Port blocked by firewall
- Wrong repository URL

**Resolution:**
1. Wait and retry (auto-retry enabled)
2. Check repository status
3. Try alternative package manager

### NET-003: DNS Resolution Failed

**Error Message:**
```
could not resolve host
```

**Cause:**
- DNS server unreachable
- Domain name doesn't exist
- Network connectivity issue

**Resolution:**
1. Check DNS: `nslookup pypi.org`
2. Test connectivity: `ping 8.8.8.8`
3. Configure DNS:
   ```bash
   # Add to /etc/resolv.conf
   nameserver 8.8.8.8
   nameserver 1.1.1.1
   ```

---

## System Errors

### SYS-001: Permission Denied

**Error Message:**
```
Permission denied
```

**Cause:**
- Insufficient permissions for operation
- System-level package manager requires sudo
- Directory not writable

**Resolution:**
1. Use user-level package manager:
   ```yaml
   preferences:
     package_managers:
       python: [uv, pipx, pip]  # uv/pipx don't need sudo
   ```
2. Or use sudo:
   ```bash
   sudo python3 cli_audit.py
   ```
3. Fix directory permissions:
   ```bash
   chmod 755 ~/.local/bin
   ```

### SYS-002: Disk Space Exhausted

**Error Message:**
```
No space left on device
```

**Cause:**
- Insufficient disk space for installation
- Download cache full

**Resolution:**
1. Check space: `df -h`
2. Clean cache:
   ```bash
   # pip
   pip cache purge

   # cargo
   cargo clean

   # apt
   sudo apt clean
   ```
3. Free up space or expand disk

### SYS-003: File Not Found

**Error Message:**
```
FileNotFoundError: [Errno 2] No such file or directory
```

**Cause:**
- Required file or directory missing
- Incorrect path specified

**Resolution:**
1. Verify path exists
2. Create missing directories:
   ```bash
   mkdir -p ~/.config/cli-audit
   ```
3. Check file permissions

---

## Exit Codes

| Code | Meaning | Retryable | Action |
|------|---------|-----------|--------|
| `0` | Success | N/A | Continue |
| `1` | General error | No | Check error message |
| `2` | Misuse of command | No | Fix command syntax |
| `75` | Temporary failure | Yes | Auto-retry |
| `111` | Connection refused | Yes | Auto-retry |
| `126` | Command not executable | No | Check permissions |
| `127` | Command not found | No | Install package manager |
| `128` | Invalid exit argument | Yes | Auto-retry (git errors) |
| `130` | Terminated by Ctrl+C | No | User interrupted |
| `-1` | Timeout or system error | Sometimes | Check timeout settings |

---

## Troubleshooting

### General Debugging Steps

1. **Enable Debug Mode:**
   ```bash
   CLI_AUDIT_DEBUG=1 python3 cli_audit.py
   ```

2. **Enable Verbose Logging:**
   ```python
   result = install_tool(..., verbose=True)
   ```

3. **Check System Requirements:**
   ```bash
   python3 --version  # 3.9+
   which pip pipx cargo npm
   echo $PATH
   ```

4. **Validate Configuration:**
   ```python
   from cli_audit import load_config, validate_config

   config = load_config()
   warnings = validate_config(config)
   for warning in warnings:
       print(f"⚠️  {warning}")
   ```

### Common Resolution Patterns

**Network Issues:**
1. Increase timeout
2. Check connectivity
3. Configure proxy
4. Try offline mode: `CLI_AUDIT_OFFLINE=1`

**Permission Issues:**
1. Use user-level package managers (uv, pipx, cargo)
2. Fix directory permissions: `chmod 755`
3. Or use sudo (system PMs only)

**Package Manager Issues:**
1. Verify PM installed: `which <pm>`
2. Update PATH
3. Configure PM hierarchy in config
4. Try alternative PM

**Validation Issues:**
1. Check PATH
2. Verify binary exists: `which <tool>`
3. Test manually: `<tool> --version`
4. Update PATH and reload shell

### Getting Help

1. **Check Documentation:**
   - [CLI_REFERENCE.md](CLI_REFERENCE.md) - Command reference
   - [PHASE2_API_REFERENCE.md](PHASE2_API_REFERENCE.md) - API documentation
   - [TESTING.md](TESTING.md) - Testing and debugging

2. **Enable Tracing:**
   ```bash
   CLI_AUDIT_TRACE=1 CLI_AUDIT_TRACE_NET=1 python3 cli_audit.py 2> trace.log
   ```

3. **Report Issue:**
   Include:
   - Error message and stack trace
   - Operating system and version
   - Python version
   - Tool and package manager versions
   - Debug output

---

## Related Documentation

- **[CLI_REFERENCE.md](CLI_REFERENCE.md)** - Command-line reference
- **[PHASE2_API_REFERENCE.md](PHASE2_API_REFERENCE.md)** - API documentation
- **[TESTING.md](TESTING.md)** - Testing guide
- **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** - Development guide
- **[CONTRIBUTING.md](../CONTRIBUTING.md)** - Contributing guidelines

---

**Last Updated:** 2025-10-13
**Maintainers:** See [CONTRIBUTING.md](../CONTRIBUTING.md)
