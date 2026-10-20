#!/usr/bin/env python3
"""
configure_cursor_free.py — 將 Cursor 接到本機 freellmapi gateway，令 Cursor 用免費模型。

原理（全部經本機實測驗證，2026-10-20）：
  Cursor 3.25.6 BYOK = 三個位：
    1. openAIBaseUrl          → 明文，存喺 state.vscdb 嘅 applicationUser reactiveStorage
    2. secret://cursorAuth/openAIKey → Chromium OSCrypt v10 加密（v10 + nonce + AES-256-GCM）
    3. aiSettings.userAddedModels / modelOverrideEnabled → 明文，model picker 顯示嘅模型清單

  master key 喺 <UserData>/Local State → os_crypt.encrypted_key（DPAPI 保護，可用 pywin32 解）

用法：
    python configure_cursor_free.py --check          # 只睇現況，唔改
    python configure_cursor_free.py --apply          # 套用（需先關閉 Cursor）
    python configure_cursor_free.py --apply --models "minimax-m3.1-flash,nemotron-3.5-lightning"
    python configure_cursor_free.py --apply --state-db <副本路徑>   # 沙盒 dry-run

⚠️ 必須先關閉 Cursor 再 --apply（state.vscdb 有 WAL，Cursor 行緊寫會覆蓋）。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cursor_oscrypt import decrypt_secret, encrypt_secret, load_master_key, mask  # noqa: E402

CURSOR_USER = Path(os.environ.get("APPDATA", "")) / "Cursor" / "User"
GLOBAL_STORAGE = CURSOR_USER / "globalStorage"
STATE_DB = GLOBAL_STORAGE / "state.vscdb"
LOCAL_STATE = CURSOR_USER.parent / "Local State"

REACTIVE_KEY = (
    "src.vs.platform.reactivestorage.browser.reactiveStorageServiceImpl"
    ".persistentStorage.applicationUser"
)
SECRET_KEY = "secret://cursorAuth/openAIKey"

DEFAULT_GATEWAY = "http://127.0.0.1:3001/v1"
# Cursor 會用 WF_() 正規化 base URL：
#   - pathname == "/"  → 自動補 "/v1"
#   - 去尾斜杠
#   - 之後由 Cursor 自己拼 "/chat/completions"
# 所以 base URL 唔好自己加 "/chat/completions"（會變雙重 suffix）。
DEFAULT_MODELS = [
    "minimax-m3.1-flash",
    "nemotron-3.5-lightning",
    "nemotron-3-ultra",
    "north-mini-code",
    "lfm-2.5-2.6b",
    "free-router",
]
# 註：nemotron-3-super 已於 2026-10-20 實測 404（上游下架），唔好再放落 DEFAULT_MODELS。
# 全部 6 個模型實測 HTTP 200 + cost=0。


def gateway_key(gateway_db: Path) -> str:
    """由 freellmapi 讀統一 API key。"""
    con = sqlite3.connect(f"file:{gateway_db}?mode=ro", uri=True)
    try:
        row = con.execute(
            "SELECT value FROM settings WHERE key='unified_api_key'"
        ).fetchone()
    finally:
        con.close()
    if not row:
        raise SystemExit(f"[!] 喺 {gateway_db} 搵唔到 unified_api_key")
    return row[0]


def read_state(db: Path | None = None) -> tuple[dict, bytes | None]:
    """讀 applicationUser JSON + openAIKey blob。"""
    target = db or STATE_DB
    con = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        row = con.execute(
            "SELECT value FROM ItemTable WHERE key=?", (REACTIVE_KEY,)
        ).fetchone()
        app = json.loads(row[0]) if row else {}
        srow = con.execute(
            "SELECT value FROM ItemTable WHERE key=?", (SECRET_KEY,)
        ).fetchone()
    finally:
        con.close()
    blob = None
    if srow:
        try:
            blob = bytes(json.loads(srow[0])["data"])
        except Exception:
            blob = None
    return app, blob


def write_state(app: dict, key_blob: bytes | None, db: Path | None = None) -> None:
    """寫回 state.vscdb（需 Cursor 已關閉）。"""
    target = db or STATE_DB
    con = sqlite3.connect(str(target))
    try:
        con.execute(
            "INSERT INTO ItemTable(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (REACTIVE_KEY, json.dumps(app, ensure_ascii=False)),
        )
        if key_blob is not None:
            con.execute(
                "INSERT INTO ItemTable(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (SECRET_KEY, json.dumps({"type": "Buffer", "data": list(key_blob)})),
            )
        con.commit()
    finally:
        con.close()


def cursor_running() -> bool:
    import subprocess

    try:
        # tasklist 輸出係 locale 編碼，唔好假設 UTF-8
        out = subprocess.run(
            ["tasklist"], capture_output=True, timeout=15
        ).stdout.decode("mbcs", errors="ignore")
    except Exception:
        return False
    return "Cursor.exe" in out


def main() -> int:
    ap = argparse.ArgumentParser(description="將 Cursor 接到免費 gateway")
    ap.add_argument("--check", action="store_true", help="只睇現況")
    ap.add_argument("--apply", action="store_true", help="套用")
    ap.add_argument("--gateway", default=DEFAULT_GATEWAY, help="gateway base URL")
    ap.add_argument(
        "--gateway-db",
        default=str(Path.home() / "freellmapi" / "server" / "data" / "freeapi.db"),
        help="freellmapi SQLite 路徑",
    )
    ap.add_argument("--models", help="逗號分隔嘅 model id（預設用內置清單）")
    ap.add_argument(
        "--state-db",
        help="覆蓋 state.vscdb 路徑（沙盒 dry-run 用，會跳過 Cursor 進程檢查）",
    )
    ap.add_argument(
        "--wait",
        type=int,
        default=0,
        metavar="SEC",
        help="等 Cursor 關閉最多 SEC 秒，關咗就自動套用（唔會強制 kill Cursor）",
    )
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    if not args.check and not args.apply:
        ap.error("要 --check 或者 --apply")

    sandbox = Path(args.state_db) if args.state_db else None
    target_db = sandbox or STATE_DB

    if not target_db.exists():
        print(f"[!] 搵唔到 {target_db}")
        return 1

    app, blob = read_state(target_db)
    ai = app.setdefault("aiSettings", {})
    added = ai.get("userAddedModels") or []
    override = ai.get("modelOverrideEnabled") or []

    print("=" * 68)
    print("Cursor BYOK 現況")
    print("=" * 68)
    print(f"  openAIBaseUrl    : {app.get('openAIBaseUrl')!r}")
    print(f"  useOpenAIKey     : {app.get('useOpenAIKey')}")
    print(f"  userAddedModels  : {added}")
    print(f"  modelOverride    : {override}")
    if blob:
        try:
            mk = load_master_key(LOCAL_STATE)
            pt = decrypt_secret(blob, mk).decode("utf-8", "replace")
            print(f"  openAIKey        : {mask(pt)}")
        except Exception as e:
            print(f"  openAIKey        : (解密失敗 {e})")
    print(f"  Cursor 行緊?     : {cursor_running()}")

    if args.check:
        return 0

    # ---- apply ----
    if not sandbox and cursor_running():
        if args.wait > 0:
            import time

            deadline = time.time() + args.wait
            print(f"[*] 等 Cursor 關閉（最多 {args.wait} 秒）…")
            while time.time() < deadline:
                if not cursor_running():
                    print("[OK] Cursor 已關閉，開始套用")
                    break
                time.sleep(3)
            else:
                print("\n[!] 超時，Cursor 仲行緊 —— 冇改任何嘢。")
                print("    再跑一次，或用 --wait 加大秒數。")
                return 2
        else:
            print("\n[!] Cursor 仲行緊 —— 要先完全關閉 Cursor（所有視窗）再 run。")
            print("    原因：state.vscdb 開住 WAL，行緊寫會蓋掉我哋改嘅值。")
            print("    （用 --state-db <副本> 可以做沙盒 dry-run，唔需要關 Cursor）")
            print("    （用 --wait 600 可以自動等佢關咗再套用）")
            return 2

    models = (
        [m.strip() for m in args.models.split(",") if m.strip()]
        if args.models
        else list(DEFAULT_MODELS)
    )

    try:
        gw_key = gateway_key(Path(args.gateway_db))
    except Exception as e:
        print(f"[!] 攞 gateway key 失敗: {e}")
        return 1

    if not args.no_backup:
        bak = target_db.with_name(
            f"{target_db.name}.bak-{args.gateway.replace(':', '-').replace('/', '-')}"
        )
        shutil.copy2(target_db, bak)
        print(f"\n[OK] 已備份 → {bak.name}")

    mk = load_master_key(LOCAL_STATE)
    new_blob = encrypt_secret(gw_key.encode("utf-8"), mk)

    app["openAIBaseUrl"] = args.gateway
    app["useOpenAIKey"] = True
    ai["userAddedModels"] = sorted(set(added) | set(models))
    ai["modelOverrideEnabled"] = sorted(set(override) | set(models))
    ai.setdefault("modelOverrideDisabled", [])

    write_state(app, new_blob, target_db)

    print(f"[OK] openAIBaseUrl → {args.gateway}")
    print(f"[OK] openAIKey → 已用 OSCrypt v10 重新加密（{mask(gw_key)}）")
    print(f"[OK] userAddedModels      += {models}")
    print(f"[OK] modelOverrideEnabled += {models}")

    # ---- 自我驗證：讀回 + 解密 + 真打 gateway ----
    print("\n--- 自我驗證 ---")
    v_app, v_blob = read_state(target_db)
    if not v_blob:
        print("  [X] 讀唔到 openAIKey blob")
        return 1
    try:
        v_key = decrypt_secret(v_blob, mk).decode("utf-8", "replace")
    except Exception as e:
        print(f"  [X] 解密失敗: {e}")
        return 1
    ok_key = v_key == gw_key
    print(f"  base URL 讀回 : {v_app.get('openAIBaseUrl')}")
    print(f"  key 讀回+解密 : {'一致 ✅' if ok_key else '唔一致 ❌'}")
    if not ok_key:
        return 1

    # 真打 gateway
    try:
        import urllib.request

        body = json.dumps(
            {
                "model": models[0],
                "messages": [{"role": "user", "content": "reply with exactly: CURSOR_FREE_OK"}],
                "max_tokens": 20,
            }
        ).encode()
        req = urllib.request.Request(
            f"{args.gateway.rstrip('/')}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {v_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=45) as r:
            d = json.loads(r.read())
            cost = (d.get("usage") or {}).get("cost")
            txt = (d["choices"][0]["message"].get("content") or "")[:60]
            print(f"  gateway 實測   : HTTP {r.status} | cost={cost} | {txt!r}")
    except Exception as e:
        print(f"  [!] gateway 實測失敗: {type(e).__name__}: {e}")

    print("\n下一步：重啟 Cursor → Settings → Models 揀新模型 → 試打一個 prompt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
