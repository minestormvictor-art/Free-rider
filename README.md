<div align="center">

# Free-Rider 自由客

### 🆓 零成本 AI Token 接入 · 免費 API 目錄

**搵免費／優惠 AI API 方案，核實仲生效，然後零成本接落 Cursor / WorkBuddy / DSH / Qwen Code**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Providers](https://img.shields.io/badge/providers-30%20%2F%20513%2B%20models-purple.svg)](skills/free-api-directory/)
[![Verified](https://img.shields.io/badge/verified-6%2F6%20cost%3D0-success.svg)](skills/free-api-directory/)

</div>

---

## 這是什麼

**自由客（Free-Rider）** 係一個 WorkBuddy agent，專責一件事：

> **搵出仍在生效嘅免費／優惠 AI API 方案，逐個核實，然後交出確切接入步驟。**

配備兩套可執行 skill：

| Skill | 用途 |
|---|---|
| **`free-api-directory`** | 離線 provider 目錄：30 家、513+ 免費模型，含 base URL、申請入口、信用卡要求、rate limit。**完全離線，唔使上網，唔會讀寫任何 API key** |
| **`free-for-all`** | 免費額度巡檢、多端模型安裝／同步、健康檢查、已廢 provider 清理 |

---

## 快速開始

### 安裝

```bash
git clone https://github.com/minestormvictor-art/Free-rider.git
cp -r Free-rider/. ~/.workbuddy/plugins/marketplaces/my-experts/plugins/free-rider/
```

然後喺 WorkBuddy 重啟／重載 plugin。

### 查免費 provider（離線）

```bash
cd skills/free-api-directory/scripts

python query_directory.py --list                # 全部 30 個 provider
python query_directory.py --no-card             # 只要唔使信用卡（10 個）
python query_directory.py --provider groq       # base URL / 申請入口 / 代表模型
python query_directory.py --search nemotron     # 搜 provider 名或 model id
python query_directory.py --modality code       # 按模態篩
python query_directory.py --provider kilo --json # JSON 輸出
```

### 零成本接入 Cursor（已實測驗證）

```bash
cd skills/free-api-directory/scripts

python configure_cursor_free.py --check             # 先睇現況，唔會改
python configure_cursor_free.py --apply             # 套用（要先關閉 Cursor）
python configure_cursor_free.py --apply --wait 3600 # 或者：等 Cursor 關咗自動套用
```

腳本會自動備份 `state.vscdb`、改寫 BYOK 三個位、然後**自我驗證**
（讀回 → 解密 → 真打 gateway），輸出 `HTTP 200 | cost=0` 就代表真係通。

> ⚠️ **必須完全關閉 Cursor**（`state.vscdb` 開住 WAL，行緊寫會覆蓋改動）。
> 腳本偵測到進程會直接拒絕改，**唔會強制 kill 你的 Cursor**。
> 需要 `pywin32` + `cryptography`（Windows only）。

---

## 免費通道

### 通道 A · 本機 gateway（推薦，無每日上限）

走自架 router（freellmapi），轉發去免 key 免費層。

- **Base URL**：`http://127.0.0.1:3001/v1`
- **實測可用（6/6 全部 HTTP 200、`usage.cost = 0`）**：

| Model | 用途 |
|---|---|
| `minimax-m3.1-flash` | 免費層最穩，支援 function calling |
| `nemotron-3.5-lightning` | 快，適合日常 |
| `nemotron-3-ultra` | 免費層最強推理（550B） |
| `north-mini-code` | code 專用 |
| `lfm-2.5-2.6b` | 最穩，function calling 首選 |
| `free-router` | 自動路由免費層 |

### 通道 B · OpenRouter 免費層

- **Base URL**：`https://openrouter.ai/api/v1`
- **額度 50 req/day（全帳戶共用，唔係每個 model 各計）**

### 免 key 供應商

| Provider | 免 key | 條款 |
|---|---|---|
| Kilo Code (`api.kilo.ai/api/gateway`) | ✅ | 官方明文：unauthenticated access for free models only，**200 req/hr/IP** |
| LLM7.io (`api.llm7.io/v1`) | ⚠️ 部分 | 免費層 **100,000 tokens/day**、250 r/h |

> 🔒 **數據私隱警告**：Kilo 嘅 NVIDIA free endpoint 係 trial only，會記錄使用數據。
> **唔好提交機密或客戶資料。**

---

## 紅線

自由客遵守以下規則，唔會違反：

- ❌ 唔買付費方案
- ❌ 唔偷 / 唔 share / 唔賣 key
- ❌ **唔喺 chat 或任何渠道貼 key**
- ❌ 唔繞過 paywall 或 ToS
- ❌ 唔裝可疑 repo（特別係「免費 API」釣魚 repo）
- ⚠️ 目錄係**候選池**，唔係保證可用 —— 接入前一定實測
- ⚠️ 免 key provider **唔好提交機密或客戶資料**

---

## 項目結構

```
Free-rider/
├── .codebuddy-plugin/plugin.json      plugin manifest（單一 agent）
├── agents/
│   └── grok-agent-01.md               自由客 ← 唯一 agent
├── skills/
│   ├── free-for-all/                  免費額度巡檢 + 多端安裝 + 健康檢查
│   │   ├── SKILL.md
│   │   └── scripts/                   install / doctor / claim_credits /
│   │                                  probe_providers / prune_dead_apis / …
│   └── free-api-directory/            離線 provider 目錄 + 接入腳本
│       ├── SKILL.md
│       ├── references/
│       │   ├── providers.json         30 provider / 513+ 模型
│       │   ├── self-hosted-routers.md 自架 router 對照
│       │   └── local-inference-freetoken.md
│       └── scripts/
│           ├── query_directory.py     離線查詢 CLI
│           ├── build_directory.py     由 source 重抽目錄
│           ├── configure_cursor_free.py  Cursor BYOK 零成本接入
│           ├── cursor_oscrypt.py      Chromium OSCrypt v10 加解密
│           └── bind_grok_bot_free.py  agent 綁免費通道
├── avatars/expert.png
└── roster.json                        agent manifest
```

---

## 安全說明

`configure_cursor_free.py` 會讀寫本機 Cursor 的 BYOK 設定（`state.vscdb`）：

- 讀寫前**自動備份** `state.vscdb`
- **唔會**上傳任何 key、唔會連接任何外部服務（除咗你自己指定嘅 gateway）
- API key 全部留喺本機，只喺 stdout 用 `sk-or-…6159` 形式遮罩顯示

`free-api-directory` 的查詢腳本**完全離線**，唔發任何網絡請求、唔讀或寫任何 API key。

---

## 來源

- Agent persona 源自 Grok Bot agent presets（經 DSH 移植）
- Provider 目錄改編自 awesome-freellm-apis 每日刷新目錄
- 自架 router 參考 freellmapi 與 free-claude-code
- 本地推理資料參考 FreeToken

---

## License

MIT © Victor Tse Yu Fai — 見 [LICENSE](LICENSE)。
