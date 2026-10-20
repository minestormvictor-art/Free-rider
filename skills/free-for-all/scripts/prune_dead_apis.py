#!/usr/bin/env python3
"""
prune_dead_apis.py — 清理已廢嘅自定義 API model（三邊同步）

每月 1 號執行。判定邏輯（重要）：
  * 判定「已廢」**只靠 OpenRouter catalog 對比**（GET /api/v1/models）
    → model id 唔喺 catalog = 已下架 / 已改名 → 可安全移除
  * **唔用實測 chat 判定**，因為 429（provider 過載 或 每日 request counter 用完）
    唔等於 model 已廢，實測會誤殺大量正常 model
  * 403 = 限特殊場合，唔算廢

安全設計：
  * 每次改動前自動備份三邊
  * --dry-run 預覽（預設就係 dry-run，要 --apply 先寫入）
  * 支援 --keep 保護指定 model id
  * key 唔會出現在命令行
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

from install import WB_PATH, DSH_PATH, QWEN_PATH, OR_BASE, resolve_key  # noqa: E402

# 保護名單：唔會被自動移除（用 id 前綴或完整 id）
DEFAULT_KEEP = [
    "liquid/lfm-2.5-2.6b:free",       # 實測最穩
    "minimax/minimax-m3.1-flash:free",  # 唯一 auto 主動 tool_call
    "qwen/qwen3-coder-next",          # 最平 + 支援 tools
    "openrouter/free",                # OpenRouter 官方 router
]

# 已知的 alias → 現名 對應（model 改名但仍然可用，唔算廢，唔移除）
ALIAS_NOTE = "（alias，catalog 用現名，保留）"


def hr(t=""):
    line = "─" * 64
    print(f"\n{line}" if t else line)
    if t:
        print(f"  {t}")
        print(line)


def fetch_catalog():
    """拉 OpenRouter catalog 全部 model id。"""
    key = resolve_key()
    req = urllib.request.Request(
        f"{OR_BASE}/models", headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())["data"]
    return {m["id"] for m in data}, {m["id"] for m in data if m["id"].endswith(":free")}


def read_workbuddy():
    if not os.path.isfile(WB_PATH):
        return []
    with open(WB_PATH, encoding="utf-8") as f:
        return json.load(f)


def read_dsh_ids():
    if not os.path.isfile(DSH_PATH):
        return []
    with open(DSH_PATH, encoding="utf-8") as f:
        s = f.read()
    return [ln.split("id: ")[1].strip() for ln in s.splitlines()
            if ln.strip().startswith("- id:") and "/" in ln]


def is_kept(mid, keep_list):
    for k in keep_list:
        if mid == k or mid.startswith(k + ":") or mid.startswith(k):
            return True
    return False


def analyze(wb_models, dsh_ids, catalog, keep_list):
    """回 (dead_ids, alive_ids, other_provider_ids, dsh_dead)。

    ⚠️ 只有 OpenRouter 嘅 model 可以用 catalog 判定。
    本機 gateway（:3001）嘅 model 唔喺 OpenRouter catalog，必須跳過 ——
    否則會把全部 gateway model 誤判為「已廢」而殺咗。
    """
    dead, alive, other, gateway = [], [], [], []

    for e in wb_models:
        mid = e.get("id") or ""
        if not mid:
            continue
        url = (e.get("url") or "").lower()
        if "127.0.0.1" in url or "localhost" in url:
            # 本機 gateway（freellmapi）— 用 gateway 自己嘅 catalog 判定
            gateway.append(mid)
            continue
        if "openrouter.ai" not in url:
            other.append(mid)
            continue
        if is_kept(mid, keep_list):
            alive.append((mid, "protected"))
        elif mid in catalog:
            alive.append((mid, "in-catalog"))
        else:
            dead.append((mid, "not-in-catalog"))

    # DSH：只清理 OpenRouter 格式嘅 id（含 "/"）。短 id（無 "/"）係 gateway
    # model → 唔喺 OpenRouter catalog，一定要跳過。
    dsh_dead = [i for i in dsh_ids
                if "/" in i and i not in catalog and not is_kept(i, keep_list)]
    return dead, alive, other, dsh_dead, gateway


def apply_prune(wb_models, dsh_dead, dead, keep_list):
    """執行清理。回 (移除數, 備份路徑列表)。"""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backups = []
    dead_ids = {m for m, _ in dead}

    # --- WorkBuddy ---
    if dead_ids:
        if os.path.isfile(WB_PATH):
            b = f"{WB_PATH}.bak-{stamp}"
            shutil.copy2(WB_PATH, b)
            backups.append(b)
        keep_models = [e for e in wb_models if (e.get("id") or "") not in dead_ids]
        with open(WB_PATH, "w", encoding="utf-8") as f:
            json.dump(keep_models, f, ensure_ascii=False, indent=2)

    # --- DSH ---
    if dsh_dead and os.path.isfile(DSH_PATH):
        b = f"{DSH_PATH}.bak-{stamp}"
        shutil.copy2(DSH_PATH, b)
        backups.append(b)
        with open(DSH_PATH, encoding="utf-8") as f:
            s = f.read()
        lines = s.splitlines(keepends=True)
        out, removed = [], 0
        for ln in lines:
            m = re.match(r"^\s*-\s+id:\s*(\S+)\s*$", ln)
            if m and m.group(1) in set(dsh_dead):
                removed += 1
                continue
            out.append(ln)
        with open(DSH_PATH, "w", encoding="utf-8") as f:
            f.writelines(out)

    return len(dead_ids), backups


def check_qwen_primary(catalog, keep_list):
    """檢查 Qwen Code 主模型仲在唔在 catalog。"""
    if not os.path.isfile(QWEN_PATH):
        return None
    with open(QWEN_PATH, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s.startswith("OPENAI_MODEL="):
                mid = s.split("=", 1)[1].strip()
                if not mid:
                    return None
                if mid in catalog or is_kept(mid, keep_list):
                    return (mid, True)
                return (mid, False)
    return None


def main():
    ap = argparse.ArgumentParser(description="清理已廢自定義 API model")
    ap.add_argument("--apply", action="store_true",
                    help="真正寫入（預設 dry-run）")
    ap.add_argument("--keep", action="append", default=[],
                    help="額外保護嘅 model id（可重複）")
    args = ap.parse_args()

    keep_list = DEFAULT_KEEP + args.keep

    hr("清理已廢自定義 API " + ("[APPLY]" if args.apply else "[DRY-RUN] 預覽"))
    print(f"  判定依據：OpenRouter catalog（GET /api/v1/models）")
    print(f"  唔用實測判定 → 429（過載／每日上限）唔會誤殺正常 model")

    try:
        catalog, free = fetch_catalog()
    except SystemExit as e:
        print(f"\n  ❌ {e}")
        return
    except Exception as e:
        print(f"\n  ❌ 拉 catalog 失敗：{e}")
        return
    print(f"\n  catalog：{len(catalog)} 個 model（其中 {len(free)} 個 :free）")

    wb = read_workbuddy()
    dsh_ids = read_dsh_ids()
    dead, alive, other, dsh_dead, gateway = analyze(wb, dsh_ids, catalog, keep_list)

    hr("WorkBuddy 分析")
    print(f"  總數 {len(wb)}｜在 catalog {len(alive)}｜已廢 {len(dead)}｜"
          f"本機 gateway {len(gateway)}｜非 OpenRouter {len(other)}")
    if dead:
        print("\n  ❌ 已廢（唔喺 catalog → 下架或改名）：")
        for mid, why in dead:
            print(f"     • {mid}  ({why})")
    if gateway:
        print(f"\n  ℹ 本機 gateway（freellmapi）model {len(gateway)} 個 —— "
              f"用 gateway 自己的 catalog 判定，唔會被本腳本誤殺")
    if other:
        print(f"\n  ℹ 非 OpenRouter provider（跳過，無 catalog 可比）：{len(other)} 個")
        for mid in other[:10]:
            print(f"     • {mid}")

    hr("DSH 分析")
    print(f"  總數 {len(dsh_ids)}｜已廢 {len(dsh_dead)}")
    for mid in dsh_dead:
        print(f"     • {mid}")

    qw = check_qwen_primary(catalog, keep_list)
    hr("Qwen Code 主模型")
    if qw:
        mid, ok = qw
        print(f"  {mid} → {'✅ 仍在 catalog' if ok else '❌ 已廢（建議手動改）'}")
    else:
        print("  （未設定）")

    hr("保護名單")
    for k in keep_list:
        print(f"  🔒 {k}")

    if not dead and not dsh_dead:
        print("\n✅ 冇已廢 model，唔使清。")
        return

    if not args.apply:
        print(f"\n💡 DRY-RUN：以上 {len(dead)} 個 WorkBuddy + {len(dsh_dead)} 個 DSH "
              f"model 會被移除。確認後加 --apply 執行。")
        return

    n, backups = apply_prune(wb, dsh_dead, dead, keep_list)
    print(f"\n✅ 已移除：WorkBuddy {n} 個 / DSH {len(dsh_dead)} 個")
    for b in backups:
        print(f"   備份：{os.path.basename(b)}")
    print("  註：Qwen Code 主模型如已廢需手動改（見上面提示）。")


if __name__ == "__main__":
    main()
