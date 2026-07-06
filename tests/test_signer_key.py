"""The signer must resolve a key to a real file path regardless of how a host
supplies it — a misplaced base64 value should still work, not fail casper-client
with 'file name too long' (regression for the live EXECUTION_FAILED)."""
import base64
import os

import pytest

from agent.cspr_click import _resolve_secret_key

# Synthetic, non-real key material. Header built by concatenation so it is not a
# literal private-key block (and never matches any real key).
_HDR = "-----BEGIN " + "EC PRIVATE KEY" + "-----"
_FTR = "-----END " + "EC PRIVATE KEY" + "-----"
PEM = (_HDR + "\nDUMMYtestKEYnotREAL00000000000000000000000000==\n" + _FTR + "\n").encode()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("CASPER_SECRET_KEY_B64", raising=False)


def _reads_back(path: str) -> bool:
    # compare on stripped bytes: the resolver trims surrounding whitespace, which
    # is fine for casper-client (a trailing newline is not significant)
    return os.path.isfile(path) and open(path, "rb").read().strip() == PEM.strip()


def test_base64_pasted_into_secret_key():
    # The exact misconfiguration seen live: base64 in CASPER_SECRET_KEY.
    assert _reads_back(_resolve_secret_key(base64.b64encode(PEM).decode()))


def test_base64_in_dedicated_var(monkeypatch):
    monkeypatch.setenv("CASPER_SECRET_KEY_B64", base64.b64encode(PEM).decode())
    assert _reads_back(_resolve_secret_key(""))


def test_raw_pem_pasted_into_secret_key():
    assert _reads_back(_resolve_secret_key(PEM.decode()))


def test_real_file_path_used_as_is(tmp_path):
    p = tmp_path / "key.pem"
    p.write_bytes(PEM)
    assert _resolve_secret_key(str(p)) == str(p)


def test_redact_secrets_strips_key_material_keeps_hashes():
    from agent.cspr_click import redact_secrets
    b64 = base64.b64encode(PEM).decode()
    out = redact_secrets(f"could not read '{b64}': File name too long")
    assert b64 not in out and "[redacted]" in out
    assert redact_secrets("-----BEGIN X-----\nabc\n-----END X-----") == "[redacted-key]"
    tx = "reallocated; tx " + "a1" * 32  # 64-char hash must survive
    assert redact_secrets(tx) == tx
