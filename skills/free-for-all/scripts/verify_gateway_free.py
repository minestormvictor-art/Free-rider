import json, os, re, urllib.request, urllib.error, time

t = open(os.path.expanduser("~/.dsh/.credentials.yaml"), encoding="utf-8").read()
k = re.search(r"^\s*WORKBUDDY_API_KEY\s*:\s*(.+)$", t, re.M).group(1).strip()
BASE = "http://127.0.0.1:3001"
TOOLS = [{"type": "function", "function": {
    "name": "lookup", "description": "Look up a contract clause",
    "parameters": {"type": "object",
                   "properties": {"clause": {"type": "string"}},
                   "required": ["clause"]}}}]


def gw(path, body=None, timeout=120):
    h = {"Content-Type": "application/json", "Authorization": "Bearer " + k}
    d = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=d, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")
    except Exception as e:
        return None, str(e)[:100]


def chat(mid, tools=False, mt=140):
    p = {"model": mid,
         "messages": [{"role": "user",
                       "content": "Look up clause 13 of the contract."}],
         "max_tokens": mt}
    if tools:
        p["tools"] = TOOLS
        p["tool_choice"] = "auto"
    st, body = gw("/v1/chat/completions", p)
    if st != 200:
        return None, "HTTP%s %s" % (st, body[:80].replace("\n", " "))
    try:
        d = json.loads(body)
        ch = (d.get("choices") or [None])[0]
        if ch is None:
            return None, "no-choices"
        m2 = ch.get("message") or {}
        u = d.get("usage") or {}
        return {"tc": bool(m2.get("tool_calls")), "cost": u.get("cost"),
                "pt": u.get("prompt_tokens"), "ct": u.get("completion_tokens")}, None
    except Exception as e:
        return None, "parse %s" % e


st, body = gw("/v1/models")
items = json.loads(body).get("data", [])
ready = [m for m in items if m.get("execution_status") == "ready"]

print("=== 全部 %d 個 ready model 實測（tools + 成本）===" % len(ready))
print("%-38s %-8s %-8s %-6s %s" % ("model", "HTTP", "cost", "tools", "tokens"))
ok = 0
for m in sorted(ready, key=lambda x: x.get("id", "")):
    mid = m.get("id")
    r, err = chat(mid, tools=True)
    if r is None:
        print("%-38s %-8s %s" % (mid, "FAIL", err))
    else:
        ok += 1
        print("%-38s %-8s %-8s %-6s %s→%s" % (
            mid, "200", r["cost"], "Y" if r["tc"] else "n", r["pt"], r["ct"]))
    time.sleep(0.6)

print()
print(f"✅ 實測通 {ok}/{len(ready)}")
