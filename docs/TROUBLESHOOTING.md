# Troubleshooting Guide

## Overview

This guide helps diagnose and resolve common issues with AI CLI Preparation, including network timeouts, rate limiting, version detection failures, classification errors, and performance problems.

## Quick Diagnostics

### Enable Debug Mode

```bash
CLI_AUDIT_DEBUG=1 python3 cli_audit.py --only problematic-tool
```

**Shows:**
- Suppressed exceptions
- Cache operations
- Classification decisions
- Best-effort fallbacks

### Enable Trace Mode

```bash
CLI_AUDIT_TRACE=1 python3 cli_audit.py --only problematic-tool
```

**Shows:**
- Detailed execution flow
- Function entry/exit
- Timing breakdowns
- Slow operation warnings

### Network Trace

```bash
CLI_AUDIT_TRACE_NET=1 python3 cli_audit.py --only problematic-tool
```

**Shows:**
- HTTP request URLs
- Response codes
- Retry attempts
- Error details

### Combined Diagnostics

```bash
CLI_AUDIT_DEBUG=1 CLI_AUDIT_TRACE=1 CLI_AUDIT_TRACE_NET=1 python3 cli_audit.py --only tool 2>&1 | tee debug.log
```

## Common Issues

### 1. Network Timeouts

**Symptoms:**
- Empty `latest_upstream` column
- Slow audit execution (>30s for 50 tools)
- Timeout messages in debug output

**Causes:**
- Slow network connection
- Upstream API latency
- DNS resolution issues
- Firewall blocking requests

**Diagnosis:**
```bash
# Test network reachability
curl -I https://api.github.com
curl -I https://registry.npmjs.org
curl -I https://pypi.org

# Check DNS resolution
dig api.github.com
dig registry.npmjs.org

# Test with network trace
CLI_AUDIT_TRACE_NET=1 python3 cli_audit.py --only ripgrep
```

**Solutions:**

**Increase Timeout:**
```bash
CLI_AUDIT_TIMEOUT_SECONDS=10 python3 cli_audit.py
```

**Increase Retries:**
```bash
CLI_AUDIT_HTTP_RETRIES=5 CLI_AUDIT_BACKOFF_BASE=0.5 python3 cli_audit.py
```

**Use Offline Mode:**
```bash
CLI_AUDIT_OFFLINE=1 python3 cli_audit.py
```

**Use Manual-First Mode:**
```bash
CLI_AUDIT_MANUAL_FIRST=1 python3 cli_audit.py
```

**Configure Proxy (if needed):**
```bash
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
python3 cli_audit.py
```

### 2. GitHub Rate Limiting

**Symptoms:**
- Empty upstream versions for GitHub tools
- HTTP 403 errors in trace output
- Message: "API rate limit exceeded"

**Causes:**
- Unauthenticated requests: 60/hour limit
- Authenticated requests: 5000/hour limit
- Too many concurrent workers

**Diagnosis:**
```bash
# Check current rate limit status
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/rate_limit

# Test with trace
CLI_AUDIT_TRACE_NET=1 python3 cli_audit.py --only ripgrep 2>&1 | grep "403"
```

**Solutions:**

**Add GitHub Token:**
```bash
# Generate token at https://github.com/settings/tokens
export GITHUB_TOKEN=ghp_your_token_here
python3 cli_audit.py
```

**Reduce Concurrency:**
```bash
CLI_AUDIT_HOST_CAP_GITHUB_API=2 python3 cli_audit.py
```

**Use Hints Cache:**
```bash
# Hints automatically prioritize successful methods
# No action needed - just run again
python3 cli_audit.py
```

**Use Offline Mode:**
```bash
# When rate limited, fall back to manual cache
CLI_AUDIT_OFFLINE=1 python3 cli_audit.py
```

**Check Rate Limit in Script:**
```python
import os, json, urllib.request

token = os.environ.get("GITHUB_TOKEN", "")
headers = {"Authorization": f"Bearer {token}"} if token else {}
req = urllib.request.Request("https://api.github.com/rate_limit", headers=headers)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
print(f"Remaining: {data['rate']['remaining']}/{data['rate']['limit']}")
print(f"Reset: {data['rate']['reset']}")
```

### 3. Version Detection Failures

**Symptoms:**
- Tool shows as `NOT INSTALLED` but is on PATH
- Version column shows "X" or empty
- Classification shows as `unknown`

**Causes:**
- Tool uses non-standard version flag
- Version output filtered by error detection
- Tool binary not executable
- PATH issues

**Diagnosis:**
```bash
# Check if tool is on PATH
which ripgrep || which rg

# Test version flag manually
rg --version
rg -V
rg version

# Check permissions
ls -l $(which rg)

# Test with debug
CLI_AUDIT_DEBUG=1 python3 cli_audit.py --only ripgrep
```

**Solutions:**

**Add Custom Version Detection:**

Edit `cli_audit.py` function `get_version_line()`:

```python
# Around line 1037
def get_version_line(path: str, tool_name: str) -> str:
    # Add custom handling for your tool
    if tool_name == "your-tool":
        return run_with_timeout([path, "version"])  # Custom flag

    # Try common flags
    for flag in ["--version", "-V", "version", "-v"]:
        output = run_with_timeout([path, flag])
        if output and not is_error_output(output):
            return output

    return ""
```

**Add Hint for Version Flag:**

Edit `latest_versions.json`:

```json
{
  "__hints__": {
    "local_flag:your-tool": "version"
  }
}
```

**Fix PATH Issues:**
```bash
# Check PATH
echo $PATH | tr ':' '\n'

# Add missing directory
export PATH="$HOME/.local/bin:$PATH"

# Verify tool is found
which your-tool
```

**Fix Permissions:**
```bash
# Make tool executable
chmod +x ~/.local/bin/your-tool
```

### 4. Classification Errors

**Symptoms:**
- Wrong `installed_method` (e.g., `~/.local/bin` instead of `uv tool`)
- Inconsistent classifications for same tool
- Missing or generic classifications

**Causes:**
- Ambiguous installation paths
- Multiple installation methods present
- Shebang parsing failures
- Environment detection issues

**Diagnosis:**
```bash
# Check tool path and classification
CLI_AUDIT_JSON=1 python3 cli_audit.py --only ripgrep | jq '.[] | {tool, installed_method, installed_path_resolved, classification_reason}'

# Check shebang
head -1 $(which your-tool)

# Check symlink resolution
ls -l $(which your-tool)
readlink -f $(which your-tool)

# Check environment hints
env | grep -E "(UV_|VIRTUAL_ENV|CONDA|NVM_)"
```

**Solutions:**

**Refine Classification Rules:**

Edit `cli_audit.py` function `_classify_install_method()`:

```python
# Around line 900
def _classify_install_method(path: str, tool_name: str) -> tuple[str, str]:
    # Add more specific path patterns
    if "/.mymanager/bin/" in path:
        return "mymanager", "path-under-~/.mymanager/bin"

    # Read shebang for ~/.local/bin disambiguation
    if "/.local/bin/" in path:
        shebang = _read_first_line(path)
        if "uv" in shebang:
            return "uv tool", "shebang-contains-uv"
        if "pipx" in shebang:
            return "pipx/user", "shebang-contains-pipx"

    # ... existing logic
```

**Set Classification Hints:**

Edit `latest_versions.json`:

```json
{
  "__methods__": {
    "your-tool": "uv tool"
  }
}
```

**Resolve Path Ambiguity:**
```bash
# Check for multiple installations
which -a ripgrep
which -a rg

# Prioritize by PATH order
export PATH="$HOME/.local/bin:/usr/bin"
```

### 5. HTTP Retry Failures

**Symptoms:**
- Persistent empty upstream versions
- Network trace shows all retries failing
- Specific hosts always fail

**Causes:**
- SSL/TLS certificate issues
- Proxy interference
- Host-specific blocking
- Outdated Python urllib

**Diagnosis:**
```bash
# Test with curl
curl -v https://api.github.com/repos/BurntSushi/ripgrep/releases/latest

# Check Python SSL
python3 -c "import ssl; print(ssl.OPENSSL_VERSION)"

# Test with network trace
CLI_AUDIT_TRACE_NET=1 python3 cli_audit.py --only ripgrep 2>&1 | grep -A5 "http_exc"
```

**Solutions:**

**Update SSL Certificates:**
```bash
# Debian/Ubuntu
sudo apt-get update
sudo apt-get install --reinstall ca-certificates

# macOS
brew upgrade openssl@3
```

**Configure Proxy:**
```bash
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
export NO_PROXY=localhost,127.0.0.1
```

**Increase Retry Attempts:**
```bash
CLI_AUDIT_HTTP_RETRIES=10 CLI_AUDIT_BACKOFF_BASE=1.0 python3 cli_audit.py
```

**Use Alternative Host (if available):**

Edit `cli_audit.py` function `latest_github()`:

```python
# Use Atom feed instead of API
def latest_github(owner: str, repo: str) -> tuple[str, str]:
    # Try feed first
    feed_url = f"https://github.com/{owner}/{repo}/releases.atom"
    # ... existing logic
```

### 6. Cache Corruption

**Symptoms:**
- JSON parsing errors
- Missing cache entries after update
- Inconsistent behavior between runs
- Snapshot fails to load

**Causes:**
- Interrupted write operations
- Concurrent modifications
- Disk space issues
- File permission problems

**Diagnosis:**
```bash
# Validate JSON files
jq '.' latest_versions.json
jq '.' tools_snapshot.json

# Check file permissions
ls -l latest_versions.json tools_snapshot.json

# Check disk space
df -h .

# Look for temp files
ls -la .tmp_*
```

**Solutions:**

**Recover from Backup:**
```bash
# Restore from git
git checkout latest_versions.json tools_snapshot.json

# Rebuild snapshot
make update
```

**Fix Permissions:**
```bash
chmod 644 latest_versions.json tools_snapshot.json
```

**Clean Temp Files:**
```bash
rm -f .tmp_*.json
```

**Prevent Corruption:**
```bash
# Atomic writes are built-in, but ensure:
# 1. Sufficient disk space (check with df -h)
# 2. Write permissions (check with ls -l)
# 3. No concurrent processes writing same files
```

**Manual Cache Repair:**
```bash
# Validate and pretty-print
jq '.' latest_versions.json > latest_versions.json.tmp
mv latest_versions.json.tmp latest_versions.json

# Rebuild hints
jq 'del(.__hints__)' latest_versions.json > latest_versions.json.tmp
mv latest_versions.json.tmp latest_versions.json
make update  # Rebuilds hints
```

### 7. Version Parsing Edge Cases

**Symptoms:**
- Status shows `UNKNOWN` despite valid versions
- Version comparison incorrect
- Semantic versioning failures

**Causes:**
- Non-standard version formats
- Prefixed versions (e.g., `jq-1.8.1`)
- Date-based versions (e.g., `20250822`)
- Pre-release tags (e.g., `1.0.0-beta`)

**Diagnosis:**
```bash
# Check raw version strings
CLI_AUDIT_JSON=1 python3 cli_audit.py --only jq | jq '.[] | {tool, installed, latest_upstream, installed_version, latest_version}'

# Test version parsing
python3 -c "
import re
version = 'jq-1.8.1'
match = re.search(r'(\d+\.\d+\.\d+)', version)
print(match.group(1) if match else 'FAIL')
"
```

**Solutions:**

**Enhance Version Extraction:**

Edit `cli_audit.py` function `extract_version_number()`:

```python
# Around line 1100
def extract_version_number(s: str) -> str:
    # Add custom patterns

    # Handle prefix formats (e.g., jq-1.8.1)
    match = re.search(r'[a-z]+-(\d+\.\d+\.\d+)', s)
    if match:
        return match.group(1)

    # Handle go versions (e.g., go1.25.1)
    match = re.search(r'go(\d+\.\d+\.\d+)', s)
    if match:
        return match.group(1)

    # ... existing logic
```

**Manual Version Normalization:**

Edit `latest_versions.json`:

```json
{
  "jq": "1.8.1",
  "parallel": "20250822"
}
```

**Add Comparison Override:**

Edit `cli_audit.py` function `audit_tool()`:

```python
# Special case for date-based versions
if tool.name == "parallel":
    # Compare as integers
    installed_int = int(installed_version) if installed_version.isdigit() else 0
    latest_int = int(latest_version) if latest_version.isdigit() else 0
    status = "UP-TO-DATE" if installed_int >= latest_int else "OUTDATED"
```

### 8. Performance Issues

**Symptoms:**
- Audit takes >30s for 50 tools
- High CPU usage
- Memory growth over time
- Slow rendering

**Causes:**
- Too many workers (contention)
- Slow upstream APIs
- Large number of tools
- Inefficient subprocess calls

**Diagnosis:**
```bash
# Profile execution
time make update

# Identify slow tools
CLI_AUDIT_TRACE=1 CLI_AUDIT_SLOW_MS=1000 make update 2>&1 | grep "slow"

# Monitor resources
top -p $(pgrep -f cli_audit.py)

# Test render performance
time make audit
```

**Solutions:**

**Optimize Worker Count:**
```bash
# Too many workers cause contention
CLI_AUDIT_MAX_WORKERS=12 make update

# Find optimal value for your system
for workers in 4 8 12 16 20 24; do
  echo "Testing $workers workers:"
  time CLI_AUDIT_MAX_WORKERS=$workers make update
done
```

**Reduce Timeout:**
```bash
# Fail fast on slow tools
CLI_AUDIT_TIMEOUT_SECONDS=2 make update
```

**Use Fast Mode:**
```bash
CLI_AUDIT_FAST=1 make update
```

**Enable Manual-First:**
```bash
CLI_AUDIT_MANUAL_FIRST=1 make update
```

**Limit Host Concurrency:**
```bash
CLI_AUDIT_HOST_CAP_GITHUB_API=2 CLI_AUDIT_HOST_CAP_NPM=2 make update
```

**Use Snapshot Rendering:**
```bash
# Collect once
make update

# Render many times (fast)
make audit
make audit
make audit
```

### 9. Docker Detection Issues

**Symptoms:**
- Docker version shows as "X" or empty
- Slow docker inspection
- Docker info missing

**Causes:**
- Docker daemon not running
- Permission issues (not in docker group)
- Docker info inspection enabled but slow

**Diagnosis:**
```bash
# Check docker status
docker version
docker ps

# Check permissions
groups | grep docker

# Test with docker info disabled
CLI_AUDIT_DOCKER_INFO=0 python3 cli_audit.py --only docker
```

**Solutions:**

**Fix Permissions:**
```bash
# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker ps
```

**Disable Docker Info:**
```bash
CLI_AUDIT_DOCKER_INFO=0 make update
```

**Start Docker Daemon:**
```bash
# systemd
sudo systemctl start docker

# Docker Desktop
# Start from GUI
```

### 10. Environment Variable Conflicts

**Symptoms:**
- Unexpected behavior
- Settings not applying
- Conflicting modes

**Causes:**
- Multiple .env files
- Shell environment overrides
- Typos in variable names

**Diagnosis:**
```bash
# Check all CLI_AUDIT_* variables
env | grep CLI_AUDIT

# Check for .env files
ls -a .env*

# Check shell config
grep CLI_AUDIT ~/.bashrc ~/.zshrc
```

**Solutions:**

**Clear Environment:**
```bash
# Unset all CLI_AUDIT variables
unset $(env | grep '^CLI_AUDIT_' | cut -d= -f1)

# Verify clean state
env | grep CLI_AUDIT
```

**Source Correct .env:**
```bash
# Load specific profile
set -a
source .env.production
set +a

# Verify
env | grep CLI_AUDIT
```

**Debug Variable Precedence:**
```bash
# Print all settings at startup
CLI_AUDIT_DEBUG=1 python3 cli_audit.py --only python 2>&1 | head -20
```

## Debugging Workflows

### Workflow 1: Diagnose Single Tool

```bash
# 1. Test tool manually
which ripgrep
ripgrep --version

# 2. Run audit with full debugging
CLI_AUDIT_DEBUG=1 \
CLI_AUDIT_TRACE=1 \
CLI_AUDIT_TRACE_NET=1 \
python3 cli_audit.py --only ripgrep 2>&1 | tee ripgrep_debug.log

# 3. Check classification
CLI_AUDIT_JSON=1 python3 cli_audit.py --only ripgrep | jq '.[] | {installed_method, classification_reason, installed_path_resolved}'

# 4. Test upstream lookup
python3 -c "
from cli_audit import latest_github
tag, method = latest_github('BurntSushi', 'ripgrep')
print(f'Tag: {tag}, Method: {method}')
"
```

### Workflow 2: Diagnose Network Issues

```bash
# 1. Test network reachability
for host in api.github.com registry.npmjs.org pypi.org crates.io; do
  echo "Testing $host:"
  curl -I https://$host
done

# 2. Test with retries
CLI_AUDIT_TRACE_NET=1 \
CLI_AUDIT_HTTP_RETRIES=5 \
python3 cli_audit.py --only ripgrep 2>&1 | grep -E "(http_|retry)"

# 3. Test offline fallback
CLI_AUDIT_OFFLINE=1 python3 cli_audit.py --only ripgrep

# 4. Check cache state
jq '.ripgrep' latest_versions.json
jq '.__hints__["gh:BurntSushi/ripgrep"]' latest_versions.json
```

### Workflow 3: Diagnose Performance

```bash
# 1. Baseline timing
time CLI_AUDIT_COLLECT=1 python3 cli_audit.py

# 2. Identify slow tools
CLI_AUDIT_TRACE=1 CLI_AUDIT_SLOW_MS=1000 make update 2>&1 | grep "slow"

# 3. Test different worker counts
for workers in 8 12 16 20; do
  echo "Testing $workers workers:"
  time CLI_AUDIT_MAX_WORKERS=$workers make update
done

# 4. Test with optimizations
time CLI_AUDIT_FAST=1 \
CLI_AUDIT_MANUAL_FIRST=1 \
CLI_AUDIT_TIMEOUT_SECONDS=2 \
make update
```

### Workflow 4: Diagnose Cache Issues

```bash
# 1. Validate JSON
jq '.' latest_versions.json
jq '.' tools_snapshot.json

# 2. Check metadata
jq '.__meta__' tools_snapshot.json
jq '.__hints__ | length' latest_versions.json

# 3. Rebuild cache
rm -f latest_versions.json tools_snapshot.json
git checkout latest_versions.json
make update

# 4. Verify consistency
CLI_AUDIT_OFFLINE=1 make audit
```

## Advanced Debugging

### Python Debugger (pdb)

```python
# Add breakpoint in cli_audit.py
def audit_tool(tool: Tool) -> tuple:
    import pdb; pdb.set_trace()  # Breakpoint
    # ... rest of function
```

```bash
python3 cli_audit.py --only ripgrep
# (Pdb) commands available:
# n - next line
# s - step into
# c - continue
# p variable - print variable
# l - list code
```

### Logging to File

```bash
# Capture all output
make update 2>&1 | tee update.log

# Filter for errors
make update 2>&1 | grep -i "error\|exception\|fail" | tee errors.log

# Extract timing info
CLI_AUDIT_TRACE=1 make update 2>&1 | grep "slow\|ms)" | tee timing.log
```

### Interactive Python Testing

```python
# Launch Python REPL
python3

# Import and test functions
from cli_audit import *

# Test version extraction
extract_version_number("ripgrep 14.1.1 (rev abc123)")

# Test tool audit
tool = Tool("ripgrep", ("rg",), "gh", ("BurntSushi", "ripgrep"))
result = audit_tool(tool)
print(result)

# Test classification
detect_install_method("/home/user/.cargo/bin/rg", "ripgrep")

# Test upstream lookup
latest_github("BurntSushi", "ripgrep")
```

## Environment Variable Reference

### Debugging Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `CLI_AUDIT_DEBUG` | Print debug messages | `CLI_AUDIT_DEBUG=1` |
| `CLI_AUDIT_TRACE` | Detailed execution trace | `CLI_AUDIT_TRACE=1` |
| `CLI_AUDIT_TRACE_NET` | Network call tracing | `CLI_AUDIT_TRACE_NET=1` |
| `CLI_AUDIT_PROGRESS` | Show progress updates | `CLI_AUDIT_PROGRESS=1` |
| `CLI_AUDIT_SLOW_MS` | Slow operation threshold | `CLI_AUDIT_SLOW_MS=1000` |

### Performance Variables

| Variable | Purpose | Default | Range |
|----------|---------|---------|-------|
| `CLI_AUDIT_MAX_WORKERS` | Thread pool size | 16 | 1-32 |
| `CLI_AUDIT_TIMEOUT_SECONDS` | Operation timeout | 3 | 1-30 |
| `CLI_AUDIT_HTTP_RETRIES` | Retry attempts | 2 | 0-5 |
| `CLI_AUDIT_BACKOFF_BASE` | Retry backoff base | 0.2 | 0.1-2.0 |
| `CLI_AUDIT_FAST` | Skip slow operations | 0 | 0-1 |

### Network Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `CLI_AUDIT_OFFLINE` | Force offline mode | 0 |
| `CLI_AUDIT_MANUAL_FIRST` | Try cache first | 0 |
| `GITHUB_TOKEN` | GitHub API token | "" |
| `HTTP_PROXY` | HTTP proxy URL | "" |
| `HTTPS_PROXY` | HTTPS proxy URL | "" |

### Host Concurrency Caps

| Variable | Purpose | Default |
|----------|---------|---------|
| `CLI_AUDIT_HOST_CAP_GITHUB` | github.com cap | 4 |
| `CLI_AUDIT_HOST_CAP_GITHUB_API` | api.github.com cap | 4 |
| `CLI_AUDIT_HOST_CAP_NPM` | registry.npmjs.org cap | 4 |
| `CLI_AUDIT_HOST_CAP_CRATES` | crates.io cap | 4 |
| `CLI_AUDIT_HOST_CAP_GNU` | GNU FTP cap | 2 |

## Getting Help

### Documentation Resources

- **[API_REFERENCE.md](API_REFERENCE.md)** - Function signatures and parameters
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design and data flow
- **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** - Contributing and development
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Operations and configuration
- **[TOOL_ECOSYSTEM.md](TOOL_ECOSYSTEM.md)** - Tool catalog

### Support Channels

- **GitHub Issues:** Report bugs and request features
- **GitHub Discussions:** Ask questions and share solutions
- **Pull Requests:** Contribute fixes and improvements

### Reporting Bugs

When reporting issues, include:

1. **Environment:**
```bash
python3 --version
uname -a
env | grep CLI_AUDIT
```

2. **Command:**
```bash
# Exact command that failed
CLI_AUDIT_DEBUG=1 python3 cli_audit.py --only tool
```

3. **Output:**
```bash
# Full debug output
CLI_AUDIT_DEBUG=1 CLI_AUDIT_TRACE=1 python3 cli_audit.py --only tool 2>&1 | tee debug.log
```

4. **Cache State:**
```bash
jq '.__meta__' tools_snapshot.json
jq '.tool' latest_versions.json
jq '.__hints__' latest_versions.json
```

5. **Expected vs Actual Behavior:**
- What you expected to happen
- What actually happened
- Steps to reproduce

## See Also

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Configuration and CI/CD integration
- **[API_REFERENCE.md](API_REFERENCE.md)** - Environment variables reference
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Resilience patterns and error handling
