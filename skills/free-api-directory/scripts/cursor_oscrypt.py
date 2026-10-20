#!/usr/bin/env python3
"""
cursor_oscrypt.py — Chromium OSCrypt (v10) 加解密工具，專為 Cursor/VSCode secret 存取。

Cursor 用 Electron safeStorage，底層係 Chromium OSCrypt v10：
    blob = "v10" + nonce(12) + AES-256-GCM(ciphertext + tag(16))
master key 由 DPAPI 保護，存在 <UserData>/Local State 的 os_crypt.encrypted_key。

本模組提供：
    decrypt_secret(blob, master_key) -> bytes
    encrypt_secret(plaintext, master_key) -> bytes   # 回傳 "v10"+... 完整 blob

⚠️ 安全原則：
    - 唔會印出完整明文 key，只報長度 + 首 6 字符
    - 唔會寫任何檔案（除 caller 指定）
    - 讀取 master key 唔會修改 Local State
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _HAVE_AESGCM = True
except ImportError:  # pragma: no cover
    _HAVE_AESGCM = False


def load_master_key(local_state: str | os.PathLike) -> bytes:
    """由 Local State 嘅 os_crypt.encrypted_key 解出 master key。"""
    import win32crypt

    data = json.loads(Path(local_state).read_text(encoding="utf-8"))
    enc_key = data["os_crypt"]["encrypted_key"]
    blob = base64.b64decode(enc_key)
    # 前 5 bytes = "DPAPI" 標記
    if blob[:5] != b"DPAPI":
        raise ValueError(f"encrypted_key 唔係 DPAPI 格式: {blob[:5]!r}")
    mk = win32crypt.CryptUnprotectData(blob[5:], None, None, None, 0)
    # pywin32 有時回傳 (description, data) tuple，有時直接回 bytes
    if isinstance(mk, tuple):
        mk = mk[1]
    return mk


def _aesgcm():
    if not _HAVE_AESGCM:
        raise RuntimeError("缺少 cryptography 套件，請先 pip install cryptography")
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _A

    return _A


def decrypt_secret(blob: bytes, master_key: bytes) -> bytes:
    """解密 "v10"-prefixed OSCrypt blob。"""
    if blob[:3] != b"v10":
        raise ValueError(f"唔支援嘅 blob 前綴: {blob[:3]!r}（只支援 v10）")
    AESGCM = _aesgcm()
    nonce = blob[3:15]
    ciphertext = blob[15:]
    return AESGCM(master_key).decrypt(nonce, ciphertext, None)


def encrypt_secret(plaintext: bytes, master_key: bytes) -> bytes:
    """加密成 "v10"-prefixed OSCrypt blob。"""
    AESGCM = _aesgcm()
    nonce = os.urandom(12)
    ciphertext = AESGCM(master_key).encrypt(nonce, plaintext, None)
    return b"v10" + nonce + ciphertext


def mask(value: str) -> str:
    """安全顯示：只留首 6 尾 4。"""
    if not value:
        return "(empty)"
    if len(value) <= 12:
        return f"{value[:3]}…({len(value)} chars)"
    return f"{value[:6]}…{value[-4:]} ({len(value)} chars)"


if __name__ == "__main__":
    import sys

    ls = sys.argv[1] if len(sys.argv) > 1 else (
        r"C:/Users/User/AppData/Roaming/Cursor/Local State"
    )
    mk = load_master_key(ls)
    print(f"master key: {len(mk)} bytes  OK")
