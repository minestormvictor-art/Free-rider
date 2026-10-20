#!/usr/bin/env python3
"""
query_directory.py — 查詢 awesome-freellm-apis 免費 API 目錄。

用法:
    python query_directory.py --list                     # 列出全部 provider
    python query_directory.py --no-card                  # 只要唔使信用卡嘅
    python query_directory.py --provider groq            # 睇單一 provider 詳情
    python query_directory.py --search nemotron          # 搜 model id / provider 名
    python query_directory.py --modality code            # 按模態篩
    python query_directory.py --json                     # 輸出 JSON

離線查目錄,唔會發任何網絡請求,唔會讀 key。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_JSON = Path(__file__).resolve().parent.parent / "references" / "providers.json"


def load(path: Path) -> dict:
    if not path.exists():
        print(f"[!] 搵唔到目錄檔: {path}\n    行 build_directory.py 先。", file=sys.stderr)
        raise SystemExit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def fmt_provider(p: dict, detail: bool = False) -> str:
    tag = {"permanent": "永久免費", "renewable": "可續期", "unknown": "未分類"}[p["tier"]]
    lines = [
        f"■ {p['name']}  [{tag}]  免費模型 {p['free_models']}  最大 ctx {p['max_context'] or '?'}",
        f"  base URL : {p['base_url'] or '(官方直接用,無獨立 base)'}",
        f"  申請 key : {p['key_url'] or '(無)'}",
        f"  信用卡   : {p['credit_card'] or '?'}",
    ]
    if p.get("credit_model"):
        lines.append(f"  credit   : {p['credit_model']}")
    if p.get("modalities"):
        lines.append(f"  模態     : {', '.join(p['modalities'])}")
    if detail and p["best_models"]:
        lines.append("  代表模型 :")
        for m in p["best_models"]:
            lines.append(
                f"    - {m['model_id']}  ctx={m['ctx'] or '?'}  limit={m['rate_limit'] or '?'}"
            )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="查詢免費 API 目錄")
    ap.add_argument("--db", default=str(DEFAULT_JSON))
    ap.add_argument("--list", action="store_true", help="列出全部 provider")
    ap.add_argument("--no-card", action="store_true", help="只顯示唔使信用卡")
    ap.add_argument("--provider", help="provider 名（部分匹配）")
    ap.add_argument("--search", help="搜 provider 名或 model id")
    ap.add_argument("--modality", help="按模態篩，例如 code / reasoning / vision")
    ap.add_argument("--json", action="store_true", help="輸出 JSON")
    args = ap.parse_args()

    data = load(Path(args.db))
    ps = data["providers"]
    hits = ps
    filtered = False

    if args.provider:
        hits = [p for p in ps if args.provider.lower() in p["name"].lower()]
        filtered = True
        if not hits:
            print(f"[!] 搵唔到 provider: {args.provider}", file=sys.stderr)
            return 1
    elif args.search:
        q = args.search.lower()
        hits = [
            p
            for p in ps
            if q in p["name"].lower()
            or any(q in m["model_id"].lower() for m in p["best_models"])
        ]
        filtered = True
    elif args.no_card:
        hits = [p for p in ps if p["credit_card"].strip().lower() in ("no", "none", "")]
        filtered = True
    elif args.modality:
        q = args.modality.lower()
        hits = [p for p in ps if any(q in m.lower() for m in p["modalities"])]
        filtered = True

    if args.json:
        payload = {
            "generated_at": data["generated_at"],
            "source": data["source"],
            "provider_count": len(hits),
            "providers": hits,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if not filtered:
        print("\n".join(
            f"{p['name']:<32} {p['tier']:<10} free={p['free_models']:<4} "
            f"card={p['credit_card']:<20} {p['base_url']}"
            for p in hits
        ))
        return 0

    print("\n\n".join(fmt_provider(p, detail=True) for p in hits) or "(冇結果)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
