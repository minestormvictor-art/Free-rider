#!/usr/bin/env python3
"""
install_free_providers.py — 接入「免 key 免費層」供應商到 WorkBuddy

背景（2026-10-20 實測，4 個 reference repo 審查後）
  * awesome-freellm-apis（目錄）/ freellmapi（自架 router）/ free-claude-code（router）
    / FreeToken（本地 GPU 引擎）→ 抽出 30+ 供應商
  * 逐一實測 42 個 base URL：只有 2 個**免 key 都真係通**
      - Kilo Code Gateway  https://api.kilo.ai/api/gateway
          官方明文：unauthenticated access for free models only，200 req/hr/IP
      - LLM7.io              https://api.llm7.io/v1
          官方明文：免費層 100,000 tokens/day、250 r/h、60 r/m、1 r/s
  * 其餘（Groq / Cerebras / Mistral / Cohere / HF / Gemini / NVIDIA NIM / Cloudflare …）
    全部要個別 API key → 本機無 key，唔可即時接入

接入路徑（重要）
  本機已裝 freellmapi（WorkBuddy gateway :3001 就係佢，277+ model）。
  freellmapi 內建 `kilo` provider（keyless: true），並原生支援 `no-key` sentinel。
  所以正確做法係寫 freellmapi declarative config（FREEAPI_CONFIG_PATH），
  而唔係 WorkBuddy models.json —— 後者強制 apiKey 非空（除非 loopback URL），
  而且 id 會撞（同一 model id 已由 OpenRouter 佔用）。

用法
  python install_free_providers.py            # 產生/更新 config（唔重啟 server）
  python install_free_providers.py --verify   # 經 WorkBuddy gateway 實測
  python install_free_providers.py --restart  # 重啟 freellmapi 令 config 生效
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)

FRELLA_DIR = os.path.expanduser("~/freellmapi")
CONFIG_PATH = os.path.join(FRELLA_DIR, "freellmapi-free-providers.json")
ENV_PATH = os.path.join(FRELLA_DIR, ".env")
GATEWAY = "http://127.0.0.1:3001"

# Kilo 免 key 實測通嘅 model（2026-10-20 實測：HTTP 200 + cost 0 + tools OK）
KILO_MODELS = [
    ("minimax/minimax-m3.1-flash:free",       "MiniMax M3.1 Flash (Kilo free, 1M, tools)", 1000000),
    ("nvidia/nemotron-3.5-lightning:free",    "Nemotron 3.5 Lightning (Kilo free, 1M, tools)", 1000000),
    ("cohere/north-mini-code:free",           "North Mini Code (Kilo free, 256K, tools)", 256000),
    ("nvidia/nemotron-3-super-120b-a12b:free", "Nemotron 3 Super (Kilo free, 1M, tools)", 1000000),
    ("nvidia/nemotron-3-ultra-550b-a55b:free", "Nemotron 3 Ultra (Kilo free, 1M, tools)", 1000000),
    ("liquid/lfm-2.5-2.6b:free",              "LFM 2.5 2.6B (Kilo free, 64K, tools)", 65536),
    ("poolside/laguna-s-2.1:free",            "Poolside Laguna S 2.1 (Kilo free, 262K, tools)", 262144),
    ("poolside/laguna-xs-2.1:free",           "Poolside Laguna XS 2.1 (Kilo free, 262K, tools)", 262144),
    ("dots-studio/dots-3-note-preview:free",  "Dots 3 Note Preview (Kilo free, 512K, tools)", 512000),
]

# LLM7：官方說要 key（dash.llm7.io），免 key 只係部分 model 嘅匿名旁路。
# 唔好喺 declarative config 加 llm7 key —— 該 platform 非 keyless，會被 skip。
LLM7_MODELS = [
    ("codestral-latest",           "Codestral Latest (LLM7 free)", 32000),
    ("mistral-Nemo-Instruct-2407", "Mistral Nemo 2407 (LLM7 free)", 128000),
    ("DeepSeek-V4-Flash-0731",     "DeepSeek V4 Flash (LLM7 free, 400K)", 400000),
]

UA = {"User-Agent": "WorkBuddy-ffa/1.0", "Content-Type": "application/json"}


def hr(t=""):
    line = "─" * 64
    print(f"\n{line}" if t else line)
    if t:
        print(f"  {t}")
        print(line)


def build_config():
    return {
        "keys": [
            {"platform": "kilo", "label": "Kilo Free (anonymous, keyless)",
             "enabled": True},
        ],
        "models": [
            {"platform": "kilo", "modelId": mid, "displayName": name,
             "contextWindow": ctx, "supportsTools": True}
            for mid, name, ctx in KILO_MODELS
        ] + [
            {"platform": "llm7", "modelId": mid, "displayName": name,
             "contextWindow": ctx}
            for mid, name, ctx in LLM7_MODELS
        ],
    }


def write_config():
    cfg = build_config()
    os.makedirs(FRELLA_DIR, exist_ok=True)
    if os.path.isfile(CONFIG_PATH):
        shutil_copy = os.path.join(
            FRELLA_DIR, f"freellmapi-free-providers.json.bak-{time.strftime('%Y%m%d-%H%M%S')}")
        with open(CONFIG_PATH, encoding="utf-8") as f:
            old = f.read()
        with open(shutil_copy, "w", encoding="utf-8") as f:
            f.write(old)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return cfg, os.path.basename(CONFIG_PATH) if not os.path.isfile(CONFIG_PATH) else None


def ensure_env():
    """確保 .env 有 FREEAPI_CONFIG_PATH。"""
    if not os.path.isfile(ENV_PATH):
        return False
    with open(ENV_PATH, encoding="utf-8") as f:
        t = f.read()
    if "FREEAPI_CONFIG_PATH" in t:
        return False
    with open(ENV_PATH, "a", encoding="utf-8") as f:
        f.write(
            "\n# 免費層供應商（Kilo / LLM7 匿名免費層，2026-10-20）\n"
            f"FREEAPI_CONFIG_PATH={CONFIG_PATH}\n"
        )
    return True


def gateway_key():
    p = os.path.expanduser("~/.dsh/.credentials.yaml")
    if not os.path.isfile(p):
        return None
    t = open(p, encoding="utf-8").read()
    m = re.search(r"^\s*WORKBUDDY_API_KEY\s*:\s*(.+)$", t, re.M)
    return m.group(1).strip().strip('"').strip("'") if m else None


def gw(path, body=None, timeout=120):
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


def verify():
    """經 WorkBuddy gateway 實測各 model。"""
    st, body = gw("/v1/models")
    if st != 200:
        return None, body
    items = json.loads(body).get("data", [])
    by_id = {m.get("id"): m for m in items}
    return by_id, None


def chat(model_id, tools=False, mt=150):
    TOOLS = [{"type": "function", "function": {
        "name": "lookup", "description": "Look up a contract clause",
        "parameters": {"type": "object",
                       "properties": {"clause": {"type": "string"}},
                       "required": ["clause"]}}}] if tools else None
    p = {"model": model_id,
         "messages": [{"role": "user",
                       "content": "Look up clause 13 of the contract."}],
         "max_tokens": mt}
    if TOOLS:
        p["tools"] = TOOLS
        p["tool_choice"] = "auto"
    st, body = gw("/v1/chat/completions", p)
    if st != 200:
        return "HTTP%s %s" % (st, body[:90].replace("\n", " "))
    try:
        d = json.loads(body)
        ch = (d.get("choices") or [None])[0]
        if ch is None:
            return "no-choices"
        m2 = ch.get("message") or {}
        c = m2.get("content")
        if c is None:
            c = "(reasoning) " + str(m2.get("reasoning") or "")[:24]
        u = d.get("usage") or {}
        return "OK tools=%s cost=%s %r" % (
            "Y" if m2.get("tool_calls") else "n", u.get("cost"), str(c)[:28])
    except Exception as e:
        return "parse err %s" % e


def main():
    ap = argparse.ArgumentParser(description="接入免 key 免費層供應商到 WorkBuddy")
    ap.add_argument("--verify", action="store_true", help="經 gateway 實測")
    ap.add_argument("--restart", action="store_true", help="重啟 freellmapi 令 config 生效")
    args = ap.parse_args()

    hr("免 key 免費層接入（經 freellmapi gateway）")
    if not os.path.isdir(FRELLA_DIR):
        print(f"  ❌ 搵唔到 freellmapi：{FRELLA_DIR}")
        print("     WorkBuddy gateway :3001 就係 freellmapi，缺咗佢就接唔到。")
        return

    cfg, _ = write_config()
    env_changed = ensure_env()
    print(f"  config：{CONFIG_PATH}")
    print(f"  keys   ：{len(cfg['keys'])}（kilo keyless）")
    print(f"  models ：{len(cfg['models'])}")
    print(f"  .env   ：{'已加 FREEAPI_CONFIG_PATH' if env_changed else '已有 FREEAPI_CONFIG_PATH'}")

    if args.restart:
        hr("重啟 freellmapi")
        script = os.path.join(FRELLA_DIR, "start-freellmapi.ps1")
        if os.path.isfile(script):
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                            "-File", script], capture_output=True, text=True, timeout=90)
            time.sleep(9)
            st, _b = gw("/v1/models")
            print(f"  gateway /v1/models → {'✅ 通' if st == 200 else '❌ ' + str(st)}")
        else:
            print(f"  ⚠ 搵唔到 {script}，請手動重啟 freellmapi")

    if args.verify:
        hr("經 WorkBuddy gateway 實測")
        by_id, err = verify()
        if by_id is None:
            print(f"  ❌ {err}")
            return
        print(f"  gateway catalog：{len(by_id)} 個 model")
        print()
        # 用 freellmapi 顯示嘅短 id 去測
        for mid, name, ctx in KILO_MODELS:
            short = mid.split("/")[-1].replace(":free", "")
            for cand in (short, mid):
                m = by_id.get(cand)
                if m:
                    break
            else:
                print("  %-44s ❌ catalog 冇呢個 model" % (mid,))
                continue
            status = m.get("execution_status")
            res = chat(m.get("id"), tools=True)
            print("  %-44s [%s] %s" % (mid, status, res))
        # 順帶列出 gateway 上其他 ready 嘅免費 model（用戶可直接用）
        ready = [m.get("id") for m in by_id.values()
                 if m.get("execution_status") == "ready"]
        if ready:
            hr("gateway 上 execution_status=ready 嘅 model（共 %d 個）" % len(ready))
            for r in sorted(ready):
                m = by_id[r]
                print("  %-38s ctx=%-9s" % (r, m.get("context_window")))


if __name__ == "__main__":
    main()
