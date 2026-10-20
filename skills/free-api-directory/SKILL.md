---
name: free-api-directory
description: "Offline queryable directory of 30 free/freemium LLM API providers (513+ free models) with exact base URLs, API key signup links, credit-card requirements, rate limits and best model IDs per provider. Use when the user asks which free AI API providers exist, wants a provider's base URL or key signup path, needs to compare free tiers by rate limit or context window, or wants to pick a no-credit-card provider. Also covers self-hosted free LLM routers (freellmapi gateway, free-claude-code) and local GPU inference (FreeToken). Derived from the awesome-freellm-apis directory (refreshed daily)."
---

# 免費 API 目錄（離線查詢）

30 個 provider、513+ 免費模型嘅**機器可讀目錄**。唔使上網就查得倒 base URL、申請入口、信用卡要求、rate limit 同代表 model id。

## 快速查

```bash
cd scripts

python query_directory.py --list                # 全部 30 個 provider 一覽
python query_directory.py --no-card             # 只要唔使信用卡（10 個）
python query_directory.py --provider groq       # 單一 provider 詳情 + 代表模型
python query_directory.py --search nemotron     # 搜 provider 名或 model id
python query_directory.py --modality code       # 按模態篩（code/reasoning/vision/…）
python query_directory.py --provider kilo --json # JSON 輸出（方便下游腳本）

python build_directory.py                      # 由 source zip 重抽目錄
```

`build_directory.py` 讀 `E:/Skill hub/awesome-freellm-apis-main.zip` 嘅 README 內嵌表格（每日刷新），
輸出 `references/providers.json`。**唔會發網絡請求、唔會讀或寫任何 API key。**

## 目錄字段

| 字段 | 意義 |
|---|---|
| `name` | Provider 名 |
| `tier` | `permanent`（永久免費層）/ `renewable`（可續期 credit）/ `unknown` |
| `base_url` | OpenAI-compatible endpoint（無則空字串） |
| `key_url` | 官方申請 key 入口 |
| `credit_card` | `No` / `Registration` / `Phone verification` / `信用卡要求` |
| `free_models` | 該 provider 免費模型數 |
| `max_context` | 最大 context window |
| `modalities` | 支援模態陣列 |
| `credit_model` | 續期型嘅 credit 規則（例如 OpenRouter「免費層 + $10 充值 → 1000 RPD」） |
| `best_models[]` | 代表模型：`model_id` / `ctx` / `rate_limit` |

## 永久免費層（29 個）

**唔使信用卡（10 個，signup 即可用）**
`Cerebras` `Cloudflare Workers AI` `Cohere` `Google Gemini` `Groq` `Hugging Face` `Kilo Code` `LLM7.io` `Mistral AI` `Z AI`

**只要註冊（大部分 30 RPM 級）**
`Alibaba Cloud Model Studio` `Aion Labs` `Agnes AI` `Chutes.ai` `DeepSeek` `Glhf.chat` `Grok (xAI)` `ModelScope` `Nebius` `Nscale` `Ollama Cloud` `OpenCode Zen` `OVHcloud AI Endpoints` `SambaNova` `SiliconFlow` `xAI` `AI21 Labs` `Cline`

**要手機驗證**
`NVIDIA NIM`（134 個免費模型，最多）

**可續期 credit**
`OpenRouter`（33 個免費模型，免費層 + $10 充值升 1000 RPD）

## 免 key 免費層（實測 2026-10-20）

兩個 provider 免 key 都真通，已經接落 WorkBuddy（經本機 freellmapi gateway）：

| Provider | base URL | 免 key | 官方條款 |
|---|---|---|---|
| **Kilo Code** | `https://api.kilo.ai/api/gateway` | ✅ | 官方明文：unauthenticated access for **free models only**，**200 req/hr/IP** |
| **LLM7.io** | `https://api.llm7.io/v1` | ⚠️ 部分 model | 免費層 **100,000 tokens/day**、250 r/h、60 r/m、1 r/s。Pro 先有 function calling |

**數據私隱警告**
- Kilo 嘅 NVIDIA free endpoint 係 **trial only** — 會記錄使用數據作改進 NVIDIA 產品用，**唔好提交機密資料**。
- LLM7 免費層收集匿名使用數據。

**OpenCode Zen**：免費層 **只限 OpenCode 內用**（403 FreeTierError），唔可以當通用 endpoint。

## 自架 Router（兩個）

| Repo | 性質 | 用途 |
|---|---|---|
| **freellmapi** | Node/Express 自架 router | 本機已裝（`~/freellmapi`，port 3001）。用 `keys` + `models` schema 掛 provider，支援 `keyless: true` + `no-key` sentinel → 免 key provider 嘅唯一可行接入路徑 |
| **free-claude-code** | Python 自架 router（55 provider 適配層） | 一次過掛 55 個 ToS-friendly provider，支援 10 個 coding agent（Claude Code / Codex / Pi / OpenCode / Cline / Hermes / DSH / Grok Build / Muse Code / Aider）。provider 掛完就會跟 Term of Service 更新 |

兩個都**無 key 收集、無 webhook 投遞**（2026-10-20 源碼審查）。

詳見 `references/self-hosted-routers.md`。

## 本地推理（唔係免費 API 層）

**FreeToken** = 本地 GPU MoE 推理引擎（290B+ 模型跑喺自己硬件）。**唔係免費 API provider**，
係「零 API 費」嘅另一條路 —— 有 GPU 就本機跑，冇 rate limit、冇 key、冇資料出境。
詳見 `references/local-inference-freetoken.md`。

## 落地：Cursor / Grok Bot 免費模型（實測 2026-10-20）

呢個 skill 唔止係「查目錄」，仲有兩條**已驗證可行**嘅落地路徑，令 Cursor 同 Grok Bot 用免費 token。

### 路線 1 · Cursor BYOK（`configure_cursor_free.py`）

Cursor 3.25.6 嘅 BYOK 設定其實喺**三個位**（全部本機實測查明）：

| 位 | 內容 | 加密方式 |
|---|---|---|
| `state.vscdb` → `applicationUser` → `openAIBaseUrl` | base URL | 明文 |
| `state.vscdb` → `secret://cursorAuth/openAIKey` | API key | Chromium OSCrypt v10 |
| `state.vscdb` → `aiSettings.userAddedModels` / `modelOverrideEnabled` | model 清單 | 明文 |

**解密原理**：`v10` blob = `v10` + nonce(12) + AES-256-GCM(ciphertext+tag)。
master key 喺 `%APPDATA%\Cursor\Local State` → `os_crypt.encrypted_key`（base64 + 5-byte `DPAPI` 前綴），
用 `win32crypt.CryptUnprotectData` 解 DPAPI 保護層，再 AES-GCM 解密內容。
（`cursor_oscrypt.py` 提供 `load_master_key` / `decrypt_secret` / `encrypt_secret` / `mask`，roundtrip 已驗證。）

**base URL 格式陷阱**：Cursor 會用 `WF_()` 正規化 —— `pathname === "/"` 會自動補 `/v1`、去尾斜杠，
然後**由 Cursor 自己拼 `/chat/completions`**。所以唔可以自己加 `/chat/completions` suffix（會雙重拼接）。

```bash
cd scripts
python configure_cursor_free.py --check     # 只睇現況，唔改
python configure_cursor_free.py --apply     # 套用（必須先關閉 Cursor）
python configure_cursor_free.py --apply --wait 3600   # 等 Cursor 關閉（最多 3600 秒），關咗即自動套用
python configure_cursor_free.py --apply --state-db <副本路徑>   # 沙盒 dry-run，唔使關 Cursor
```

⚠️ **必須完全關閉 Cursor 先 apply**（`state.vscdb` 開住 WAL，行緊寫會蓋掉改動）。
腳本會偵測 `Cursor.exe` 進程，行緊就直接 exit 2 拒絕改；加 `--wait N` 就會輪詢等，
**唔會強制 kill Cursor**（避免遺失未存檔案）。

**套用後腳本會自我驗證**：讀回 `state.vscdb` → OSCrypt 解密 → 比對 key → 真打 gateway，
輸出 `HTTP 200 | cost=0 | 'CURSOR_FREE_OK'` 就代表真係通。

**套用後 Cursor 見到嘅 6 個免費 model**（全部經 gateway 實測 HTTP 200 + `usage.cost=0`）：

`minimax-m3.1-flash` · `nemotron-3.5-lightning` · `nemotron-3-ultra` · `north-mini-code` · `lfm-2.5-2.6b` · `free-router`

> `nemotron-3-super` 已於 2026-10-20 實測 404（上游下架），已從清單剔除。

### 路線 2 · 將 agent 綁去免費通道（`bind_grok_bot_free.py`）

**WorkBuddy agent frontmatter 冇 `model:` 欄位**（已於 WorkBuddy asar 驗證）——
agent 用邊個模型係 UI 層決定，唔可以喺 plugin 檔案硬綁。所以 Token 自由要咁做：

1. agent frontmatter `skills` 加 `free-api-directory` → agent 執行時自動載入免費目錄 + 查詢腳本
2. agent 正文「技術基礎」段落改用**免費層 model id** → 呢段係 agent 真正會讀嘅上下文，令佢唔好叫用戶轉付費

```bash
cd scripts
python bind_grok_bot_free.py --check                        # 睇現況
python bind_grok_bot_free.py --apply                        # 改 agents/*.md（自動備份）
python bind_grok_bot_free.py --restore-from <backup_dir>    # 還原
```

腳本掃 `agents/*.md`，本 plugin 只有「自由客」一個 agent，改一個檔。

**兩個易踩嘅坑**（已修）：
- `skills:` 一定要插喺 YAML 陣列**括號裡面**：`[a, free-api-directory]`。
  寫成 `[a], free-api-directory` 係括號外逗號 = YAML 語法錯，agent 會讀唔到 skills。
- `## 技術基礎` 段落嘅 regex 要用 `[ \t]*\n` 而唔係 `\s*\n`（`\s*` 會連帶食晒多餘空行）。

### 免費通道 A · 本機 freellmapi gateway（推薦，無每日上限）

- **Base URL**：`http://127.0.0.1:3001/v1`
- **key**：`~/freellmapi/server/data/freeapi.db` → `settings.unified_api_key`（格式 `freellmapi-<48 hex>`）
- 走 Kilo Code 免 key 層（官方明文：unauthenticated access for free models only，**200 req/hr/IP**）

### 免費通道 B · OpenRouter 免費層

- **Base URL**：`https://openrouter.ai/api/v1`
- **額度 50 req/day，全帳戶共用**（唔係每個 model 各計）—— 唔好大量 probe，會燒光配額
- 判定 429 屬邊個嘅問題：淨係個別 model 429 = provider 過載；多個 `:free` model 同時 429 = 每日 counter 用完

## 紅線

- 唔買付費方案
- 唔偷／唔 share／唔賣 key；**唔喺 chat 貼 key**
- 唔繞過 paywall 或 ToS
- 目錄係**候選池**，唔係「保證可用」—— 接入前一定實測（用 `free-for-all` skill 嘅 `doctor.py`）
- 免 key provider 唔好提交機密或客戶資料

## 交付格式

搵到方案後交俾用戶：

1. **Provider + tier**（永久免費 / 可續期 / 免 key）
2. **base URL**（逐字，唔好改）
3. **model id**（逐字，唔好靠記憶）
4. **申請入口**（key_url）
5. **信用卡要求**（用戶最關心呢個）
6. **接入步驟**（WorkBuddy / DSH / Qwen Code / Cursor —— Cursor 有現成腳本 `configure_cursor_free.py`）
7. **實測狀態**（實測過先講「通」；未實測就講「候選」）
