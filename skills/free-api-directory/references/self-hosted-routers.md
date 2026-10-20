# 自架 Router 對照（freellmapi / free-claude-code）

兩個都係「一次過掛多個 provider、自己控路由」嘅自架 gateway。**2026-10-20 源碼審查：兩者皆無 key 收集、無 webhook 投遞、無憑證外傳。**

---

## 1 · freellmapi（本機已裝，`~/freellmapi`，port 3001）

Node + Express。功能強在**可以掛免 key provider**。

### 關鍵 schema

```json
{
  "keys": [
    { "platform": "kilo", "label": "Kilo Free (anonymous, keyless)", "enabled": true }
  ],
  "models": [
    {
      "platform": "kilo",
      "modelId": "minimax/minimax-m3.1-flash:free",
      "displayName": "MiniMax M3.1 Flash (Kilo free, 1M, tools)",
      "contextWindow": 1000000,
      "supportsTools": true
    }
  ]
}
```

### 兩條硬規則

1. **必須用 `keys` + `models`，唔可以用 `customProviders`**
   `customProviders` 唔支援空 `apiKey` → 報 `key is required for custom`。
2. **`platform: "llm7"` 會被 skip** —— 該 platform 唔係 keyless，要 key 喺 dash.llm7.io 攞。

### 免 key 接入原理

- freellmapi 內建 `kilo` provider（`keyless: true`），原生支援 `no-key` sentinel
- WorkBuddy `models.json` **強制 apiKey 非空**（`!isFilledString(e.apiKey) && !isLoopbackModelEndpoint(e.url)` → 報錯）
- 所以免 key provider **唔可能直接寫入 models.json**，必須經 gateway

### 啟動（持久）

`start-freellmapi.ps1` 用 `Start-Process` 起子進程 → **PowerShell session 一結束就死**。
要用持久背景方式直接跑 `node server/dist/index.js`。

另外 `Start-Process` 傳 `-Environment` 會撞 `HTTP_PROXY` / `http_proxy` 大小寫衝突。

### 設定檔位置

`~/freellmapi/freellmapi-free-providers.json`，由 `.env` 嘅 `FREEAPI_CONFIG_PATH` 指定。

### 免 key model 短 id 陷阱

WorkBuddy `models.json` 用 gateway 顯示嘅**短 id**（如 `minimax-m3.1-flash`），
唔係 OpenRouter 完整 id（`minimax/minimax-m3.1-flash:free`）。搞錯會 404。
短 id 以 `GET http://127.0.0.1:3001/v1/models` 實際回傳為準。

### `FREEAPI_DESKTOP` 通道

目前**保持關閉**（2026-10-19 按用戶要求撤銷）。要再次腳本化補上游 key：
臨時加 `FREEAPI_DESKTOP=1` → 重啟 → 補完 → 刪掉 → 重啟。

---

## 2 · free-claude-code（未裝，Python 3.14 + uv）

自架 router + Admin UI，掛 **55 個 ToS-friendly provider**，支援 **10 個 coding agent**。

### 支援嘅 coding agent

Claude Code · Codex · Pi · OpenCode · Cline · Hermes · DeepSeek Harness · Grok Build · Muse Code · Aider

### 特色功能

- **Provider 掛完就會跟 Term of Service 更新** —— 唔合規嘅整合會自動移除
- **Fallback 自動切換**：某個 provider 掛咗，重試耗盡後自動轉下一个已配置 model，唔使重開個 turn
- **RTK**：可選，過濾終端輸出，最多減少 90% terminal-output token
- **5 個內建優化**：quota probe、command-prefix detection、titles、suggestions、filepaths —— 呢啲唔會調用 provider
- **Model tier routing**：`MODEL` 為 fallback，可用 `MODEL_FABLE` / `MODEL_OPUS` / `MODEL_SONNET` / `MODEL_HAIKU` 逐層覆蓋
- **Reasoning 控制**：From client（預設）/ Off / Low / Medium / High / X-High / Max / Inherit

### 安裝（官方 script — 執行前必須先 review）

```bash
# macOS/Linux
curl -fsSL "https://raw.githubusercontent.com/Alishahryar1/free-claude-code/main/scripts/install.sh" | sh
```

```powershell
# Windows PowerShell
& ([scriptblock]::Create((irm "https://raw.githubusercontent.com/Alishahryar1/free-claude-code/main/scripts/install.ps1")))
```

⚠️ **官方建議先睇過 installer 再跑**。本 skill 唔會自動執行安裝 script。

### 環境變數（前綴即 provider 命名空間）

| 變數 | Provider | 例子 model slug |
|---|---|---|
| `ZAI_API_KEY` | Z.ai Coding Plan / Z.ai API | `zai/glm-5.2` / `zai_api/glm-4.7-flash` |
| `TOKENROUTER_API_KEY` | TokenRouter | `tokenrouter/moonshotai/kimi-k3-free` |
| `NARAROUTE_API_KEY` | NaraRoute | `nararoute/kimi-k3-free` |
| `POOLSIDE_API_KEY` | Poolside AI | `poolside/poolside/laguna-s-2.1` |
| `LLM7_API_KEY` | LLM7.io | `llm7/default` |
| `SCW_SECRET_KEY` | Scaleway | `scaleway/deepseek/deepseek-v4-flash` |
| `LIGHTNING_API_KEY` | Lightning AI | `lightning/lightning-ai/Qwen3.8-27B` |
| `EXPLABS_API_KEY` | Experiential Labs | `experiential/union-alpha` |
| `CHEAPER_INFERENCE_API_KEY` | Cheaper Inference | `cheaperinference/gpt-5.4-mini` |
| `OLLAMA_API_KEY` | Ollama Cloud | `ollama_cloud/qwen3-coder:480b` |
| `LM_STUDIO_BASE_URL` | LM Studio（本地） | `lmstudio/<model-id>` |
| `LLAMACPP_BASE_URL` | llama.cpp（本地） | `llamacpp/<model-id>` |
| `OLLAMA_BASE_URL` | Ollama（本地） | `ollama/<model-tag>` |

### 各家 key 唔通兌（重要）

| Provider | 分離規則 |
|---|---|
| OpenAI / ChatGPT | 用 ChatGPT 訂閱，唔係 API key。Admin UI → Providers → OAuth providers → OpenAI / ChatGPT → Connect，瀏覽器完成登入 |
| OpenAI API | 獨立 Platform key。Providers → Cloud providers → OpenAI API → Configure。model list 可能有唔支援 coding 嘅 id，要揀 text-generation |
| GitHub Copilot | 用簽入嘅 GitHub 帳戶 + 訂閱。要 Copilot CLI ≥ 1.0.83 在 PATH，Admin UI → OAuth providers → GitHub Copilot → Connect，model 用 `github_copilot/<model-id>` 前綴 |
| Azure OpenAI | `AZURE_OPENAI_BASE_URL` = 完整 v1 endpoint（如 `https://YOUR-RESOURCE-NAME.openai.azure.com/openai/v1/`），揀支援 Chat Completions 嘅 deployment 名 |
| Mistral Codestral | key 與 Mistral La Plateforme 分開 |
| Kimi | Code 訂閱 key 用 `kimi_code/` 前綴，API credit key 用 `kimi/` 前綴，**唔通兌**。Kimi Code 僅限個人互動式 coding agent 使用 |
| QwenCloud | Coding Plan key 用 `qwencloud_coding/`，Token Plan key 用 `qwencloud/`，**唔通兌**。Coding Plan 僅限本地個人互動使用 |
| OpenCode | Zen 同 Go 共用 `OPENCODE_API_KEY`，但用 `opencode_zen/` / `opencode_go/` 明確前綴 |
| Amazon Bedrock | `BEDROCK_BASE_URL` 要同 key 同區域 |
| Vertex AI | 用 Google ADC 唔使 API key。本機行 `gcloud auth application-default login` 一次。設 `VERTEX_PROJECT_ID`，`VERTEX_LOCATION` 預設 `global` |
| Cloudflare | 要 API token **同** account ID 兩個 |
| Ollama | Cloud 用 picker 顯示的確切 model id；本地 Ollama 用獨立 `ollama/` 前綴 |

### 本地 provider

| 工具 | 預設 URL | 指令 |
|---|---|---|
| LM Studio | `http://localhost:1234/v1` | 開 server、載 tool-capable model、用 `lmstudio/` 前綴 |
| llama.cpp | `http://localhost:8080/v1` | 起 `llama-server`（OpenAI-compatible Chat Completions API）、用 `llamacpp/` 前綴 |
| Ollama | `http://localhost:11434` | `ollama pull llama3.1` + `ollama serve`、用 `ollama/` 前綴 |

### 客戶端接入

**同一部機、同一個用戶環境**行 FCC，然後 Admin UI → Integrations → 對應卡片 → Connect。

支援：Claude Code in VS Code · Claude Desktop · Codex in VS Code / App · Claude Code in JetBrains ACP
（JetBrains 要先啟動一次 JetBrains AI Assistant 嘅 Claude Agent；JetBrains 更新 agent 後要重啟 FCC）

Claude Desktop 要**完全退出**先接，Disconnect 會還原正常 Claude 登入。
VS Code / App 改完要 reload 或重啟。

### 可選 messaging 整合

- **Discord**：Developer Portal 建 bot → 開 Message Content Intent → 邀請並給 `read`/`send`/`message-history`/`Manage Messages` 權限（`/clear` 要刪訊息）→ Messaging Platform = `discord` → 填 Bot Token / Allowed Channels / 絕對路徑 Allowed Directory → Apply
- **Telegram**：@BotFather 建 bot → 填 Bot Token / Allowed User ID / 絕對路徑 Allowed Directory → Apply

---

## 選邊個？

| | freellmapi | free-claude-code |
|---|---|---|
| 免 key provider | ✅ **原生支援**（`keyless: true`） | ❌ 要逐個 key |
| Provider 數量 | 少量（按需掛） | **55 個** |
| Coding agent 適配 | 通用 OpenAI-compatible | **10 個 agent 專用整合** |
| 管理介面 | 檔案設定 | **Admin UI**（圖形介面） |
| ToS 監控 | 無 | ✅ 自動移除不合規整合 |
| 本機狀態 | **已裝、已接 17 個 free model** | 未裝 |

**現實建議**：本機 freellmapi 已行得通（11/17 實測 200、cost=0、支援 function calling），
除非要用 Claude Code / Codex 專用整合，否則唔需要再加一套。
