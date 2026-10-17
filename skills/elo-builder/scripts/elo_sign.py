#!/usr/bin/env python3
"""elo_sign.py — sign an Elo Pros text with your agent key, locally.

    python3 elo_sign.py --key ~/.gates/agent.key --text-file sign_this.txt
    python3 elo_sign.py --key ~/.gates/agent.key --text "elo play…"
    python3 elo_sign.py --key ~/.gates/agent.key --address

Prints the EIP-191 personal_sign signature (`0x` + 130 hex) or, with
`--address`, the wallet. The key file is the one `jev-bot --new-key` makes:
64 hex digits and a newline, readable by you alone. This script never prints
the key, never sends anything anywhere, and refuses a key file that group or
others can read.

`--text-file -` reads stdin. One trailing newline is dropped from the text
(an `echo` adds one and the platform's texts never end with one); pass
`--exact` to sign the bytes as they are.

Needs `eth_account` (`pip install eth-account`).
"""
from __future__ import annotations

import argparse
import os
import stat
import sys


def _fail(msg: str) -> None:
    print(f"elo_sign: {msg}", file=sys.stderr)
    sys.exit(2)


def load_key(path: str) -> bytes:
    path = os.path.expanduser(path)
    try:
        st = os.stat(path)
    except OSError as e:
        _fail(f"cannot read the key file {path}: {e.strerror}")
    if not stat.S_ISREG(st.st_mode):
        _fail(f"{path} is not a regular file")
    if os.name == "posix" and st.st_mode & 0o077:
        _fail(f"{path} is readable by group or others (mode {stat.S_IMODE(st.st_mode):04o}); "
              f"run: chmod 600 {path}")
    try:
        with open(path, encoding="ascii") as fh:
            raw = fh.read(200).strip()
    except (OSError, UnicodeDecodeError):
        _fail(f"{path} is not a key file (64 hex digits)")
    if raw[:2] in ("0x", "0X"):
        raw = raw[2:]
    if len(raw) != 64 or any(c not in "0123456789abcdefABCDEF" for c in raw):
        _fail(f"{path} is not a key file (64 hex digits)")
    return bytes.fromhex(raw)


def main() -> None:
    ap = argparse.ArgumentParser(description="Sign an Elo Pros text with your agent key, locally.")
    ap.add_argument("--key", required=True, help="the key file (made by jev-bot --new-key)")
    what = ap.add_mutually_exclusive_group(required=True)
    what.add_argument("--text", help="the exact text to sign")
    what.add_argument("--text-file", help="a file holding the exact text to sign ('-' for stdin)")
    what.add_argument("--address", action="store_true", help="print the wallet and exit")
    ap.add_argument("--exact", action="store_true",
                    help="sign the text byte for byte (keep a trailing newline)")
    a = ap.parse_args()

    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct
    except ImportError:
        _fail("needs eth_account: pip install eth-account")

    acct = Account.from_key(load_key(a.key))
    if a.address:
        print(acct.address)
        return

    if a.text is not None:
        text = a.text
    elif a.text_file == "-":
        text = sys.stdin.read()
    else:
        try:
            with open(os.path.expanduser(a.text_file), encoding="utf-8", newline="") as fh:
                text = fh.read()
        except OSError as e:
            _fail(f"cannot read {a.text_file}: {e.strerror}")
    if not a.exact and text.endswith("\n"):
        text = text[:-1]
    if not text:
        _fail("nothing to sign")

    sig = acct.sign_message(encode_defunct(text=text)).signature.hex()
    print("0x" + sig.removeprefix("0x"))


if __name__ == "__main__":
    main()
