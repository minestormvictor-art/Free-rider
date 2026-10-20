#!/usr/bin/env python3
"""
build_directory.py — 由 awesome-freellm-apis README 抽出機器可讀嘅免費 API 目錄。

用法:
    python build_directory.py [--zip "E:/Skill hub/awesome-freellm-apis-main.zip"] [--out providers.json]

輸出:
    providers.json  { "generated_at": "...", "source": "...", "providers": [...] }

每個 provider 記錄:
    name, base_url, key_url, credit_card, free_models, max_context, modalities,
    tier ("permanent" | "renewable"), credit_model, best_models[{model_id, ctx, rate_limit}]

設計原則:
    - 只抽 README 內明確寫出嘅嘢,唔會生成 endpoint 或 model id
    - 離線可用,無網絡依賴
    - 唔會讀取或寫入任何 API key
"""
from __future__ import annotations

import argparse
import datetime as _dt
import html
import json
import re
import sys
import zipfile
from pathlib import Path

DEFAULT_ZIP = Path("E:/Skill hub/awesome-freellm-apis-main.zip")
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "references" / "providers.json"

BLOCKS = {
    "permanent": ("BEGIN_PERMANENT_FREE", "END_PERMANENT_FREE"),
    "renewable": ("BEGIN_RENEWABLE", "END_RENEWABLE"),
}


def _clean(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<a\b[^>]*>(.*?)</a>", r"\1", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip().strip("`").strip()


def _href(cell: str) -> str:
    m = re.search(r'href="([^"]+)"', cell or "")
    return html.unescape(m.group(1)) if m else ""


def _rows(table_md: str) -> list[list[str]]:
    rows = []
    for line in table_md.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells:
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        if cells[0].lower() == "provider":
            continue
        # 保留 provider 留空嘅續行（用於合併 best_models）
        rows.append(cells)
    return rows


def _section(md: str, start: str, end: str) -> str:
    i = md.find(start)
    j = md.find(end)
    if i == -1 or j == -1 or j < i:
        return ""
    return md[i + len(start): j]


def _merge_continuation(rows: list[list[str]]) -> list[dict]:
    """合併表格中『上一行 provider 留空』嘅續行。"""
    out: list[dict] = []
    for cells in rows:
        provider = _clean(cells[0])
        if not provider and out:
            out[-1]["best_models"].append(
                {
                    "model_id": _clean(cells[2]) if len(cells) > 2 else "",
                    "ctx": _clean(cells[3]) if len(cells) > 3 else "",
                    "rate_limit": _clean(cells[4]) if len(cells) > 4 else "",
                }
            )
            continue
        out.append(
            {
                "provider": provider,
                "best_models": [
                    {
                        "model_id": _clean(cells[2]) if len(cells) > 2 else "",
                        "ctx": _clean(cells[3]) if len(cells) > 3 else "",
                        "rate_limit": _clean(cells[4]) if len(cells) > 4 else "",
                    }
                ],
            }
        )
    return out


def extract(md: str) -> dict:
    providers: dict[str, dict] = {}

    for tier, (b, e) in BLOCKS.items():
        for cells in _rows(_section(md, b, e)):
            name = _clean(cells[0])
            if not name:
                continue
            rec = providers.setdefault(
                name,
                {
                    "name": name,
                    "tier": tier,
                    "base_url": "",
                    "key_url": "",
                    "credit_card": "",
                    "free_models": 0,
                    "max_context": "",
                    "modalities": [],
                    "credit_model": "",
                    "best_models": [],
                },
            )
            if tier == "renewable" and len(cells) > 2:
                rec["credit_model"] = _clean(cells[2])
            if len(cells) > 1:
                rec["free_models"] = int(re.sub(r"\D", "", _clean(cells[1])) or 0)
            if len(cells) > 3:
                rec["max_context"] = _clean(cells[3])
            if len(cells) > 4:
                mods = _clean(cells[4])
                if mods:
                    rec["modalities"] = [m.strip() for m in mods.split(",") if m.strip()]
            if len(cells) > 5:
                rec["key_url"] = _href(cells[5])

    for cells in _rows(_section(md, "BEGIN_QUICK_REF", "END_QUICK_REF")):
        name = _clean(cells[0])
        if not name:
            continue
        rec = providers.setdefault(
            name,
            {
                "name": name,
                "tier": "unknown",
                "base_url": "",
                "key_url": "",
                "credit_card": "",
                "free_models": 0,
                "max_context": "",
                "modalities": [],
                "credit_model": "",
                "best_models": [],
            },
        )
        if len(cells) > 1:
            rec["base_url"] = _clean(cells[1]).strip("`")
        if len(cells) > 2:
            rec["key_url"] = _href(cells[2]) or _clean(cells[2])
        if len(cells) > 3:
            rec["credit_card"] = _clean(cells[3])

    best = {m["provider"]: m["best_models"] for m in _merge_continuation(
        _rows(_section(md, "BEGIN_BEST_MODELS", "END_BEST_MODELS"))
    )}
    for name, models in best.items():
        if name in providers:
            providers[name]["best_models"] = models
        else:
            providers[name] = {
                "name": name,
                "tier": "unknown",
                "base_url": "",
                "key_url": "",
                "credit_card": "",
                "free_models": 0,
                "max_context": "",
                "modalities": [],
                "credit_model": "",
                "best_models": models,
            }

    return {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "source": "awesome-freellm-apis (README 內嵌表格，每日刷新)",
        "provider_count": len(providers),
        "providers": sorted(providers.values(), key=lambda p: p["name"].lower()),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="抽 awesome-freellm-apis 目錄成 JSON")
    ap.add_argument("--zip", default=str(DEFAULT_ZIP))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    zp = Path(args.zip)
    if not zp.exists():
        print(f"[!] 搵唔到 zip: {zp}", file=sys.stderr)
        return 1

    with zipfile.ZipFile(zp) as z:
        names = [n for n in z.namelist() if n.endswith("README.md") and "/" in n]
        if not names:
            print("[!] zip 入面搵唔到 README.md", file=sys.stderr)
            return 1
        md = z.read(sorted(names, key=len)[0]).decode("utf-8", "ignore")

    data = extract(md)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] {data['provider_count']} 個 provider → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
