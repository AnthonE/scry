"""
workspace — a familiar's little sandbox, honestly scoped.

What this IS (safe, built, on by default):
  - a jailed working directory per familiar; file tools that cannot read
    or write outside it (path-escape is refused, not clamped);
  - an egress allowlist — the familiar may reach scry surfaces + an
    RH-Chain RPC and nothing else, matching FAMILIAR.md's hard boundary;
  - a constrained tool surface the autonomy loop plans over.

What a familiar's capability IS (operator call, 2026-07-19):
  - **MCP + a curated tool allowlist.** A familiar acts through the MCP
    servers scry has set up and a fixed set of vetted tools — plus the
    safe workspace file ops above. That is the whole surface. It is
    plenty: MCP already reaches real capability without ever handing an
    agent a shell.

What this is NOT, by design (not a "later gate" — a standing decision):
  - **arbitrary code execution.** We do not run other people's code.
    A cwd + rlimits is a belt, not a jail, and hosting untrusted code on
    a shared VM is a risk class we are choosing not to take. `run()`
    therefore refuses. The `sandbox_backend` seam is kept ONLY as an
    escape hatch a self-hoster could wire on their own box under their
    own risk — the hosted product never wires it. Capability comes from
    MCP + tools, not from a shell.
"""
import os
from pathlib import Path

# The only hosts a familiar may reach at launch (FAMILIAR.md egress boundary).
DEFAULT_EGRESS = ("scry.moreright.xyz",)


class WorkspaceError(Exception):
    pass


class Egress:
    """A hostname allowlist. Default-closed: anything not listed is denied."""

    def __init__(self, hosts=DEFAULT_EGRESS, rpc_hosts=()):
        self.hosts = set(hosts) | set(rpc_hosts)

    def allow(self, host: str):
        self.hosts.add(host)

    def allowed(self, url_or_host: str) -> bool:
        host = url_or_host
        if "://" in host:
            host = host.split("://", 1)[1]
        host = host.split("/", 1)[0].split(":", 1)[0]
        return host in self.hosts


class Workspace:
    """A familiar's jailed directory + the safe tool surface over it."""

    def __init__(self, root: Path, egress: Egress = None,
                 sandbox_backend=None, max_bytes: int = 256 * 1024):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.egress = egress or Egress()
        self.sandbox_backend = sandbox_backend      # None => run() refuses
        self.max_bytes = max_bytes

    # ── path confinement ─────────────────────────────────────────────────
    def _resolve(self, rel: str) -> Path:
        if os.path.isabs(rel):
            raise WorkspaceError(f"absolute paths refused: {rel!r}")
        p = (self.root / rel).resolve()
        if p != self.root and not p.is_relative_to(self.root):
            raise WorkspaceError(f"path escapes the workspace: {rel!r}")
        return p

    # ── safe file tools (always available) ───────────────────────────────
    def write(self, rel: str, content: str) -> dict:
        data = str(content).encode()
        if len(data) > self.max_bytes:
            raise WorkspaceError(f"write exceeds {self.max_bytes} bytes")
        p = self._resolve(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return {"wrote": rel, "bytes": len(data)}

    def read(self, rel: str) -> str:
        p = self._resolve(rel)
        if not p.is_file():
            raise WorkspaceError(f"no such file: {rel!r}")
        return p.read_text()

    def list(self) -> list:
        return sorted(str(p.relative_to(self.root))
                      for p in self.root.rglob("*") if p.is_file())

    # ── the gated exec seam ──────────────────────────────────────────────
    def run(self, argv, timeout: int = 20) -> dict:
        """Refused by design. The hosted product does not run agent code —
        capability is MCP + curated tools, never a shell (see module docstring).

        The `sandbox_backend` hook exists ONLY so a self-hoster can wire their
        own isolation on their own box at their own risk; the hosted keep
        never sets it."""
        if self.sandbox_backend is None:
            raise WorkspaceError(
                "code execution is off by design: familiars act through MCP + a "
                "curated tool allowlist, not a shell. A cwd + rlimits is not a "
                "security boundary and we do not host untrusted code.")
        return self.sandbox_backend(list(argv), str(self.root), timeout)


def rlimit_preexec(cpu_seconds: int = 10, address_space_mb: int = 512):
    """A preexec_fn a real backend can pass to subprocess as a BELT (not the
    boundary). Kept here so the eventual sandbox backend has it ready."""
    def _apply():
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        b = address_space_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (b, b))
        resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
    return _apply
