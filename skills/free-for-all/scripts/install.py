#!/usr/bin/env python3
"""
install.py — 把 OpenRouter 模型一次過寫入 WorkBuddy / DSH / Qwen Code

安全設計：
  * API key 唔好放命令行（會觸發敏感內容審批攔截）
  * 取值順序：--key 引數 → OR_KEY 環境變數 → ~/.qwen/.env 的OPENAI_API_KEY
  * 每次寫入前自動備份
  * --sync-only 只讀不寫，用嚟查三邊是否一致

用法：
  python install.py --key sk-or-v1-xxx --models "a/b:free,c/d:free"
  python install.py --preset free        # 內置免費組合
  python install.py --preset paid        # 內置 Grok 組合
  python install.py --sync-only          # 只檢查不修改
  python install.py --doctor             # 實測每個 model 是否通
"""
import argparse
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request

# ---------------------------------------------------------------- 路徑
WB_PATH  = os.path.expanduser("~/.workbuddy/models.json")
DSH_PATH = os.path.expanduser("~/.dsh/profiles/desktop/cordis.patch.yml")
QWEN_PATH = os.path.expanduser("~/.qwen/.env")

OR_BASE = "https://openrouter.ai/api/v1"
OR_URL  = f"{OR_BASE}/chat/completions"

# ---------------------------------------------------------------- 內置組合
PRESETS = {
    "free": [
        ("liquid/lfm-2.5-2.6b:free",   "LFM 2.5 2.6B (Free)",             65536,  True,  False),
        ("poolside/laguna-s-2.1:free", "Poolside Laguna S 2.1 (Free)",   262144, True,  False),
        ("google/gemma-4-31b-it:free", "Gemma 4 31B IT (Free)",           262144, True,  False),
        ("google/gemma-4-26b-a4b-it:free", "Gemma 4 26B A4B IT (Free)",   262144, True,  False),
    ],
    "paid": [
        ("x-ai/grok-4.20",       "Grok 4.20 (2M ctx, 最抵)",  2000000, True, True),
        ("x-ai/grok-build-0.1",  "Grok Build 0.1 (最平)",      256000, True, False),
        ("x-ai/grok-4.7",        "Grok 4.7",                   500000, True, True),
    ],
    "qwen": [
        ("qwen/qwen3.8-flash",      "Qwen3.8 Flash (最抵)",   1000000, True, False),
        ("qwen/qwen3-coder-next",   "Qwen3 Coder Next",        262144, True, False),
        ("qwen/qwen3-coder",        "Qwen3 Coder",             262144, True, False),
        ("qwen/qwen3.7-plus",       "Qwen3.7 Plus",           1000000, True, False),
        ("qwen/qwen3.8-27b",        "Qwen3.8 27B",            1000000, True, False),
        ("qwen/qwen3.8-max-0902",   "Qwen3.8 Max 0902",       1000000, True, False),
        ("qwen/qwen3.7-max",        "Qwen3.7 Max",            1000000, True, False),
    ],
    "kimi": [
        ("moonshotai/kimi-k2.5",       "Kimi K2.5",             262144, True, False),
        ("moonshotai/kimi-k2.7-code",  "Kimi K2.7 Code",        262144, True, False),
        ("moonshotai/kimi-k2",         "Kimi K2",               131072, True, False),
        ("moonshotai/kimi-k2.6",       "Kimi K2.6",             262144, True, False),
        ("moonshotai/kimi-k3",         "Kimi K3 (1M ctx)",     1048576, True, True),
    ],
    "doubao": [
        ("bytedance-seed/seed-1.6-flash", "豆包 Seed 1.6 Flash",   262144, True, False),
        ("bytedance-seed/seed-2.0-mini",  "豆包 Seed 2.0 Mini",    262144, True, False),
        ("bytedance-seed/seed-2.0-code",  "豆包 Seed 2.0 Code",    262144, True, False),
        ("bytedance-seed/seed-2-1-turbo", "豆包 Seed 2.1 Turbo",   262144, True, False),
        ("bytedance-seed/seed-2.0-lite",  "豆包 Seed 2.0 Lite",    262144, True, False),
        ("bytedance-seed/seed-1.6",       "豆包 Seed 1.6",         262144, True, False),
    ],
}
# "all" 必須在 PRESETS 建好之後才能組装（否則 dict literal 內引用不到自己）
PRESETS["all"] = (
    PRESETS["free"] + PRESETS["paid"] + PRESETS["qwen"]
    + PRESETS["kimi"] + PRESETS["doubao"]
)

# 已知持續 429 / provider 過載嘅 model，唔可以選做預設主模型。
# （實測 2026-10-19~20：Google provider 側免費額度長期被搶，連續多日 429）
DEGRADED = {
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
}

# 免費 model 之間嘅穩定優先次序（實測穩定性：lfm 最佳）。
# set 迭代順序唔穩定，所以用呢個 list 做 tiebreak。
FREE_PREFERENCE = [
    "liquid/lfm-2.5-2.6b:free",   # 實測最穩 + function calling 支援
    "poolside/laguna-s-2.1:free",
]

# 已知單價（input $/1M token），用嚟揀最平主模型。
# 未列出的 model 視為高價（999），避免被隨意選中。
COST = {
    # 免費
    "liquid/lfm-2.5-2.6b:free": 0.0,
    "poolside/laguna-s-2.1:free": 0.0,
    "google/gemma-4-31b-it:free": 0.0,
    "google/gemma-4-26b-a4b-it:free": 0.0,
    # qwen
    "qwen/qwen3.8-flash": 0.075,
    "qwen/qwen3-coder-next": 0.100,
    "qwen/qwen3-coder": 0.100,
    "qwen/qwen3.7-plus": 0.200,
    "qwen/qwen3.8-27b": 0.240,
    "qwen/qwen3.8-max-0902": 0.500,
    "qwen/qwen3.7-max": 0.500,
    # grok
    "x-ai/grok-build-0.1": 1.00,
    "x-ai/grok-4.20": 1.25,
    "x-ai/grok-4.7": 2.00,
    # kimi
    "moonshotai/kimi-k3": 0.239,
    "moonshotai/kimi-k2.5": 0.500,
    "moonshotai/kimi-k2": 0.570,
    "moonshotai/kimi-k2-0905": 0.600,
    "moonshotai/kimi-k2-thinking": 0.600,
    "moonshotai/kimi-k2.6": 0.650,
    "moonshotai/kimi-k2.7-code": 0.671,
    # doubao / seed
    "bytedance-seed/seed-1.6-flash": 0.075,
    "bytedance-seed/seed-2.0-mini": 0.100,
    "bytedance/ui-tars-1.5-7b": 0.100,
    "bytedance-seed/seed-1.6": 0.250,
    "bytedance-seed/seed-2.0-lite": 0.250,
    "bytedance-seed/seed-2.0-code": 0.500,
    "bytedance-seed/seed-2-1-turbo": 0.500,
}

# ---------------------------------------------------------------- 工具函數


def resolve_key(cli_key=None):
    """取值順序：CLI → OR_KEY 環境變數 → ~/.qwen/.env"""
    if cli_key:
        return cli_key
    k = os.environ.get("OR_KEY")
    if k:
        return k
    if os.path.isfile(QWEN_PATH):
        with open(QWEN_PATH, encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s.startswith("OPENAI_API_KEY="):
                    v = s.split("=", 1)[1].strip()
                    if v:
                        return v
    sys.exit(
        "ERROR: 搵唔到 API key。\n"
        "  做法一（推薦，避免敏感內容審批攔截）：\n"
        "    先手動寫好 ~/.qwen/.env（內含 OPENAI_API_KEY=sk-or-v1-xxx）\n"
        "  做法二：設定環境變數 OR_KEY\n"
        "  做法三：直接用 --key 參數（會觸發審批，較慢）"
    )


def backup(path, tag):
    if not os.path.isfile(path):
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dst = f"{path}.bak-{stamp}"
    shutil.copy2(path, dst)
    return dst


def hr(title=""):
    line = "─" * 62
    print(f"\n{line}" if title else line)
    if title:
        print(f"  {title}")
        print(line)


# ---------------------------------------------------------------- 驗證


def check_key(key):
    """驗證 key 有效性 + 免費額度。回 dict。"""
    req = urllib.request.Request(
        f"{OR_BASE}/key", headers={"Authorization": f"Bearer {key}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read()).get("data") or {}
            if not d:
                return {"ok": False, "reason": "INVALID"}
            return {
                "ok": True,
                "free": d.get("is_free_tier"),
                "limit": d.get("limit"),
                "remaining": d.get("limit_remaining"),
                "usage": d.get("usage"),
            }
    except urllib.error.HTTPError as e:
        return {"ok": False, "reason": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "reason": str(e)}


def check_model(key, model, max_tokens=400):
    """實測 model 能否 chat。回 dict。"""
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "Reply with only: OK"}],
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(
        OR_URL,
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            d = json.loads(r.read())
            c = d["choices"][0]["message"]
            return {
                "ok": True,
                "reply": (c.get("content") or "").strip()[:40],
                "cost": d["usage"]["cost"],
            }
    except urllib.error.HTTPError as e:
        try:
            code = json.loads(e.read()).get("error", {}).get("code", e.code)
        except Exception:
            code = e.code
        return {"ok": False, "code": code}
    except Exception as e:
        return {"ok": False, "code": str(e)[:60]}


# ---------------------------------------------------------------- 寫入


def write_workbuddy(key, specs):
    existing = []
    if os.path.isfile(WB_PATH):
        with open(WB_PATH, encoding="utf-8") as f:
            existing = json.load(f)
    have = {e.get("id") for e in existing}
    added = 0
    for mid, name, _ctx, tools, reason in specs:
        if mid in have:
            continue
        existing.append({
            "id": mid,
            "name": name,
            "vendor": "Custom",
            "url": f"{OR_BASE}/chat/completions",
            "apiKey": key,
            "supportsToolCall": tools,
            "supportsImages": False,
            "supportsReasoning": reason,
            "useCustomProtocol": False,
        })
        added += 1
    if added:
        b = backup(WB_PATH, "workbuddy")
        with open(WB_PATH, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        print(f"  WorkBuddy : +{added} 個，現共 {len(existing)} 條   (備份 {os.path.basename(b)})")
    else:
        print(f"  WorkBuddy : 已齊，{len(existing)} 條")
    return added


def write_dsh(key, specs):
    """寫入 DSH cordis.patch.yml。

    ⚠️ 2026-10-20 更新：DSH 現時主要用 `@deepseek-ai/dsh-llm-pi-ai` plugin，
    採用多 provider 路由結構（providers.workbuddy / providers.qwen），
    且憑證用 `apiKeyEnv` 引用（key 唔寫入設定檔）。
    舊的 `llm-deepseek` block 仍然支援，但優先插入 pi-ai 的 qwen route。

    插入策略：
      1. 若存在 `llm-pi-ai` block → 插到其 `qwen:` provider 的 models 陣列
      2. 否則 → 插到 `llm-deepseek` 的 models 陣列
      3. 否則 → 插到 agent-preset-registry 之前
    """
    if not os.path.isfile(DSH_PATH):
        print(f"  DSH       : ⚠ 搵唔到 {DSH_PATH}，跳過")
        return 0
    with open(DSH_PATH, encoding="utf-8") as f:
        s = f.read()

    new_specs = [sp for sp in specs if sp[0] not in s]
    if not new_specs:
        print("  DSH       : 已齊")
        return 0

    lines = [f"          - id: {mid}\n            name: {n}\n            contextWindow: {ctx}"
             for mid, n, ctx, _t, _r in new_specs]
    block = "\n".join(lines)

    b = backup(DSH_PATH, "dsh")
    old = s

    if "- id: llm-pi-ai" in s:
        # 插到 qwen: provider 的 models 陣列末尾
        # 策略：搵 "      qwen:" 之後第一個 "        models:" 行，插到其 models 區塊尾
        idx = s.find("\n      qwen:")
        if idx != -1:
            models_idx = s.find("        models:", idx)
            if models_idx != -1:
                # 搵該 models 陣列的結尾（下一個少於同 indent 的 key）
                tail = s[models_idx:]
                import re as _re
                m = _re.search(r"\n(?=      \w)", tail)
                end = models_idx + (m.start() if m else len(tail))
                s = s[:end] + "\n" + block + s[end:]
                where = "llm-pi-ai · qwen route"
            else:
                s = s.rstrip() + "\n" + block + "\n"
                where = "llm-pi-ai (fallback)"
        else:
            s = s.rstrip() + "\n" + block + "\n"
            where = "llm-pi-ai (fallback)"
    elif "- id: llm-deepseek" in s:
        marker = "\n- id: agent-preset-registry"
        if marker in s:
            s = s.replace(marker, "\n" + block + marker, 1)
        else:
            s = s.rstrip() + "\n" + block + "\n"
        where = "llm-deepseek"
    else:
        s = s.rstrip() + "\n" + block + "\n"
        where = "root (fallback)"

    if s != old:
        with open(DSH_PATH, "w", encoding="utf-8") as f:
            f.write(s)
        print(f"  DSH       : +{len(new_specs)} 個 → {where}   (備份 {os.path.basename(b)})")
    return len(new_specs)


def write_qwen(key, models):
    """寫入 ~/.qwen/.env。

    主模型選擇原則：**全局最平嘅一個**（含免費 model），唔係本次傳入清單嘅第一個。
    （2026-10-20 教訓：--models 傳入順序不代表成本順序；preset 內第一個可能係最貴。）
    """
    os.makedirs(os.path.dirname(QWEN_PATH), exist_ok=True)
    b = backup(QWEN_PATH, "qwen") if os.path.isfile(QWEN_PATH) else None

    # 候選 = 傳入的 models + COST 表內所有已知 model
    candidates = {sp[0] for sp in models} | set(COST.keys())
    # 排除已知過載 model
    candidates -= DEGRADED
    # 免費優先，其次單價最低；同單價用 FREE_PREFERENCE 做穩定 tiebreak
    def rank(m):
        free_rank = FREE_PREFERENCE.index(m) if m in FREE_PREFERENCE else 99
        return (0 if m.endswith(":free") else 1, COST.get(m, 999.0), free_rank, m)
    primary = min(candidates, key=rank)

    content = (
        "# OpenRouter 配置（由 openrouter-bridge plugin 生成）\n"
        f"OPENAI_BASE_URL={OR_BASE}\n"
        f"OPENAI_API_KEY={key}\n"
        f"OPENAI_MODEL={primary}\n"
        "# 註：可手動改用其他，例如 qwen/qwen3.8-flash($0.000022)、moonshotai/kimi-k2.5($0.000025)\n"
    )
    with open(QWEN_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    try:
        os.chmod(QWEN_PATH, 0o600)
    except OSError:
        pass
    print(f"  Qwen Code : 已寫入 {os.path.basename(QWEN_PATH)}  (model={primary})"
          + (f", 備份 {os.path.basename(b)}" if b else ""))


# ---------------------------------------------------------------- 檢查


def read_state():
    state = {}
    if os.path.isfile(WB_PATH):
        try:
            with open(WB_PATH, encoding="utf-8") as f:
                state["workbuddy"] = [e.get("id") for e in json.load(f)]
        except Exception as e:
            state["workbuddy"] = f"<讀取失敗: {e}>"
    else:
        state["workbuddy"] = "<檔案不存在>"

    if os.path.isfile(DSH_PATH):
        with open(DSH_PATH, encoding="utf-8") as f:
            s = f.read()
        state["dsh"] = [
            ln.split("id: ")[1].strip()
            for ln in s.splitlines()
            if ln.strip().startswith("- id:") and "/" in ln
        ]
    else:
        state["dsh"] = "<檔案不存在>"

    if os.path.isfile(QWEN_PATH):
        with open(QWEN_PATH, encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("OPENAI_MODEL="):
                    state["qwen"] = [line.split("=", 1)[1].strip()]
                    break
            else:
                state["qwen"] = ["<未設定>"]
    else:
        state["qwen"] = ["<檔案不存在>"]
    return state


def show_sync():
    st = read_state()
    hr("三邊同步狀態")
    for tool, ids in st.items():
        label = {"workbuddy": "WorkBuddy", "dsh": "DSH", "qwen": "Qwen Code"}[tool]
        print(f"\n  {label} ({len(ids)} 個)")
        for i in ids:
            print(f"    • {i}")

    hr("同步差異")
    wb = set(st.get("workbuddy", []))
    dsh = set(st.get("dsh", []))
    qw = set(st.get("qwen", []))
    only_wb = wb - dsh
    only_dsh = dsh - wb
    common = wb & dsh

    if not only_wb and not only_dsh:
        print("  ✅ WorkBuddy 與 DSH 模型清單一致")
    else:
        if only_wb:
            print(f"  ⚠ 只有 WorkBuddy 有: {', '.join(sorted(only_wb))}")
        if only_dsh:
            print(f"  ⚠ 只有 DSH 有: {', '.join(sorted(only_dsh))}")
    if common:
        print(f"  共同: {len(common)} 個")
    if qw - wb:
        print(f"  ℹ Qwen 主模型: {', '.join(qw)}")


# ---------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser(description="OpenRouter 模型三邊安裝器")
    ap.add_argument("--key", help="API key（建議改用 OR_KEY 環境變數）")
    ap.add_argument("--models", help="逗號分隔 model id")
    ap.add_argument("--preset", choices=list(PRESETS), help="內置組合")
    ap.add_argument("--sync-only", action="store_true", help="只顯示三邊狀態")
    ap.add_argument("--doctor", action="store_true", help="實測每個 model")
    args = ap.parse_args()

    if args.sync_only:
        show_sync()
        return

    # 決定 model 清單
    specs = []
    if args.models:
        ctx_map = {m: c for m, _n, c, _t, _r in PRESETS["all"]}
        for mid in [m.strip() for m in args.models.split(",") if m.strip()]:
            specs.append((mid, mid.split("/")[-1], ctx_map.get(mid, 262144), True, False))
    elif args.preset:
        specs = PRESETS[args.preset]
    else:
        ap.print_help()
        return

    key = resolve_key(args.key)

    hr(f"安裝 {len(specs)} 個模型")
    k = check_key(key)
    if not k["ok"]:
        print(f"  ⚠ API key 檢查: {k['reason']} — 仍然繼續寫入，但模型會用唔到")
    else:
        free = "免費層" if k["free"] else "付費層"
        extra = f"，剩餘額度 {k['remaining']}/{k['limit']}" if k.get("limit") else ""
        print(f"  API key: ✅ 有效（{free}{extra}）")

    write_workbuddy(key, specs)
    write_dsh(key, specs)
    write_qwen(key, specs)

    print("\n✅ 完成。記得重啟 WorkBuddy 與 DSH。")

    if args.doctor:
        hr("實測健康檢查")
        for mid, name, _c, _t, _r in specs:
            r = check_model(key, mid)
            if r["ok"]:
                print(f"  ✅ {mid:34} ${r['cost']:.6f}  {r['reply']!r}")
            else:
                print(f"  ❌ {mid:34} [{r['code']}]")


if __name__ == "__main__":
    main()