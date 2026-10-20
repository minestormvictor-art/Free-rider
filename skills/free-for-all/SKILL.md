---
name: free-for-all
description: Find and verify live free/freemium AI API plans (OpenAI-compatible, Anthropic, Google, open routers, student/trial credits, zero-cost tiers), then wire them into Cursor, WorkBuddy, DSH and Qwen Code. Use when the user asks for free AI API keys, cheap LLM access, how to add a custom provider to Cursor, or wants their existing model configs checked and synced. Includes live key validation and a 57-agent Grok Bot roster index.
---

# 自由客 — 免費 AI 資源偵察與接入

搵到仍在生效嘅免費／優惠 AI API 方案，核實後交出**確切嘅 base URL、申請路徑、接入步驟**。

## 兩條工作線

### A · 搵資源（web search）

1. **搜** — 搵現行免費層：OpenAI-compatible、Anthropic、Google、open router、學生／試用 credit、zero-cost tier
2. **核實** — 開返官方 pricing／docs 頁，抽出：
   - model id（**逐字**，唔好靠記憶）
   - rate limit、額度、有效期
   - 地區／登入要求
   - OpenAI-compatible endpoint（如有）
3. **交付** — 俾用戶：base URL、key 申請路徑、Cursor 接入步驟

**優先官方文件，唔好用隨機 blog。** 唔好發明 endpoint 或 key。

### B · 接入（本地執行）

四個目標工具，各有各嘅設定格式：

| 工具 | 設定檔 | 格式 | 能否代勞 |
|---|---|---|---|
| **WorkBuddy** | `~/.workbuddy/models.json` | JSON 陣列 | ✅ 可以 |
| **DSH** | `~/.dsh/profiles/desktop/cordis.patch.yml` | YAML patch | ✅ 可以 |
| **Qwen Code** | `~/.qwen/.env` | env | ✅ 可以 |
| **Cursor** | `globalStorage/state.vscdb` → `secret://cursorAuth/openAIKey` | Electron safeStorage 加密 | ❌ **唔得**，只能叫用戶手動入 UI |

```bash
cd scripts
python install.py --sync-only              # 睇三邊狀態
python install.py --preset free --doctor    # 安裝 + 實測
python doctor.py                            # 完整健康檢查
python claim_credits.py                     # 多平台免費額度巡檢（8 平台，唯讀）
python prune_dead_apis.py                   # 清理已廢 model（DRY-RUN 預覽）
python prune_dead_apis.py --apply           # 真正清理
python probe_providers.py                   # 跨供應商 base URL 探測（42 個）
python install_free_providers.py --verify   # 免 key 免費層（Kilo/LLM7）狀態
python add_gateway_models_to_workbuddy.py --apply  # gateway 免費 model 入 WorkBuddy
python verify_gateway_free.py               # 經 gateway 實測所有 ready model
```

### C · 查目錄（離線）

搵「仲有咩免費 provider」時，唔使逐個上網搜 —— 用 `free-api-directory` skill：

```bash
cd ../free-api-directory/scripts
python query_directory.py --list           # 30 個 provider 一覽
python query_directory.py --no-card        # 只要唔使信用卡（10 個）
python query_directory.py --provider groq  # base URL / 申請入口 / 代表模型
python query_directory.py --search nemotron
```

**目錄 = 候選池，唔係「保證可用」。** 接入前一定要用本 skill 嘅 `doctor.py` 實測。

## 紅線（不可越過）

- 唔買付費方案
- 唔偷／唔share／唔賣 key
- 唔繞過 paywall 或 ToS
- 唔抓取憑證
- **唔喺 chat 或其他渠道貼 key**
- 唔裝可疑嘅「free API」repo（可能係惡意程式）
- 唔建立其他 bot
- 遇到疑似釣魚、憑證收集、破解 key 嘅「免費」方案 → **拒絕並講原因**

## 相關 skill

- **`free-api-directory`** —— 離線免費 API 目錄（30 provider / 513+ 模型），查 base URL、申請入口、信用卡要求、rate limit
- **`openrouter-bridge`** —— OpenRouter 模型通道與健康檢查

## 語氣

短、hustler-lab 感；用戶寫咩語言就回咩語言（粵/英夾雜）；**直接畀最好嘅現行免費選項 + 接入步驟**；唔講廢話。

## 觸發時機

- 預設：每日掃描新／有變化嘅免費 token 方案
- 按需：用戶點名某個 provider
- 冇新嘢或原有方案仍然有效 → **保持安靜**

---

## 附錄 A · 實測可用模型（2026-10-20）

⚠️ OpenRouter catalog 會變，用之前跑 `doctor.py` 重新確認。

**免費層（有限額，通常 50 次/日；充值 $10 後升 1,000 次/日）**
```
liquid/lfm-2.5-2.6b:free               64K    ← 最穩，支援 function calling
nvidia/nemotron-3-ultra-550b-a55b:free  1M    ← 2026-10-20 新增，實測通
nvidia/nemotron-3.5-lightning:free     1M    ← 2026-10-20 新增，實測通
nvidia/nemotron-3-super-120b-a12b:free  256K  ← 2026-10-20 新增，實測通
cohere/north-mini-code:free            256K   ← 2026-10-20 新增，code 專用
minimax/minimax-m3.1-flash:free        1M     ← 2026-10-20 新增，實測通
dots-studio/dots-3-note-preview:free   512K   ← 2026-10-20 新增，實測通
poolside/laguna-s-2.1:free             262K   ← 間中 429
poolside/laguna-xs-2.1:free           262K   ← 間中 429
google/gemma-4-31b-it:free             262K   ← 長期 429
google/gemma-4-26b-a4b-it:free         262K   ← 長期 429
```

**403 = 限特殊場合，唔係 429**：`thinkingmachines/inkling:free` / `thinkingmachines/inkling-small:free`
（975B 總參數、1M ctx，但 catalog 有、實測 403，唔好當可用）

**收費但極平**
```
qwen/qwen3-coder-next        $0.000003   ← 全場最平
bytedance-seed/seed-2.0-mini  $0.000012
qwen/qwen3.8-flash           $0.000022
bytedance-seed/seed-1.6-flash$0.000021
x-ai/grok-4.20               $0.000104   ← 2M context + 便宜
```

**其他可用**
```
qwen/qwen3.7-plus / qwen3.8-27b / qwen3.8-max-0902 / qwen3.7-max
moonshotai/kimi-k2.5 / k2.6 / k2 / k2.7-code / k3(1M ctx)
bytedance-seed/seed-2.0-code / seed-2-1-turbo / seed-2.0-lite / seed-1.6
x-ai/grok-build-0.1 / grok-4.7
```

**Kimi（moonshotai）同豆包（bytedance-seed）全部收費，全部支援 function calling。**

## 附錄 B · 43 個 Grok Bot Agent 名單

> 2026-10-20 融合後：原 57 個減至 43 個。13 個職能重疊者已併入對應嘅本地 expert
> （工料測量／屋宇裝備／合約／結構／八字／風水／占卜／玄學分流／項目管理／室內／三個繪圖），
> 內容以「作業資源與技術來源」章節形式保留。1 個完全重複者已合併。

**現存編號缺號**（2026-10-20 實測 `roster.json` 43 條、`agents/` 43 個 `.md`）：
`6, 9, 11, 21, 24, 36, 40, 41, 42, 45, 51, 54, 55, 56, 57` —— 呢啲係融合掉咗嘅職能，
唔係漏建。要對帳原 57 個清單時以缺號表為準，唔好當成 bug。

`roster.json` 有完整 manifest。

**營運／財務（13）**
`自由客`
`總經理`
`保安`
`訂單客服`
`法務`
`人事`
`雲端代理協調助手`
`行政`
`會計`
`供應商對接`
`物流報關`
`上架專員`
`團隊經理`

**開發／技術（13）**
`前端開發`
`首席AI官`
`工作台搭建師`
`高級開發`
`蛋博士`
`網站專員`
`夜間審核工程師`
`全端搭建師`
`網頁專家`
`硬件系統工程師`
`工作區搭建師`
`逆向工程師`
`現代網頁`

**營銷／內容（13）**
`動畫設計師`
`外展拓客`
`SEO與AEO台`
`音樂監製`
`媒介買手`
`平面設計師`
`編劇`
`文案策略師`
`縮圖封面師`
`剪接師傅`
`成效分析師`
`影視總監`
`晨報`

**工程／建造（香港）（4）**
`香港建材`
`香港土木工程師`
`香港建築師`
`香港建築工程師`

## 附錄 C · 常見錯誤碼

| 碼 | 原因 | 動作 |
|---|---|---|
| 401 | key 失效 | 換 key |
| 403 | model 限特殊場合 | 換 model |
| 404 | model 名錯／無免費版 | 對 catalog 逐字核 |
| 400 | model 類型錯（embedding/TTS）| 換 model 類型 |
| **403** | model 限特殊場合 | 換 model，唔好重試 |
| **429** | **provider 過載，唔關你事** | 等陣重試或換 provider |
| 502 | 本地 gateway 冇開 | 開 gateway 或改直連 |

**驗證 model 存在性只能用 catalog list**（`GET /api/v1/models`）。`GET /api/v1/models/{id}` 一律 404，唔可信。

**判定 429 屬於邊個嘅問題**：先 `GET /api/v1/key` —— key `active` 但 chat 返 429，就係 provider 過載。

### ⚠️ 429 有兩種成因，唔好亂下結論（2026-10-20 實測修正）

舊結論「429 = provider 過載」**唔完整**。真實有兩種：

| 判定方法 | 結論 |
|---|---|
| 同一 model 隔 10-30 秒重試仍然 429，**且多個 :free model 同時 429** | **每日 request counter 用完**（OpenRouter 免費層 = 50 req/day/account，全 account 共用，唔係每個 model 各自計） |
| 淨係個別 model 429，其他 :free model 同時正常 | provider 側過載 |

**重要**：`GET /api/v1/key` 嘅 `usage` / `limit` 只反映 **credit 餘額**（美元），**唔反映 request 計數**。所以見到 `remaining: 49.97/50` 唔代表免費層仲有 50 次可用 —— 要靠實際 ping 判斷。

**實務教訓**：巡檢時唔好用大量 probe 燒免費層配額。一次長度量測（每 model 3-5 次）就已經可能用掉 30-50 次。建議：每 model 只 ping 1-2 次，需要 function calling 確認就加 1 次 forced tool_choice。

## 附錄 D · 已失效 / 唔好再推（2026-10-20 官方核實）
| 平台 | 狀態 | 官方依據 |
|---|---|---|
| **GitHub Models** | ❌ **2026-07-30 全面退役** | playground / catalog / inference API / BYOK 全部取消。改推 Azure AI Foundry 或 GitHub Copilot |
| **Hugging Face Inference Providers** | ⚠ **免費帳戶 $0/月** | 只有 PRO / Team / Enterprise 每席 $2/月。免費戶要買 credits。Router 仍可用：`https://router.huggingface.co/v1` |
| **Mistral Free tier 額度** | ⚠ **公開頁無數字** | `docs.mistral.ai/deployment/laplateforme/tier/` 已 404；限額只喺 Admin Panel 顯示。唔好聲稱具體額度，要用就自己登入 console 睇 |
| **Cloudflare Workers AI 熱門模型** | ⚠ **部分要付費 plan** | kimi-k2.6 / k2.7-code / glm-5.2 / glm-5.3 / glm-5.3-flash / deepseek-v4 全系列需 Workers Paid 或 AI Gateway credits。免費層仍係 10,000 neurons/day |

## 附錄 E · 實測成本表（2026-10-20，~1000 token prompt / 200 token completion）

用真實長度 prompt 實測，唔係查表。`per1K_p` = 每 1K **prompt** token 成本，agent 場景最重要（每步都要重送 context）。

| model | per1K_p | per1K_c | function calling | ctx | 備註 |
|---|---|---|---|---|---|
| **bytedance-seed/seed-1.6-flash** | **$0.000136** | $0.000671 | ❌ | 262K | 全場最平，但唔支援 tools |
| **qwen/qwen3-coder-next** | $0.000143 | $0.005020 | ✅ | 262K | 最平 + 支援 tools ← **agent 首選** |
| bytedance-seed/seed-2.0-mini | $0.000184 | $0.000875 | ❌ | 262K | output 極平 |
| qwen/qwen3.8-flash | $0.000251 | $0.001170 | ✅ | 1M | 支援 tools + 1M ctx |
| qwen/qwen3-coder | $0.000356 | $0.004715 | ❌ | 262K | |
| bytedance-seed/seed-2.0-lite | $0.000473 | $0.004243 | ✅ | 262K | |
| moonshotai/kimi-k2.5 | $0.001267 | $0.005608 | ✅ | 262K | |
| bytedance-seed/seed-2-1-turbo | $0.000780 | $0.006972 | ✅ | 262K | |
| x-ai/grok-4.20 | $0.001125 | $0.077967 | ✅ | 2M | 2M ctx，但 output 貴 15 倍 |

**免費層**（$0）：`liquid/lfm-2.5-2.6b:free`（64K，最穩）、`minimax/minimax-m3.1-flash:free`（1M，**實測唯一 auto 模式下主動發 tool_call**）、`nvidia/nemotron-3-ultra-550b-a55b:free`（1M）、`nvidia/nemotron-3.5-lightning:free`（1M）、`nvidia/nemotron-3-super-120b-a12b:free`、`cohere/north-mini-code:free`、`dots-studio/dots-3-note-preview:free`、`poolside/laguna-s-2.1:free`

**function calling 實測結論**：`auto` 模式下大部分 model 唔會主動叫 tool，但 **forced `tool_choice` 全部 8 個免費 + 11 個付費 model 都回正確 tool_calls** → 能力上全部支援，淨係「主動性」有分別。`qwen/qwen3.8-flash` 強制 tool_choice 會 **HTTP 400**（唔支援 forced）。

**ctx 實測**：所有 1M ctx 免費 model 都成功接收 ~16.8K token prompt 並答對 needle（`MAGENTA-7788`）。`liquid/lfm-2.5-2.6b:free` catalog 話 64K，但實測食到 16.8K 無錯。**`minimax/minimax-m3.1-flash:free` 係唯一 auto 模式成功自發 tool_call 嘅免費 model**。

## 附錄 F · 多平台免費層核實表（2026-10-20 官方頁核實）

「可自動領取」判定標準：**平台有 API 令自動化程式可以查餘額或觸發領取**。
冇 API 嘅（要登陸 console 撳掣）→ 只能提示用戶手動做，唔好假裝可以自動領。

| 平台 | 免費層 | 額度 / 有效期 | 可自動？ | 餘額查詢 API | 備註 |
|---|---|---|---|---|---|
| **OpenRouter** | ✅ | 50 req/day（UTC），要 1,000/day 需累計充值 $10 | ✅ 自動 | `GET /api/v1/key` → `usage`/`limit`/`limit_remaining` | 免費層**限 request 數**，唔限 token |
| **WorkBuddy** | ➖ | 本身無積分，走 OpenRouter | ✅ 自動 | 本機 gateway :3001 + models.json | |
| **Kimi 國際** (platform.moonshot.ai) | ❌ | **無免費層**，要 $1 起充 | ➖ | `GET /v1/users/me/balance` → `available_balance`/`voucher_balance`/`cash_balance` | 充值滿 $5 送 $5 代金券；代金券 90 日到期 |
| **Kimi 中國** (platform.moonshot.cn) | ✅ 新戶 | 個人實名送 **¥15**（一次性） | ❌ 手動 | 同上但 base = `api.moonshot.cn/v1` | key 兩邊**唔互通**，混用 401 |
| **豆包 / 火山方舟** | ✅ | Seed-2.1-pro / 2.1-turbo / Seed-Evolving 各 **50 萬 tokens**；Seedream-4.5/4.0 各 200 張；語音合成 5000 字符；聯網 2 萬次/月。另有「協作獎勵計劃二期」**每日可領單模型最高 500 萬 Tokens** | ❌ 手動 | 官方**無餘額查詢 API**，要登 console | base = `https://ark.cn-beijing.volces.com/api/v3` |
| **MiniMax** | ❌ | **完全按量計費，無免費層、無試用 credit** | ➖ | 官方無餘額 API | M3.1-Flash 輸入 ¥1/百萬 tokens |
| **Cursor Hobby** | ✅ | 2,000 completions/月 + 50 次慢速 premium request，無需卡 | ❌ 手動 | 冇餘額 API | BYOK 要 UI 手貼（safeStorage 加密，**冇指令可代勞**） |
| **Qwen Code** | ✅ | **QwenOAuth 每日 1,000 次**（2026-02-09 由 2,000 減半） | ❌ 手動 | 本機 `~/.qwen/usage/token-usage-YYYY-MM-DD.jsonl` | 本機現時指向 OpenRouter → OAuth 額度**未啟用**；要 `qwen` 內 `/auth` 選 QwenOAuth |
| **Grok Bot roster** | ➖ | 本地 plugin，無積分；背後經 OpenRouter | ✅ 自動 | 睇 OpenRouter | xAI 官方 API 頁**無免費層明文** |
| **GitHub Models** | ❌ | 2026-07-30 全面退役 | — | — | 改用 Azure AI Foundry |
| **HF Inference Providers** | ⚠ | 免費戶 $0/月，只有 PRO 每席 $2 | — | — | Router `https://router.huggingface.co/v1` |

**自動巡檢腳本**：`scripts/claim_credits.py`（唯讀，8 平台，唔會自動購買或領取）。
**清理腳本**：`scripts/prune_dead_apis.py`（用 catalog 對比判定已廢，唔用實測 → 唔會被 429 誤殺）。

## 附錄 G · 免 key 免費層（Kilo / LLM7）— 2026-10-20 實測接入

### 背景：4 個 reference repo 審查結果

| repo | 性質 | 審查結論 | 已轉為 |
|---|---|---|---|
| `awesome-freellm-apis` | **純目錄**（513+ API、30 provider） | 無程式碼，安全。抽 base URL + model id 用 | **`free-api-directory` skill**（離線 JSON 目錄 + 查詢腳本） |
| `freellmapi` | **自架 router**（Node/Express） | 無 key 收集行為。**本機已裝**（`~/freellmapi`，port 3001） | `free-api-directory/references/self-hosted-routers.md` |
| `free-claude-code` | **自架 router**（Python，55 provider 適配層） | 無 key 收集行為 | `free-api-directory/references/self-hosted-routers.md` |
| `FreeToken` | **本地 GPU MoE 推理引擎**（290B+ 模型跑喺自己硬件） | 唔係免費 API 層，唔適用 | `free-api-directory/references/local-inference-freetoken.md` |

**安全掃描結果**：4 個 repo 全部無 webhook 投遞、無 `.env` 外傳、無憑證收集。冇安裝任何一個（只讀 source）。

**離線查目錄**（新增，唔使上網）：
```bash
cd ../free-api-directory/scripts
python query_directory.py --list           # 30 個 provider 一覽
python query_directory.py --no-card        # 只要唔使信用卡（10 個）
python query_directory.py --provider groq  # base URL / 申請入口 / 代表模型
python query_directory.py --search nemotron
```

### 實測結論：42 個供應商，只有 2 個免 key 真通

| 供應商 | base URL | 免 key | 官方條款 |
|---|---|---|---|
| **Kilo Code** | `https://api.kilo.ai/api/gateway` | ✅ **可用** | 官方明文：unauthenticated access for **free models only**，**200 req/hr/IP**。`:free` suffix 標示免費層。⚠️ **NVIDIA free endpoint 係 trial only — 唔好提交個人或機密資料**（會被記錄作改進 NVIDIA 產品） |
| **LLM7.io** | `https://api.llm7.io/v1` | ⚠️ 部分 model | 官方明文：free tier **100,000 tokens/day**、250 r/h、60 r/m、1 r/s。⚠️ 官方「collect anonymous usage data to improve the Service」。Pro 先有 function calling |
| OpenCode Zen | `https://opencode.ai/zen/v1` | ❌ | 官方：free tier **只限 OpenCode 內用**（403 FreeTierError），部分 model 香港地區不可用 |
| 其餘 39 個 | — | ❌ | 全部要個別 API key |

### 接入路徑（關鍵：唔係 WorkBuddy models.json）

WorkBuddy `models.json` **強制 apiKey 非空**（官方 asar 邏輯：`!isFilledString(e.apiKey) && !isLoopbackModelEndpoint(e.url)` → 報錯）。
所以免 key 供應商**唔可以直接寫入 models.json**。

**正確做法**：經本機 freellmapi gateway（:3001）。
- freellmapi 內建 `kilo` provider（`keyless: true`），原生支援 `no-key` sentinel
- 設定檔：`~/freellmapi/freellmapi-free-providers.json`，由 `.env` 嘅 `FREEAPI_CONFIG_PATH` 指定
- 內容格式：`{"keys":[{"platform":"kilo","label":"...","enabled":true}], "models":[{"platform":"kilo","modelId":"...","displayName":"...","contextWindow":N,"supportsTools":true}]}`
- **注意**：`platform: "llm7"` 會被 skip（該 platform 非 keyless，要 key 喺 dash.llm7.io 攞）
- **注意**：`customProviders` schema 唔支援空 apiKey（會報 `key is required for custom`）→ 必須用 `keys` + `models`

WorkBuddy 側則用 `add_gateway_models_to_workbuddy.py --apply` 加入 models.json：
- `url` = `http://127.0.0.1:3001/v1/chat/completions`
- `apiKey` = `WORKBUDDY_API_KEY`（由 `~/.dsh/.credentials.yaml` 讀，唔經命令行）
- model id 用 gateway 顯示嘅**短 id**（如 `minimax-m3.1-flash`，唔係 `minimax/minimax-m3.1-flash:free`）

### 實測結果（2026-10-20，經 WorkBuddy gateway）

**11/17 實測通，全部 `cost=0`，全部支援 function calling**：
`minimax-m3.1-flash`(1M) `nemotron-3.5-lightning`(1M) `nemotron-3-super`(1M) `nemotron-3-ultra`(1M)
`north-mini-code`(256K) `lfm-2.5-2.6b`(64K) `poolside-laguna-s-2.1`(262K) `poolside-laguna-xs-2.1`(262K)
`dots-3-note-preview`(512K) `free-router`(200K) `kilo-auto`(256K)

其餘 6 個 429 = 上游限流，唔係已廢。

### 重啟 freellmapi 嘅陷阱

`start-freellmapi.ps1` 用 `Start-Process` 起子進程 → **PowerShell session 一結束就死**。
要用 `run_in_background` 直接跑 `node server/dist/index.js` 先會持久。
另外 `Start-Process` 傳 `-Environment` 會撞 `HTTP_PROXY` / `http_proxy` 大小寫衝突 → 直接用背景工具。

### 仍然需要個別 key 嘅供應商（申請入口）

| 供應商 | base URL | 入口 | 卡片 |
|---|---|---|---|
| Groq | `https://api.groq.com/openai/v1` | console.groq.com/keys | 無需 |
| Cerebras | `https://api.cerebras.ai/v1` | cloud.cerebras.ai | 無需 |
| Mistral | `https://api.mistral.ai/v1` | console.mistral.ai/api-keys | 無需 |
| Cohere | `https://api.cohere.com/compatibility/v1` | dashboard.cohere.com/api-keys | 無需 |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | aistudio.google.com/app/apikey | 無需 |
| NVIDIA NIM | `https://integrate.api.nvidia.com/v1` | build.nvidia.com/settings/api-keys | 手機驗證 |
| Cloudflare | `https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/v1` | dash.cloudflare.com/profile/api-tokens | 無需 |
| SiliconFlow | `https://api.siliconflow.cn/v1` | cloud.siliconflow.cn/account/ak | 實名送 ¥16 |
| ModelScope | `https://api-inference.modelscope.cn/v1` | modelscope.cn/my/myaccesstoken | 免費 61 模型 |
| Z AI | `https://open.bigmodel.cn/api/paas/v4` | open.bigmodel.cn/usercenter/apikeys | 無需 |
