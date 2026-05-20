# context-youtube — Context OS MVP

YouTube字幕を最小コスト・最高品質でLLMに渡すパイプライン。

## 設計思想

**高価なLLMは最終出力のみ。** 前処理・検索・圧縮はすべてルールベース・ローカル演算。

```
YouTube字幕
  ↓ fetch + clean + deduplicate
前処理セグメント
  ↓ sentence-transformers (ローカル, 無料)
Embedding保存 (ChromaDB local)
  ↓ BM25 + Vector → RRF融合
Hybrid Search結果
  ↓ query密度 + 位置スコア
Score-based Attention
  ↓ フィラー除去 + 低密度文削除 + トークン予算内に収める
Rule-based Compression
  ↓ タイムスタンプ付きで時系列順に整理
Prompt Assembly
  ↓ 1回のみ
Claude Sonnet (final only)
  ↓ (video_id, query) キーで24h保存
Result Cache
```

## コスト試算

| 項目 | コスト |
|------|--------|
| Embedding (sentence-transformers) | 無料 (ローカル) |
| Vector DB (ChromaDB) | 無料 (ローカル) |
| BM25検索 | 無料 |
| Claude Sonnet 1クエリ (~6500トークン) | ~¥3 |
| 月100クエリ | **~¥300** |
| 月1000クエリ | **~¥3,000** |

目標の月1,000〜5,000円に収まる。キャッシュヒット率が上がれば更に安価。

## セットアップ & 起動

### 1. APIキーを設定

```bash
cp .env.example .env
```

`.env` を編集して使いたいプロバイダのキーを設定：

```bash
# 有料 (デフォルト) — Claude Haiku + Sonnet
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# 完全無料 — Gemini 1.5 Flash
# LLM_PROVIDER=gemini
# GEMINI_API_KEY=...

# 完全無料 — Groq Llama 3.3 70B
# LLM_PROVIDER=groq
# GROQ_API_KEY=...
```

### 2. ウェブアプリとして起動

```bash
pip install -r requirements.txt
bash start.sh
```

ブラウザで **http://localhost:3000** を開く。

> または `make start` でも同じ（`make` が使えない場合は `bash start.sh`）

### CLI として使う場合

```bash
# 基本
python main.py "https://www.youtube.com/watch?v=VIDEO_ID" "この動画の主なポイントは？"

# 詳細ログ付き
python main.py VIDEO_ID "query" -v

# JSON出力
python main.py VIDEO_ID "query" --json

# 抽出済み知識ベースの確認
python main.py VIDEO_ID --inspect
```

## iPadやスマホからどこでも使う（Vercel + Render）

フロントエンドをVercel（無料）、バックエンドをRender（無料枠）にデプロイすると
どのデバイス・どのネットワークからでもアクセスできる。

> **Renderの無料枠**: 15分間アクセスがないとスリープする。次のアクセス時に30秒ほど起動に時間がかかるが、機能は問題ない。

### Step 1 — バックエンドをRenderにデプロイ

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Fornus-debug/context-youtube)

ボタンをクリック後、「Environment Variables」で以下を設定：

```
LLM_PROVIDER=anthropic          # or gemini / groq
ANTHROPIC_API_KEY=sk-ant-...    # 選んだプロバイダのキー
ALLOWED_ORIGINS=https://your-app.vercel.app  # ← Step 2で決まるURL（後で更新可）
```

デプロイ完了後に表示されるURL（例: `https://context-youtube-api.onrender.com`）をコピー。

### Step 2 — フロントエンドをVercelにデプロイ

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2FFornus-debug%2Fcontext-youtube&root-directory=frontend&env=BACKEND_URL&envDescription=Render%E3%83%90%E3%83%83%E3%82%AF%E3%82%A8%E3%83%B3%E3%83%89%E3%81%AEURL%20%28%E4%BE%8B%3A%20https%3A%2F%2Fxxx.onrender.com%29&project-name=context-youtube&repository-name=context-youtube)

ボタンをクリック → `BACKEND_URL` にStep 1のRenderのURLを入力 → Deploy。

デプロイ完了後のURL（例: `https://your-app.vercel.app`）をRenderの `ALLOWED_ORIGINS` に設定して再デプロイ。

### 完成

`https://your-app.vercel.app` をiPadのSafariで開いて「ホーム画面に追加」すると
アプリのように使えます。

---

## ファイル構成

```
src/
  transcript.py   # 字幕取得・クリーニング・チャンク分割
  embeddings.py   # ローカルEmbedding生成・ChromaDB永続化
  search.py       # Hybrid Search (BM25 + Vector, RRF融合)
  compression.py  # Score-based Attention + Rule-based Compression
  prompt.py       # Prompt Assembly + コスト推定
  cache.py        # ディスクキャッシュ (diskcache)
  pipeline.py     # パイプライン統合
main.py           # CLIエントリポイント
tests/            # ユニットテスト (22件)
```

## チューニング

`.env` で調整可能なパラメータ:

| 変数 | デフォルト | 説明 |
|------|-----------|------|
| `LLM_PROVIDER` | `anthropic` | `anthropic` / `gemini` / `groq` |
| `CONTEXT_BUDGET_TOKENS` | 6000 | LLMに渡す最大トークン数 |
| `CACHE_TTL_SECONDS` | 86400 | キャッシュ有効期間 (秒) |
| `EMBEDDING_MODEL` | all-MiniLM-L6-v2 | Sentence Transformersモデル |
| `EXTRACT_MODEL` | (プロバイダ依存) | 知識抽出用モデルの上書き |
| `ANSWER_MODEL` | (プロバイダ依存) | 回答生成用モデルの上書き |

## テスト

```bash
python -m pytest tests/ -v
```
