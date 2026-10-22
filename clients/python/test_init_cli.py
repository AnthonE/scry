"""Offline test for scry-init's key file (scry_client.init_cli).

The generated wallet key must never exist on disk readable by anyone but its
owner — not even for the instant between a write and a chmod, because a reader
that opened the file in that instant keeps reading after the chmod.
Run: python3 test_init_cli.py"""
import os
import stat
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = 0


def ok(cond, label):
    global PASS
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)
    PASS += 1
    print(f"  ok: {label}")


home = Path(tempfile.mkdtemp()) / "scry-home"
os.environ["SCRY_HOME"] = str(home)
os.environ.pop("SCRY_KEY", None)
from scry_client import init_cli  # noqa: E402

# Record the file's mode at every moment key bytes reach it, however it is
# written (Path.write_text, or os.write on a raw fd).
seen = []
_write_text, _os_write = Path.write_text, os.write


def _spy_write_text(self, data, *a, **k):
    n = _write_text(self, data, *a, **k)
    if self.name == "key":
        seen.append(stat.S_IMODE(os.stat(self).st_mode))
    return n


def _spy_os_write(fd, data):
    n = _os_write(fd, data)
    seen.append(stat.S_IMODE(os.fstat(fd).st_mode))
    return n


print("[scry-init: the generated key is owner-only from its first byte]")
old_umask = os.umask(0o022)
Path.write_text, os.write = _spy_write_text, _spy_os_write
try:
    key = init_cli._load_or_create_key()
finally:
    Path.write_text, os.write = _write_text, _os_write
    os.umask(old_umask)

kp = home / "key"
ok(key.startswith("0x") and len(key) == 66, "a key is generated")
ok(kp.read_text().strip() == key, "the key on disk is the key returned")
ok(seen and all(m & 0o077 == 0 for m in seen),
   f"the key file is never group/other-readable while written (modes {[oct(m) for m in seen]})")
ok(stat.S_IMODE(kp.stat().st_mode) == 0o600, "the key file ends 0600")
ok(stat.S_IMODE(home.stat().st_mode) & 0o077 == 0, "~/.scry is created owner-only")
ok(init_cli._load_or_create_key() == key, "a second run loads the same key")

print(f"\nALL {PASS} CHECKS PASS")
