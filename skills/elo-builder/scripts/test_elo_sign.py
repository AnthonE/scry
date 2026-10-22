"""Offline test for elo_sign.py — no network, a throwaway key.

Proves the signer signs a platform text and refuses everything that is not
one: the hive voice derivation text (its signature IS a secret key), an
EIP-4361 sign-in for any site, a lone one-line blob, and a text carrying a
character a reader cannot see. The rule is the broker's `sign_family` and
arca's `read_message`: two lines at least, the first `elo <family>` (or the
legacy `scry <family>`).

Run: python3 test_elo_sign.py  (needs eth_account; skipped honestly without).
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "elo_sign.py")
PASS = 0


def ok(cond, label):
    global PASS
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)
    PASS += 1
    print(f"  ok: {label}")


try:
    from eth_account import Account
    from eth_account.messages import encode_defunct
except ImportError:
    print("  skip: eth_account not installed (elo_sign needs it to sign at all)")
    print(f"\nall good — {PASS} checks passed")
    sys.exit(0)

KEY_HEX = "22" * 32
ADDR = Account.from_key("0x" + KEY_HEX).address.lower()

tmp = tempfile.mkdtemp(prefix="elo-sign-test-")
key_path = os.path.join(tmp, "agent.key")
with open(key_path, "w", encoding="ascii") as fh:
    fh.write(KEY_HEX + "\n")
os.chmod(key_path, 0o600)


def run(text):
    return subprocess.run([sys.executable, SCRIPT, "--key", key_path, "--text-file", "-"],
                          input=text, capture_output=True, text=True, timeout=60)


def refused(text, label):
    r = run(text)
    ok(r.returncode != 0 and "0x" not in r.stdout,
       f"refuses {label} (exit {r.returncode}, stdout {r.stdout.strip()[:20]!r})")
    ok(KEY_HEX not in r.stdout + r.stderr, f"the refusal of {label} never prints the key")


try:
    print("[signs a platform text]")
    play = (f"elo play\naction: submit\nwallet: {ADDR}\nday: 2026-10-22\n"
            f"detail: gates-pr 0123456789abcdef #0")
    r = run(play + "\n")
    sig = r.stdout.strip()
    ok(r.returncode == 0 and sig.startswith("0x") and len(sig) == 132,
       f"an `elo play` text is signed ({r.stderr.strip()[:80]})")
    ok(Account.recover_message(encode_defunct(text=play), signature=sig).lower() == ADDR,
       "the signature recovers the key's own wallet")
    ok("elo play" in r.stderr, "the first line is shown on stderr before signing")
    legacy = f"scry entitle\nwallet: {ADDR}\ntitle: gates"
    r = run(legacy)
    ok(r.returncode == 0 and r.stdout.strip().startswith("0x"),
       "a legacy `scry <family>` text is signed (an installed game may send one)")

    print("[refuses what is not one]")
    refused(f"scry hive voice v1\nwallet: {ADDR}\nthis signature IS my hive voice key.\n"
            "sign it only to derive your scry hive identity — never on any other site.",
            "the hive voice derivation text")
    refused(f"elopros.com wants you to sign in with your Ethereum account:\n{ADDR}\n\n"
            "Sign in\n\nURI: https://elopros.com\nVersion: 1\nChain ID: 4663\n"
            "Nonce: abcdef12\nIssued At: 2026-10-22T00:00:00Z",
            "an EIP-4361 sign-in")
    refused("0x" + "ab" * 32, "a single-line 32-byte blob")
    refused("elo play", "a lone first line with nothing under it")
    refused(f"elo Play!\nwallet: {ADDR}", "a family outside lowercase letters and dashes")
    refused(f"elo play\nwallet: {ADDR}‮\ndetail: x", "a bidi override")
    refused(f"elo play\nwallet: {ADDR}\x00hidden", "a NUL")
    refused("elo play\n" + "x" * 5000, "a text over 4096 bytes")
finally:
    os.unlink(key_path)
    os.rmdir(tmp)

print(f"\nall good — {PASS} checks passed")
