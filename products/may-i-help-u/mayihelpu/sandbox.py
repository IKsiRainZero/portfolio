import re
from pathlib import Path

DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    (r"\brm\s+-rf\s+/", "rm -rf / (recursive delete root)"),
    (r"\brm\s+-r\s+/", "rm -r / (recursive delete root)"),
    (r"\brm\s+-rf\s+\S*\s+--no-preserve-root", "rm -rf --no-preserve-root"),
    (r"\bsudo\b", "sudo (privilege escalation)"),
    (r"\bsu\b", "su (switch user)"),
    (r"\bdoas\b", "doas (privilege escalation)"),
    (r"\bchmod\s+777\b", "chmod 777 (world-writable permission)"),
    (r"\bcurl\b.+\|.+\b(bash|sh|zsh|dash)\b", "curl piped to shell interpreter"),
    (r"\bwget\b.+-O\s*-\s*\|.+\b(bash|sh|zsh|dash)\b", "wget piped to shell interpreter"),
    (r">\s*/dev/(sd|hd|nvme|loop|mmcblk)", "redirect to block device"),
    (r"\bmkfs\.", "mkfs (filesystem format)"),
    (r"\bdd\s+if=", "dd (raw device copy)"),
    (r"\bfdisk\b", "fdisk (partition table manipulation)"),
    (r":\(\)\s*\{\s*:\|:&\s*\}\s*;\s*:", "fork bomb detected"),
    (r">\s*/etc/", "write to /etc/ system config"),
    (r">>\s*/etc/", "append to /etc/ system config"),
    (r">\s*/proc/", "write to /proc/"),
    (r">\s*/sys/", "write to /sys/"),
    (r">\s*/boot/", "write to /boot/"),
    (r"\bchown\s+\S+\s+/", "chown on system path"),
    (r"\bchattr\b", "chattr (immutable attribute change)"),
]


def validate_command(cmd: str) -> tuple[bool, str]:
    for pattern, description in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return False, description
    return True, ""


# File-system operations that WRITE/DELETE/EXECUTE (not read-only)
_DESTRUCTIVE_OPS = re.compile(
    r"\b(rm\b|mv\b|cp\b|chmod\b|chown\b|touch\b|dd\b|tee\b)"
    r"|>\s*\S|>>\s*\S"         # redirect (write/append)
    r"|\.\/\S+"                 # execute a local binary/script
)

# Extracts paths that look like absolute filesystem targets
_PATH_PATTERN = re.compile(r"(/[a-zA-Z0-9._\-][a-zA-Z0-9._\-/]*)")

_WINDOWS_DRIVE = re.compile(r"([A-Za-z]:\\(?:Users|Program|Windows|System)[a-zA-Z0-9._\-\\]*)")


def validate_paths(cmd: str, workspace: str) -> tuple[bool, list[str]]:
    ws = str(Path(workspace).resolve())
    is_destructive = bool(_DESTRUCTIVE_OPS.search(cmd))
    violations: list[str] = []

    _DEV_ALLOW = {"/dev/null", "/dev/random", "/dev/urandom",
                  "/dev/stdout", "/dev/stderr", "/dev/stdin", "/dev/zero"}

    for m in _PATH_PATTERN.finditer(cmd):
        p = m.group(1)
        # Check raw path for virtual device paths before filesystem resolution
        if p in _DEV_ALLOW:
            continue
        try:
            resolved = str(Path(p).resolve())
        except (OSError, ValueError):
            continue
        if resolved.startswith(ws):
            continue
        if resolved in _DEV_ALLOW:
            continue
        if not is_destructive:
            continue
        violations.append(p)

    for m in _WINDOWS_DRIVE.finditer(cmd):
        p = m.group(1)
        try:
            resolved = str(Path(p).resolve())
        except (OSError, ValueError):
            continue
        if resolved.startswith(ws):
            continue
        if is_destructive:
            violations.append(p)

    return len(violations) == 0, violations


def preview_command(cmd: str, workspace: str) -> str:
    ws_short = str(workspace)
    return f"[DRY RUN] cwd={ws_short}\n  $ {cmd}\n  (would execute, skipped)"


class Sandbox:
    def __init__(self, workspace: str, dry_run: bool = False):
        self.workspace = workspace
        self.dry_run = dry_run

    def check(self, command: str) -> tuple[bool, str]:
        ok, reason = validate_command(command)
        if not ok:
            return False, f"blocked: {reason}"
        ok, violations = validate_paths(command, self.workspace)
        if not ok:
            return False, f"path violations outside workspace: {', '.join(violations[:3])}"
        return True, ""

    def preview(self, command: str) -> str:
        return preview_command(command, self.workspace)
