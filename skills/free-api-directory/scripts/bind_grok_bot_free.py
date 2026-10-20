#!/usr/bin/env python3
"""
bind_grok_bot_free.py — 將 Grok Bot roster 43 個 agent 綁去免費模型通道。

WorkBuddy agent frontmatter 支援嘅欄位（2026-10-20 實測 WorkBuddy asar）：
    name / description / displayName / profession / maxTurns / skills
    ❌ 無 `model:` 欄位 —— agent 用邊個模型係 WorkBuddy UI 層決定，
       唔可以喺 plugin 檔案硬綁。

所以「Token 自由」喺 Grok Bot 側要咁做：
  1. agent frontmatter `skills` 加 `free-api-directory`
     → agent 執行時自動載入免費 API 目錄 + 查詢腳本，
       知道邊啲模型免費、base URL 幾多、邊啲要信用卡
  2. agent 正文「技術基礎」段落改用**免費層模型 id**
     → 呢段係 agent 真正會讀嘅上下文，令佢唔好叫用戶用付費模型
  3. 免費層模型 id 寫成 gateway 短 id（經 freellmapi），
     WorkBuddy models.json 已經有對應條目（cost=0）

用法：
    python bind_grok_bot_free.py --check     # 睇現況
    python bind_grok_bot_free.py --apply     # 改檔（自動備份）
    python bind_grok_bot_free.py --apply --restore-from <backup_dir>
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

ROSTER = Path.home() / ".workbuddy" / "plugins" / "marketplaces" / "my-experts" / "plugins" / "grok-bot-roster"
AGENTS_DIR = ROSTER / "agents"

# 經 freellmapi gateway 嘅免費模型短 id（models.json 已有，實測 cost=0）
FREE_MODELS_GATEWAY = [
    ("minimax-m3.1-flash", "1M", "唯一 auto 模式主動發 tool_call 嘅免費 model"),
    ("nemotron-3.5-lightning", "1M", "NVIDIA Nemotron 3.5 Lightning"),
    ("nemotron-3-ultra", "1M", "NVIDIA Nemotron 3 Ultra 550B"),
    ("north-mini-code", "256K", "code 專用"),
    ("lfm-2.5-2.6b", "64K", "最穩，支援 function calling"),
    ("free-router", "200K", "自動路由免費層"),
]

# 免費層 OpenRouter id（直連，有 50 req/day 帳戶級上限）
FREE_MODELS_OPENROUTER = [
    ("minimax/minimax-m3.1-flash:free", "1M"),
    ("nvidia/nemotron-3-ultra-550b-a55b:free", "1M"),
    ("nvidia/nemotron-3.5-lightning:free", "1M"),
    ("cohere/north-mini-code:free", "256K"),
    ("liquid/lfm-2.5-2.6b:free", "64K"),
]

TECH_BLOCK_RE = re.compile(
    r"(## 技術基礎[ \t]*\n)(.*?)(?=\n---|\Z)", re.S
)


def build_tech_block() -> str:
    """技術基礎段落內容（**唔包含** '## 技術基礎' 標題，由呼叫端決定）。"""
    gw = "\n".join(
        f"  - `{mid}`（{ctx}）— {note}" for mid, ctx, note in FREE_MODELS_GATEWAY
    )
    orr = "\n".join(f"  - `{mid}`（{ctx}）" for mid, ctx in FREE_MODELS_OPENROUTER)
    return f"""本 agent 由 Grok Bot roster 移植而來。**只用免費層模型，唔好建議用戶轉付費。**

### 免費通道 A · 本機 freellmapi gateway（推薦，無每日上限）

- **Base URL**：`http://127.0.0.1:3001/v1`（本機 gateway，轉發去 Kilo 免 key 層）
- **key 來源**：`~/freellmapi/server/data/freeapi.db` → `settings.unified_api_key`
  （WorkBuddy `models.json` 已有對應條目，直接揀 model 就得，唔使手動配 key）
- **實測狀態**：11/17 模型 HTTP 200、`cost=0`、支援 function calling

可用免費模型：
{gw}

### 免費通道 B · OpenRouter 免費層

- **Base URL**：`https://openrouter.ai/api/v1`
- **額度**：**50 req/day（全帳戶共用，唔係每個 model 各計）** —— 唔好大量 probe，會燒光配額
- **判定 429 屬邊個嘅問題**：淨係個別 model 429 = provider 過載；多個 :free model 同時 429 = 每日 counter 用完

{orr}

### 查目錄（唔使上網）

`free-api-directory` skill 內置 30 個免費 provider 目錄：

```bash
cd scripts
python query_directory.py --list           # 全部 30 個 provider
python query_directory.py --no-card        # 只要唔使信用卡（10 個）
python query_directory.py --provider groq  # base URL / 申請入口 / 代表模型
```

### 紅線

- 唔建議付費模型，唔好叫用戶「升級去付費 tier」
- 唔喺 chat 或其他渠道貼 key
- 目錄係候選池，未實測唔好講「通」—— 用 `free-for-all` skill 嘅 `doctor.py` 驗
"""


def process_agent(path: Path) -> tuple[bool, str]:
    text = path.read_text(encoding="utf-8")
    orig = text

    # 1. frontmatter skills 加 free-api-directory
    #    必須插喺 YAML 陣列「括號裡面」：
    #      skills: [a]        -> skills: [a, free-api-directory]
    #      skills: [a, b]     -> skills: [a, b, free-api-directory]
    #    唔可以寫成 skills: [a], free-api-directory（括號外逗號 = YAML 語法錯）
    def fix_skills(m: re.Match) -> str:
        line = m.group(0).rstrip()
        if "free-api-directory" in line:
            return line
        m2 = re.match(r"^(skills:\s*\[)(.*?)(\])", line)
        if not m2:
            # 唔係陣列格式 → 照原樣 append（極少見情況）
            return line + ",free-api-directory"
        head, body, tail = m2.group(1), m2.group(2).strip(), m2.group(3)
        if not body:
            return f"{head} free-api-directory{tail}"
        return f"{head}{body}, free-api-directory{tail}"

    text = re.sub(r"^skills:.*$", fix_skills, text, count=1, flags=re.M)

    # 2. 技術基礎段落換成免費版本
    #    TECH_BLOCK_RE 已包含 "## 技術基礎" 標題，所以 build_tech_block 要唔含標題
    if TECH_BLOCK_RE.search(text):
        text = TECH_BLOCK_RE.sub(
            lambda m: m.group(1) + "\n" + build_tech_block() + "\n", text, count=1
        )
    else:
        # 冇技術基礎段落 → 喺最後一個 --- 之後加
        idx = text.rfind("\n---")
        block = "\n" + build_tech_block() + "\n"
        if idx == -1:
            text = text.rstrip() + "\n" + block
        else:
            text = text[:idx] + "\n" + block + text[idx:]

    if text == orig:
        return False, "無變化"
    path.write_text(text, encoding="utf-8")
    return True, "已更新"


def main() -> int:
    ap = argparse.ArgumentParser(description="將 Grok Bot agents 綁去免費模型")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--restore-from", help="由備份目錄還原")
    args = ap.parse_args()

    if not args.check and not args.apply and not args.restore_from:
        ap.error("要 --check、--apply 或者 --restore-from")

    if args.restore_from:
        src = Path(args.restore_from)
        if not src.is_dir():
            print(f"[!] 搵唔到備份目錄 {src}")
            return 1
        n = 0
        for f in src.glob("*.md"):
            shutil.copy2(f, AGENTS_DIR / f.name)
            n += 1
        print(f"[OK] 由 {src} 還原 {n} 個 agent")
        return 0

    files = sorted(AGENTS_DIR.glob("*.md"))
    print(f"Grok Bot agents: {len(files)} 個\n")

    if args.check:
        with_dir, with_free, old_block = 0, 0, 0
        for f in files:
            t = f.read_text(encoding="utf-8")
            sk = re.search(r"^skills:.*$", t, re.M)
            has_free = sk and "free-api-directory" in sk.group(0)
            block = TECH_BLOCK_RE.search(t)
            is_old = bool(block) and "只限 OpenRouter" in block.group(0)
            if has_free:
                with_free += 1
            if block:
                with_dir += 1
            if is_old:
                old_block += 1
            flag = "OK " if has_free and not is_old else "-> "
            print(f"  {flag}{f.name}")
        print(f"\n已掛 free-api-directory : {with_free}/{len(files)}")
        print(f"有技術基礎段落         : {with_dir}/{len(files)}")
        print(f"仍然係舊（付費導向）段落: {old_block}/{len(files)}")
        return 0

    # apply
    import datetime as dt

    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = ROSTER / f"_backup_agents_{ts}"
    bak.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copy2(f, bak / f.name)
    print(f"[OK] 備份 → {bak}")

    changed = 0
    for f in files:
        ok, msg = process_agent(f)
        if ok:
            changed += 1
    print(f"[OK] 已更新 {changed}/{len(files)} 個 agent")
    print("\n下一步：重啟 WorkBuddy（或重載 plugin），agent 就會用免費層模型")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
