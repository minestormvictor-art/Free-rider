# 本地推理（FreeToken）— 零 API 費嘅另一條路

**FreeToken 唔係免費 API provider。** 佢係一個 edge-native MoE 推理引擎 —— 將 290B+ frontier 級 open-weight MoE 模型跑喺你自己嘅消費級硬件（ gaming PC / laptop / 工作站 GPU）上。

**點解要留意**：當你想避開「免費層 50 次/日」呢類限額、又唔想付 API 費、又想唔使將資料送出去 —— 本地推理係答案。代價係要自己嘅 GPU、磁碟、ram。

## 核心賣點

| 特性 | 內容 |
|---|---|
| **Edge-native runtime** | 頻寬自適應 CPU–GPU 協同執行（$q^\star$ policy）、全層雙緩衝 prefill streaming、全域 LRU expert cache、graph-compatible execution、FTW fast weight format |
| **Semantic-aware caching** | 語意 anchor checkpoint 處理 recurrent state 同 KV cache —— agentic context edit（tool call、thinking block）唔使重算 context |
| **Elastic memory** | 執行中動態重新分配 VRAM（expert cache ↔ KV memory），**唔使重啟引擎、唔使重載權重** |
| **支援模型** | DeepSeek-V4-Flash、Qwen3.6-35B-A3B、GLM-5.2 等，跨 MXFP4 / NVFP4 / FP8 / BF16 |
| **硬件** | 原生支援 NVIDIA RTX 30 / 40 / 50 系列；亦可用 CPU、主機記憶體、互連 |

## API 相容性

FreeToken 同時服務：

- **OpenAI API**：`/v1/chat/completions`、`/v1/responses`、`/v1/models`
- **Anthropic API**：`/v1/messages`、`/v1/messages/count_tokens`

→ 任何 OpenAI 或 Anthropic client library 都可以淨係改 base URL 就接上。

## 安裝

```bash
# 推薦 uv
uv pip install "freetoken[accel]"

# 或者由 source
git clone https://github.com/FlashML-org/FreeToken.git && cd FreeToken
uv venv && source .venv/bin/activate
uv pip install -e ".[accel]"
```

桌面版（Windows / Linux）：<https://www.flashml.ai/> —— 自動配置引擎 + GUI（跑模型、傾偈、調參）。

## 快速開始

```bash
ft serve --model ~/models/Qwen3.6-35B-A3B
```

`--model` 亦接受 Hugging Face repo id。dtype、attention / MoE backend、cache 大小、tool-call 同 reasoning parser 全部由 checkpoint 同 GPU 自動解析。

Server ready 標誌（日誌）：`API server is ready to serve on 127.0.0.1:1919`

```bash
# 睇服務緊咩
curl http://127.0.0.1:1919/v1/models

# 發請求
curl http://127.0.0.1:1919/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"Qwen3.6-35B-A3B","messages":[{"role":"user","content":"What is a Mixture-of-Experts model?"}],"max_tokens":256,"stream":true}'
```

## Terminal 對話

```bash
ft shell                                    # attach 去上面個 server
ft shell --model ~/models/Qwen3.6-35B-A3B   # 一個 process 開引擎 + 傾偈
```

`/help` 睇 shell 內指令。**attach mode 唔使 GPU**，所以可以驅動另一部機嘅 server（`--server URL`）。

## 一鍵接 coding agent

```bash
ft launch claude   # claude / codex / dsh / hermes / openclaw / opencode
```

會寫好該 agent 嘅 provider config、缺 CLI 就裝埋、然後對住你個 server 啟動。`--dry-run` 可以先睇改乜。

## 支援模型清單

FreeToken 直接載入 HF safetensors checkpoints。以下係**已知良好**（預編譯 kernel 專為佢哋調校）：

| 模型 | HF checkpoints |
|---|---|
| DeepSeek-V4 | `deepseek-ai/DeepSeek-V4-Flash-0731` |
| GLM-5.3-Flash | `RedHatAI/GLM-5.3-Flash-NVFP4` |
| GLM-5.2 | `nvidia/GLM-5.2-NVFP4` |
| GLM-4.7 | `nvidia/GLM-4.7-NVFP4` |
| Qwen3.8-Flash-Next | `Qwen/Qwen3.8-Flash-Next-FP8` / `RadixArk/Qwen3.8-Flash-Next-NVFP4` / `nvidia/Qwen3.8-Flash-Next-NVFP4` |
| Qwen3.6 / Qwen3.5 MoE | `Qwen/Qwen3.6-35B-A3B`（-FP8）/ `nvidia/Qwen3.6-35B-A3B-NVFP4` / `Qwen/Qwen3.5-35B-A3B`（-FP8）/ `nvidia/Qwen3.5-35B-A3B-NVFP4` |
| Qwen3.8 / Qwen3.6 dense | `Qwen/Qwen3.8-27B`（-FP8）/ `RadixArk/Qwen3.8-27B-NVFP4` / `nvidia/Qwen3.8-27B-NVFP4` / `Qwen/Qwen3.6-27B`（-FP8）/ `nvidia/Qwen3.6-27B-NVFP4` |
| Qwen3-MoE | `Qwen/Qwen3-30B-A3B` |
| Qwen3-VL | `Qwen/Qwen3-VL-8B-Instruct` / `Qwen/Qwen3-VL-30B-A3B-Instruct` |
| gpt-oss | `openai/gpt-oss-120b` / `openai/gpt-oss-20b` |
| Gemma-4 | `google/gemma-4-26B-A4B-it` / `nvidia/Gemma-4-26B-A4B-NVFP4` / `google/gemma-4-12B-it` / `nvidia/Gemma-4-31B-IT-NVFP4` |
| MiniMax-M2.5 | `nvidia/MiniMax-M2.5-NVFP4` |
| MiniMax-M3 | `nvidia/MiniMax-M3-NVFP4` |
| Muse-Glimmer | `meta-models/Muse-Glimmer-30B` / `RedHatAI/Muse-Glimmer-30B-NVFP4` |

其他同架構 checkpoint 通常都 work（預編譯 kernel 只係針對以上調校）。

## 影像輸入

呢啲 family 預設接受影像輸入；想跳過 vision encoder 就加 `--text-model-only`。

| Family | Image tokens | 參數 |
|---|---|---|
| Qwen3.6（全部變體、所有 weight format）、Qwen3.8-Flash-Next、Qwen3-VL | resize 後每 32×32 像素一個 token，動態解析度 | `--image-min-tokens` / `--image-max-tokens`；`--mm-processor-kwargs` 例：`{"size":{"longest_edge":1048576}}` |
| Gemma-4 26B-A4B / 31B（`gemma4`：ViT tower，streamed，`--mm-encoder-weights host`） | soft-token 預算 70 / 140 / 280 / 560 / 1120，每張圖縮放到預算 | `--mm-processor-kwargs` 例：`{"max_soft_tokens":1120}` |
| Gemma-4 12B（`gemma4_unified`：linear patch embedder，resident） | 同上預算，48×48 super-patch 每 soft token | 同上 |

各 family 用自己嘅單位讀 flag。

## 本機硬件現實檢查

用戶本機：**HP ProBook 440 G10，i5-1335U，32 GB RAM，NVMe SSD**（無獨顯）。

→ 呢部機**跑唔到** 290B MoE 級模型。FreeToken 對呢部機嚟講係「架構參考」而唔係「即刻可用」。

可行替代：用較細嘅 dense 模型（Qwen3.8-27B、Qwen3-VL-8B-Instruct、gpt-oss-20b）+ 量化（NVFP4/FP8），
但要 32 GB RAM 兼顯存，就屬於勉強試水範圍。

**結論**：FreeToken 對呢部筆電唔構成即時可攞嘅「免費」方案；
真正喺本機即刻生效嘅免費方案，仍然係**本機 freellmapi gateway + Kilo 免 key 層**（見 `self-hosted-routers.md`）。

## 相關文件（source zip 內）

- `docs/install.md` — 安裝
- `docs/quickstart.md` — 快速開始
- `docs/models.md` — 支援模型
- `docs/cli.md` — CLI 參數
- `docs/ftw-hotfix.md` — 修復舊 FTW checkpoint
- `python/freetoken/daemon/README.md` — daemon
- `tests/kvcache/radix/README.md` — radix KV cache

論文：arXiv 2608.16157（*FreeToken: Efficient Edge-Native MoE Serving with Bandwidth-Adaptive Execution*）
