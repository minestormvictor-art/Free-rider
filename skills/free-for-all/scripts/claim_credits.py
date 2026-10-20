#!/usr/bin/env python3
"""
claim_credits.py — 多平台免費額度 / 積分巡檢

設計原則
  * 純讀取：唔會自動買嘢、唔會自動領取、唔會改任何設定
  * key 唔會出現在命令行或輸出
  * 每個平台嘅狀態都標明「可自動查」定「要手動去官網領」
  * 查唔到就講「未有憑證」，唔會作

支援平台
  workbuddy / openrouter / kimi / doubao(火山方舟) / minimax / cursor / qwen / grokbot
"""
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

# ---------------------------------------------------------------- 憑證位置（只讀，唔會寫）
ENV_FILES = [
    os.path.expanduser("~/.qwen/.env"),
    os.path.expanduser("~/.workbuddy/.env"),
    os.path.expanduser("~/.config/qwen/.env"),
    os.path.expanduser("~/.ark.env"),
    os.path.expanduser("~/.minimax.env"),
]
CRED_FILES = [
    os.path.expanduser("~/.dsh/.credentials.yaml"),
    os.path.expanduser("~/.cursor/cli-config.json"),
]
DSH_PATCH = os.path.expanduser("~/.dsh/profiles/desktop/cordis.patch.yml")
CURSOR_VSCDB = os.path.expanduser(
    "~/AppData/Roaming/Cursor/User/globalStorage/state.vscdb")
QWEN_USAGE = os.path.expanduser("~/.qwen/usage")
QWEN_RECORD = os.path.expanduser("~/.qwen/usage_record.jsonl")
ROSTER = os.path.expanduser(
    "~/.workbuddy/plugins/marketplaces/my-experts/plugins/grok-bot-roster/roster.json")
ROSTER_AGENTS = os.path.expanduser(
    "~/.workbuddy/plugins/marketplaces/my-experts/plugins/grok-bot-roster/agents")


def hr(t=""):
    line = "─" * 64
    print(f"\n{line}" if t else line)
    if t:
        print(f"  {t}")
        print(line)


def read_env_keys():
    """收集所有 .env 檔案嘅 KEY=VALUE（只喺記憶體，唔會輸出值）。"""
    out = {}
    for p in ENV_FILES:
        if not os.path.isfile(p):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if not s or s.startswith("#") or "=" not in s:
                        continue
                    k, v = s.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if v:
                        out.setdefault(k, v)
        except OSError:
            pass
    return out


def find_key(names):
    """喺 .env / 環境變數搵第一個存在嘅 key。"""
    env = read_env_keys()
    for n in names:
        if n in env:
            return env[n], f"env:{n}"
    for n in names:
        v = os.environ.get(n)
        if v:
            return v, f"os.environ:{n}"
    return None, None


def http_get(url, key=None, timeout=25):
    hdr = {"Accept": "application/json"}
    if key:
        hdr["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, headers=hdr)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def http_post(url, key, payload, timeout=60):
    body = json.dumps(payload).encode()
    hdr = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=body, headers=hdr)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


# ---------------------------------------------------------------- 各平台檢查函數

def check_openrouter():
    """OpenRouter：唯一有真實可查餘額 API 嘅。"""
    from install import resolve_key, check_key
    try:
        key = resolve_key()
    except SystemExit:
        return {"state": "no-cred", "detail": "~/.qwen/.env 無 OPENAI_API_KEY"}
    k = check_key(key)
    if not k["ok"]:
        return {"state": "error", "detail": f"key 無效：{k['reason']}"}
    tier = "免費層" if k.get("free") else "付費層"
    detail = f"{tier}，已用 ${k.get('usage')}"
    if k.get("limit"):
        detail += f"，餘額 ${k['remaining']:.4f} / ${k['limit']}"
    return {
        "state": "ok",
        "detail": detail,
        "claim": "免費層 50 req/day（UTC 計），要 1,000/day 需累計充值 $10（官方：9 credits 起計）",
        "manual": False,
    }


def check_workbuddy():
    """WorkBuddy 本機 gateway + models.json 健康。"""
    import socket
    gw = None
    for port in (3001,):
        s = socket.socket()
        s.settimeout(1.5)
        try:
            s.connect(("127.0.0.1", port))
            gw = port
        except OSError:
            pass
        finally:
            s.close()
    models = 0
    p = os.path.expanduser("~/.workbuddy/models.json")
    if os.path.isfile(p):
        try:
            models = len(json.load(open(p, encoding="utf-8")))
        except Exception:
            pass
    detail = f"models.json {models} 條"
    detail += f"，本機 gateway :{gw} 在線" if gw else "，本機 gateway 未開"
    return {
        "state": "ok" if gw else "warn",
        "detail": detail,
        "claim": "WorkBuddy 本身無獨立積分；走 OpenRouter 免費層",
        "manual": False,
    }


def check_kimi():
    """Kimi / Moonshot：查餘額 API。國際版無免費層，中國版新戶送 ¥15。"""
    key, src = find_key(["MOONSHOT_API_KEY", "KIMI_API_KEY", "MOONSHOT_KEY"])
    if not key:
        return {
            "state": "no-cred",
            "detail": "無 MOONSHOT_API_KEY",
            "claim": "國際版 platform.moonshot.ai 無免費層（要 $1 起充）；"
                     "中國版 platform.moonshot.cn 新用戶個人實名送 ¥15（一次性）",
            "manual": True,
            "url": "https://platform.moonshot.cn/console/account",
        }
    for base, label in (("https://api.moonshot.ai/v1", "國際"),
                        ("https://api.moonshot.cn/v1", "中國")):
        try:
            d = http_get(f"{base}/users/me/balance", key)
            dd = d.get("data") or {}
            return {
                "state": "ok",
                "detail": f"{label}版 餘額 ${dd.get('available_balance')} "
                          f"(現金 ${dd.get('cash_balance')} / 代金券 ${dd.get('voucher_balance')})",
                "claim": "代金券到期前用完；餘額 ≤ 0 會 exceeded_current_quota_error",
                "manual": False,
            }
        except urllib.error.HTTPError:
            continue
        except Exception:
            continue
    return {
        "state": "error",
        "detail": "key 存在但兩邊餘額 API 都失敗（host 唔對或 key 已失效）",
        "claim": "檢查 key 係由 platform.moonshot.ai 定 .cn 開",
        "manual": True,
    }


def check_doubao():
    """豆包 / 火山方舟：官方確認免費額度 50 萬 tokens/模型。"""
    key, src = find_key(["ARK_API_KEY", "DOUBAO_API_KEY", "VOLC_API_KEY"])
    if not key:
        return {
            "state": "no-cred",
            "detail": "無 ARK_API_KEY",
            "claim": "官方免費額度：Doubao-Seed-2.1-pro / 2.1-turbo / Seed-Evolving "
                     "各 50 萬 tokens；Seedream-4.5/4.0 各 200 張；"
                     "語音合成 5000 字符；聯網 2 萬次/月。"
                     "官方另有「協作獎勵計劃二期」：每日可領單模型最高 500 萬 Tokens",
            "manual": True,
            "url": "https://console.volcengine.com/ark/region:ark+cn-beijing/apikey",
        }
    base = "https://ark.cn-beijing.volces.com/api/v3"
    try:
        http_post(f"{base}/chat/completions", key,
                  {"model": "doubao-seed-2-1-turbo", "messages": [
                      {"role": "user", "content": "OK"}], "max_tokens": 4})
        return {"state": "ok", "detail": "ARK_API_KEY 有效，官方 base URL 可通",
                "claim": "免費額度餘額需登陸 console 睇（API 無餘額查詢接口）",
                "manual": True, "url": "https://console.volcengine.com/ark"}
    except urllib.error.HTTPError as e:
        code = e.code
        return {"state": "error", "detail": f"ARK key 測試失敗 HTTP {code}",
                "claim": "確認 endpoint 地區同 model id 對唔對", "manual": True}
    except Exception as e:
        return {"state": "error", "detail": f"ARK 連線失敗：{str(e)[:50]}",
                "claim": "檢查網絡", "manual": True}


def check_minimax():
    """MiniMax：官方確認完全按量計費，無免費層。"""
    key, src = find_key(["MINIMAX_API_KEY", "MINIMAX_KEY"])
    if not key:
        return {
            "state": "no-free-tier",
            "detail": "無 MINIMAX_API_KEY",
            "claim": "官方定價頁：MiniMax 全部按量計費（輸入 ¥1-4 / 百萬 tokens），"
                     "無免費層、無試用 credit。要用就要充值",
            "manual": False,
            "url": "https://platform.minimax.cn/docs/pricing/overview",
        }
    base = "https://api.minimaxi.com/v1"
    try:
        http_post(f"{base}/chat/completions", key,
                  {"model": "MiniMax-M3.1-Flash", "messages": [
                      {"role": "user", "content": "OK"}], "max_tokens": 4})
        return {"state": "ok", "detail": "MINIMAX_API_KEY 有效",
                "claim": "無免費層，只能按量計費", "manual": False}
    except urllib.error.HTTPError as e:
        return {"state": "error", "detail": f"MINIMAX key 測試失敗 HTTP {e.code}",
                "claim": "無免費層", "manual": False}
    except Exception as e:
        return {"state": "error", "detail": f"MINIMAX 連線失敗：{str(e)[:50]}",
                "claim": "無免費層", "manual": False}


def check_cursor():
    """Cursor：Hobby 免費層，BYOK 要手動入 UI（safeStorage 加密，冇程式可代勞）。"""
    has_vscdb = os.path.isfile(CURSOR_VSCDB)
    has_cli = os.path.isfile(os.path.expanduser("~/.cursor/cli-config.json"))
    # 版本：直接讀 package.json（比跑 cursor --version 可靠）
    ver = "未偵測到"
    pkg = os.path.expanduser(
        "~/AppData/Local/Programs/cursor/resources/app/package.json")
    if os.path.isfile(pkg):
        try:
            ver = json.load(open(pkg, encoding="utf-8")).get("version", ver)
        except Exception:
            pass
    installed = has_vscdb or has_cli
    return {
        "state": "ok" if installed else "no-cred",
        "detail": (f"已安裝（Cursor {ver}）" if installed
                   else f"未安裝{'（' + ver + '）' if ver != '未偵測到' else ''}"),
        "claim": "Hobby 免費層：2,000 completions/月 + 50 次慢速 premium request，"
                 "無需信用卡。BYOK 要喺 Cursor UI 手動貼 key（Electron safeStorage 加密，"
                 "冇任何指令可以代勞）",
        "manual": True,
        "url": "https://cursor.com/dashboard",
    }


def check_qwen():
    """Qwen Code：QwenOAuth 每日 1000 次；本機走 OpenRouter 所以 OAuth 額度未啟用。"""
    oauth = any(os.path.isfile(os.path.expanduser(p)) for p in
                ("~/.qwen/oauth_creds.json", "~/.qwen/oauth.json"))
    # 本機 .env 指向邊度
    target = "無"
    env = read_env_keys()
    if env.get("OPENAI_BASE_URL"):
        target = env["OPENAI_BASE_URL"]
    # 今日用量：由 usage_record.jsonl + usage/ 目錄統計
    today = time.strftime("%Y-%m-%d")
    sessions = 0
    if os.path.isfile(QWEN_RECORD):
        try:
            with open(QWEN_RECORD, encoding="utf-8") as f:
                for line in f:
                    if today in line:
                        sessions += 1
        except OSError:
            pass
    tok_file = os.path.join(QWEN_USAGE, f"token-usage-{today}.jsonl")
    tokens = 0
    calls = 0
    if os.path.isfile(tok_file):
        try:
            with open(tok_file, encoding="utf-8") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    calls += 1
                    for k, v in d.items():
                        if isinstance(v, (int, float)) and "token" in k.lower():
                            tokens += v
        except OSError:
            pass
    detail = f"現時指向 {target}"
    if sessions or calls:
        detail += f"，今日 {sessions} 個 session / {calls} 次呼叫"
        if tokens:
            detail += f" / {tokens:,.0f} tokens"
    else:
        detail += "，今日未見用量記錄"
    detail += ("；已用 OAuth（1000 次/日）" if oauth
               else "；未用 OAuth → 1000 次/日 額度未啟用")
    return {
        "state": "ok",
        "detail": detail,
        "claim": "官方：QwenOAuth 每日 1,000 次免費調用（2026-02-09 由 2,000 減半）。"
                 "要啟用要 `qwen` 內執行 /auth 選 QwenOAuth。"
                 "百煉 Coding Plan 需另外買 API Key（官方建議開「免費額度用完即停」防欠費）",
        "manual": oauth is False,
    }


def check_grokbot():
    """Grok Bot roster：本地 agent 索引，唔係 API 平台。"""
    n = 0
    if os.path.isdir(ROSTER_AGENTS):
        n = len([f for f in os.listdir(ROSTER_AGENTS) if f.endswith(".md")])
    roster_n = 0
    missing = []
    if os.path.isfile(ROSTER):
        try:
            d = json.load(open(ROSTER, encoding="utf-8"))
            roster_n = len(d) if isinstance(d, list) else 0
            nums = set()
            for x in d:
                m = re.search(r"(\d+)$", str(x.get("slug", "")))
                if m:
                    nums.add(int(m.group(1)))
            # 對照 SKILL.md 聲稱嘅 57 個
            missing = [i for i in range(1, 58) if i not in nums]
        except Exception:
            pass
    note = f"，缺編號 {missing}" if missing else ""
    return {
        "state": "ok",
        "detail": f"agents/ {n} 個 agent 檔，roster.json {roster_n} 條{note}",
        "claim": "grok-bot-roster 係本地 plugin（agent 索引），本身無積分可領。"
                 "背後模型經 OpenRouter 走 → 額度睇 OpenRouter。"
                 "xAI 官方 API 文件頁無免費層／無新戶贈金明文",
        "manual": False,
    }


# ---------------------------------------------------------------- 報告

CHECKS = [
    ("WorkBuddy",    check_workbuddy),
    ("OpenRouter",   check_openrouter),
    ("Kimi",         check_kimi),
    ("豆包（火山方舟）", check_doubao),
    ("MiniMax",      check_minimax),
    ("Cursor",       check_cursor),
    ("Qwen Code",    check_qwen),
    ("Grok Bot",     check_grokbot),
]

ICON = {"ok": "✅", "warn": "⚠️", "no-cred": "🔑", "no-free-tier": "➖",
        "error": "❌"}


def main():
    hr("多平台免費額度巡檢 " + time.strftime("%Y-%m-%d %H:%M"))
    results = []
    for name, fn in CHECKS:
        try:
            r = fn()
        except Exception as e:
            r = {"state": "error", "detail": f"檢查腳本異常：{str(e)[:80]}"}
        results.append((name, r))

    for name, r in results:
        print(f"\n{ICON.get(r['state'], '·')} {name}")
        print(f"    狀態：{r.get('detail', '')}")
        if r.get("claim"):
            for i, line in enumerate(wrap(r["claim"], 62)):
                print(f"    {'領取：' if i == 0 else '      '}{line}")
        if r.get("url"):
            print(f"    入口：{r['url']}")
        if r.get("manual"):
            print(f"    ⚠️  需要手動（無 API 可自動領取）")

    hr("統計")
    auto = sum(1 for _, r in results if r["state"] == "ok" and not r.get("manual"))
    manual = sum(1 for _, r in results if r.get("manual"))
    nokey = sum(1 for _, r in results if r["state"] == "no-cred")
    free_none = sum(1 for _, r in results if r["state"] == "no-free-tier")
    print(f"  可自動查餘額：{auto} 個")
    print(f"  要手動領取　：{manual} 個")
    print(f"  未有憑證　　：{nokey} 個")
    print(f"  官方無免費層：{free_none} 個")
    print("\n  註：所有額度查詢都係唯讀。冇自動購買、冇自動領取、冇貼 key 落任何渠道。")


def wrap(text, n):
    """按長度粗略斷行（中英混排夠用）。"""
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


if __name__ == "__main__":
    main()
