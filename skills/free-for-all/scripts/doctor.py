#!/usr/bin/env python3
"""
doctor.py — 三邊模型健康檢查

同時做兩件事：
  1. 靜態：讀三邊設定檔，列出模型清單並比對差異
  2. 動態：對每個模型打真 API，驗證 key × model 配對是否真係通

不修改任何檔案。安全讀取。
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from install import (  # noqa: E402
    WB_PATH, DSH_PATH, QWEN_PATH,
    check_key, check_model, read_state, resolve_key, hr,
)

# 各工具「主模型」取清單第一個
PRIMARY = {"WorkBuddy": None, "DSH": None, "Qwen Code": None}


def collect_targets(state):
    """由三邊設定抽出所有 model id（去重，保留順序）。"""
    out = []
    for tool, ids in state.items():
        if not isinstance(ids, list):
            continue
        for i in ids:
            if i and "/" in i and i not in out and "<" not in i:
                out.append(i)
    return out


def main():
    hr("靜態檢查：三邊設定檔")
    st = read_state()
    for tool, ids in st.items():
        label = {"workbuddy": "WorkBuddy", "dsh": "DSH", "qwen": "Qwen Code"}[tool]
        path = {"workbuddy": WB_PATH, "dsh": DSH_PATH, "qwen": QWEN_PATH}[tool]
        exists = os.path.isfile(path)
        n = len(ids) if isinstance(ids, list) else 0
        print(f"\n  {label:12} {'✅' if exists else '❌ 檔案不存在'}  {n} 個")
        for i in (ids if isinstance(ids, list) else ["-"]):
            print(f"    • {i}")

    # --- 重啟判斷 ---
    hr("重啟判斷")
    for label, path in [("WorkBuddy", WB_PATH), ("DSH", DSH_PATH)]:
        if os.path.isfile(path):
            m = time.strftime("%H:%M:%S", time.localtime(os.path.getmtime(path)))
            print(f"  {label:12} 設定檔最後修改 {m}")
    print("  → 若設定檔修改時間 晚於 進程啟動時間 = 已生效，唔使重啟")
    print("  → WorkBuddy: 用工作管理員檢查；DSH: 用任務管理員檢查")

    # --- key 檢查 ---
    hr("API key 檢查")
    try:
        key = resolve_key()
    except SystemExit as e:
        print(f"  ❌ {e}")
        return
    k = check_key(key)
    if k["ok"]:
        free = "免費層" if k["free"] else "付費層"
        extra = f"，剩餘 {k['remaining']}/{k['limit']}" if k.get("limit") else ""
        print(f"  ✅ key 有效（{free}{extra}，已用 {k.get('usage')}）")
    else:
        print(f"  ❌ key 無效：{k['reason']}")
        return

    # --- 模型實測 ---
    targets = collect_targets(st)
    if not targets:
        print("\n  （冇 model 可測）")
        return

    hr(f"模型實測（共 {len(targets)} 個）")
    results = {}
    for m in targets:
        r = check_model(key, m)
        results[m] = r
        if r["ok"]:
            print(f"  ✅ {m:36} ${r['cost']:.6f}  {r['reply']!r}")
        else:
            code = r["code"]
            hint = {
                401: "key 失效",
                403: "model 限特殊場合",
                404: "model 名錯 / 無免費版",
                400: "model 類型錯（embedding/TTS）",
                429: "provider 過載（唔關你事）",
            }.get(code, "")
            print(f"  ❌ {m:36} [{code}] {hint}")

    # --- 總結 ---
    hr("總結")
    ok = [m for m, r in results.items() if r["ok"]]
    bad = [m for m, r in results.items() if not r["ok"]]
    print(f"  ✅ 可用 {len(ok)} 個 / 共 {len(results)} 個")
    if bad:
        print(f"  ❌ 不可用 {len(bad)} 個：")
        for m in bad:
            print(f"       {m}  → {results[m]['code']}")
        if all(results[m]["code"] == 429 for m in bad):
            print("\n  💡 全部 429 = provider 側過載，等陣再試。key 本身有效。")
    if ok:
        print(f"\n  建議預設：{ok[0]}")


if __name__ == "__main__":
    main()