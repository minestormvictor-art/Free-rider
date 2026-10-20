#!/usr/bin/env python3
"""
probe_providers.py — 跨供應商免費層探測（一次性工具）

用途：由 4 個 reference repo 抽出的 30 個供應商，逐一實測：
  1. base URL 係咪通（TLS + 路徑存在）
  2. 用現有 OpenRouter key 會唔會被接受（部分供應商共用 OpenRouter 聚合）
  3. 免註冊供應商（無 key）會唔會直接俾用

安全：key 只喺記憶體，唔會印出、唔會落命令行。
"""
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)
from install import resolve_key  # noqa: E402

# 由 4 個 repo 抽出：provider -> (base_url, 免費 model id 候選)
PROVIDERS = [
    ("OpenRouter",        "https://openrouter.ai/api/v1",            ["nvidia/nemotron-3-ultra-550b-a55b:free"]),
    ("Groq",              "https://api.groq.com/openai/v1",         ["llama-3.3-70b-versatile"]),
    ("Cerebras",          "https://api.cerebras.ai/v1",             ["llama-3.3-70b"]),
    ("Mistral",           "https://api.mistral.ai/v1",              ["open-mistral-7b"]),
    ("Cohere",            "https://api.cohere.com/compatibility/v1", ["command-r7b-12-2024"]),
    ("HuggingFace",       "https://router.huggingface.co/v1",       ["deepseek-ai/DeepSeek-V3-0324"]),
    ("Google Gemini",     "https://generativelanguage.googleapis.com/v1beta/openai", ["gemini-2.5-flash"]),
    ("NVIDIA NIM",        "https://integrate.api.nvidia.com/v1",    ["meta/llama-3.3-70b-instruct"]),
    ("Cloudflare",        "https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/v1", ["@cf/meta/llama-3.3-70b-instruct-fp8-fast"]),
    ("SiliconFlow",       "https://api.siliconflow.cn/v1",          ["Qwen/Qwen2.5-7B-Instruct"]),
    ("ModelScope",        "https://api-inference.modelscope.cn/v1",  ["Qwen/Qwen2.5-7B-Instruct"]),
    ("Z AI",              "https://open.bigmodel.cn/api/paas/v4",   ["glm-4-flash"]),
    ("xAI",               "https://api.x.ai/v1",                    ["grok-4-7"]),
    ("DeepSeek",          "https://api.deepseek.com/v1",            ["deepseek-chat"]),
    ("Kilo Code",         "https://api.kilo.ai/api/gateway",        ["nvidia/nemotron-3-ultra-550b-a55b:free"]),
    ("LLM7.io",           "https://api.llm7.io/v1",                 ["gpt-oss-20b"]),
    ("OpenCode Zen",      "https://opencode.ai/zen/v1",             ["big-pickle"]),
    ("Chutes.ai",         "https://api.chutes.ai/v1",               ["chutesai/mistral-3-8b"]),
    ("OVHcloud",          "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1", ["meta-llama-3_3-70b-instruct"]),
    ("SambaNova",         "https://api.sambanova.ai/v1",            ["Meta-Llama-3.3-70B-Instruct"]),
    ("Nebius",            "https://api.studio.nebius.com/v1",       ["meta-llama-3.1-70b-instruct"]),
    ("Nscale",            "https://inference.api.nscale.com/v1",    ["meta-llama-3.1-70b-instruct"]),
    ("Cline",             "https://api.cline.bot/api/v1",           ["cline/free"]),
    ("Glhf.chat",         "https://glhf.chat/api/openai/v1",        ["hf:gpt-oss-120b"]),
    ("Agnes AI",          "https://apihub.agnes-ai.com/v1",         ["openai/gpt-oss-120b"]),
    ("Aion Labs",         "https://api.aionlabs.ai/v1",             ["aion-1-large"]),
    ("Featherless",       "https://api.featherless.ai/v1",          ["meta-llama-3.3-70b-instruct"]),
    ("Fireworks",         "https://api.fireworks.ai/inference/v1",  ["accounts/fireworks/models/llama-v3p3-70b-instruct"]),
    ("DeepInfra",         "https://api.deepinfra.com/v1/openai",   ["meta-llama/Meta-Llama-3.3-70B-Instruct"]),
    ("WandB",             "https://api.inference.wandb.ai/v1",      ["meta-llama-3.1-70b-instruct"]),
    ("Moonshot",          "https://api.moonshot.ai/v1",             ["kimi-k2-0905-preview"]),
    ("MiniMax",           "https://api.minimax.io/v1",              ["MiniMax-M2.5"]),
    ("Vercel AI Gateway", "https://ai-gateway.vercel.sh/v1",        ["openai/gpt-oss-120b"]),
    ("Kimi Code",         "https://api.kimi.com/coding/v1",         ["kimi-for-coding"]),
    ("ZenMux",            "https://zenmux.ai/api/v1",               ["glm-4.6"]),
    ("Waver AI",          "https://api.waver.ai/v1",               ["gpt-oss-120b"]),
    ("Bynara",            "https://router.bynara.id/v1",            ["openai/gpt-oss-120b"]),
    ("TokenFactory",      "https://tokenfactory.nebius.com/v1",    ["meta-llama-3.1-70b-instruct"]),
    ("Ali Token Plan",    "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1", ["qwen3-coder-plus"]),
    ("Chutes Alt",        "https://api.cheaperinference.com/v1",    ["openai/gpt-oss-120b"]),
    ("Experimental",      "https://api.experientiallabs.ai/v1",     ["gpt-oss-120b"]),
    ("Novita",            "https://api.novita.ai/openai/v1",        ["meta-llama/llama-3.1-70b-instruct"]),
    ("SambaNova Alt",     "https://api.inference.wandb.ai/v1",      ["meta-llama-3.1-70b-instruct"]),
]

UA = {"User-Agent": "WorkBuddy-provider-probe/1.0",
      "Content-Type": "application/json"}


def probe_chat(base, model, key, timeout=25):
    """試 chat completions。回 (state, detail)。"""
    url = base.rstrip("/") + "/chat/completions"
    if "{ACCOUNT_ID}" in url:
        return ("need-param", "URL 需要 account_id")
    payload = {"model": model, "messages": [{"role": "user", "content": "OK"}],
               "max_tokens": 8}
    hdr = dict(UA)
    if key:
        hdr["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=hdr)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read())
            c = (d.get("choices") or [{}])[0].get("message", {}).get("content", "")
            return ("ok", f"200 回覆 {c[:20]!r}")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "ignore")[:150]
        except Exception:
            pass
        if e.code in (401, 403):
            return ("auth-needed", f"HTTP {e.code} {body}")
        if e.code == 404:
            return ("no-model", f"HTTP 404 {body}")
        if e.code == 429:
            return ("quota", f"HTTP 429 {body}")
        return ("http-%s" % e.code, body)
    except urllib.error.URLError as e:
        return ("unreachable", str(e.reason)[:60])
    except Exception as e:
        return ("error", str(e)[:60])


def main():
    or_key = resolve_key()
    print("=" * 78)
    print("跨供應商探測（用現有 OpenRouter key 試，key 唔會顯示）")
    print("=" * 78)
    print(f"{'provider':<20} {'base url':<46} {'state':<12} detail")
    print("-" * 78)

    results = []
    for name, base, models in PROVIDERS:
        model = models[0]
        st, detail = probe_chat(base, model, or_key)
        results.append((name, base, model, st, detail))
        print(f"{name:<20} {base[:44]:<46} {st:<12} {detail[:60]}")

    print()
    print("=" * 78)
    print("分類")
    print("=" * 78)
    buckets = {}
    for name, base, model, st, detail in results:
        buckets.setdefault(st, []).append((name, base, model))
    for st in ("ok", "auth-needed", "no-model", "quota", "unreachable",
               "need-param", "error"):
        items = buckets.get(st, [])
        if not items:
            continue
        print(f"\n[{st}] {len(items)} 個")
        for name, base, model in items:
            print(f"   • {name:<20} {base[:50]:<52} {model}")

    print()
    ok = buckets.get("ok", [])
    print(f"✅ 現有 key 即刻可用：{len(ok)} 個 → {[n for n,_,_ in ok]}")
    print(f"🔑 要個別 key　　　：{len(buckets.get('auth-needed', []))} 個")
    print(f"➖ 唔通/無 model　：{len(buckets.get('unreachable', []))} 個")


if __name__ == "__main__":
    main()
