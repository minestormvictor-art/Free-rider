#!/usr/bin/env python3
"""
add_gateway_models_to_workbuddy.py — 把 freellmapi gateway 上嘅免費 model
加入 WorkBuddy models.json（令 WorkBuddy UI 可以直接揀）

背景
  * WorkBuddy 嘅 models.json 只可以填 4 個 field 嘅 custom model，apiKey **必須非空**
    （官方 asar 邏輯：!isFilledString(e.apiKey) && !isLoopbackModelEndpoint(e.url) → 報錯）
  * 所以免 key 嘅 Kilo/LLM7 直連唔 WorkBuddy 認。
  * 但本機 freellmapi gateway（:3001）已經幫我哋處理咗 no-key sentinel，
    而且 WorkBuddy 本身就用 WORKBUDDY_API_KEY 認證 → 經 gateway 就 OK。

做法
  * base URL = http://127.0.0.1:3001/v1/chat/completions
  * apiKey  = WORKBUDDY_API_KEY（由 ~/.dsh/.credentials.yaml 讀，唔會出現喺命令行）
  * model id 用 gateway 顯示嘅短 id（例如 minimax-m3.1-flash）

安全
  * 預設 DRY-RUN，--apply 先寫入
  * 自動備份 models.json
  * 只加 execution_status == 'ready' 嘅 model（即係真係有可用 provider 嘅）
"""
import argparse
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)
from install import WB_PATH  # noqa: E402

GATEWAY = "http://127.0.0.1:3001"
CRED_PATH = os.path.expanduser("~/.dsh/.credentials.yaml")


def hr(t=""):
    line = "─" * 64
    print(f"\n{line}" if t else line)
    if t:
        print(f"  {t}")
        print(line)


def gateway_key():
    if not os.path.isfile(CRED_PATH):
        return None
    t = open(CRED_PATH, encoding="utf-8").read()
    m = re.search(r"^\s*WORKBUDDY_API_KEY\s*:\s*(.+)$", t, re.M)
    return m.group(1).strip().strip('"').strip("'") if m else None


def gw(path, body=None, timeout=60):
    k = gateway_key()
    if not k:
        return None, "搵唔到 WORKBUDDY_API_KEY"
    h = {"Content-Type": "application/json", "Authorization": "Bearer " + k}
    d = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(GATEWAY + path, data=d, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")
    except Exception as e:
        return None, str(e)[:110]


def fetch_ready():
    st, body = gw("/v1/models")
    if st != 200:
        return None, body
    items = json.loads(body).get("data", [])
    return [m for m in items if m.get("execution_status") == "ready"], None


def main():
    ap = argparse.ArgumentParser(description="把 gateway 免費 model 加入 WorkBuddy")
    ap.add_argument("--apply", action="store_true", help="真正寫入 models.json")
    ap.add_argument("--all", action="store_true",
                    help="加入全部 ready model（預設只加免費）")
    args = ap.parse_args()

    hr("把 gateway 免費 model 加入 WorkBuddy models.json")

    key = gateway_key()
    if not key:
        print(f"  ❌ 搵唔到 WORKBUDDY_API_KEY（{CRED_PATH}）")
        return

    ready, err = fetch_ready()
    if ready is None:
        print(f"  ❌ gateway 唔通：{err}")
        print("     檢查 freellmapi 仲跑緊未（port 3001）")
        return

    # 免費 model 判斷：context / 名稱含 free，或者係我哋實測過嗰批 Kilo 免費 id
    FREE_HINT = ("free", "kilo", "nemotron", "minimax", "laguna", "lfm",
                 "north-mini", "dots", "inkling", "gemma", "free-router")
    if args.all:
        targets = ready
    else:
        targets = [m for m in ready
                   if any(h in (m.get("id", "") + " " + (m.get("name") or "")).lower()
                          for h in FREE_HINT)]

    print(f"  gateway ready model：{len(ready)} 個")
    print(f"  擬加入：{len(targets)} 個")

    existing = []
    if os.path.isfile(WB_PATH):
        with open(WB_PATH, encoding="utf-8") as f:
            existing = json.load(f)
    have = {e.get("id") for e in existing}
    gateway_url = f"{GATEWAY}/v1/chat/completions"

    new_entries = []
    for m in targets:
        mid = m.get("id")
        if mid in have:
            continue
        if any(e.get("url") == gateway_url and e.get("id") == mid for e in existing):
            continue
        ctx = m.get("context_window") or 262144
        new_entries.append({
            "id": mid,
            "name": f"{m.get('name') or mid} (Free via local gateway)",
            "vendor": "Custom",
            "url": gateway_url,
            "apiKey": key,
            "supportsToolCall": True,
            "supportsImages": False,
            "supportsReasoning": True,
            "useCustomProtocol": False,
            "maxInputTokens": ctx,
        })

    hr("擬加入嘅 entry")
    for e in new_entries:
        print(f"  {e['id']:<38} ctx={e['maxInputTokens']:<9} → {e['url']}")
    if not new_entries:
        print("  （全部已在 models.json，無需新增）")

    if not args.apply:
        print(f"\n💡 DRY-RUN：確認後加 --apply 執行。")
        return

    if not new_entries:
        return
    b = f"{WB_PATH}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(WB_PATH, b)
    existing.extend(new_entries)
    with open(WB_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 已加入 {len(new_entries)} 個，現共 {len(existing)} 條   (備份 {os.path.basename(b)})")
    print("  記得重啟 WorkBuddy。")


if __name__ == "__main__":
    main()
