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

## セットアップ

```bash
pip install -r requirements.txt
cp .env.example .env
# .env に ANTHROPIC_API_KEY を設定
```

## 使い方

```bash
# 基本
python main.py "https://www.youtube.com/watch?v=VIDEO_ID" "この動画の主なポイントは何ですか？"

# タイトル指定 + 詳細出力
python main.py dQw4w9WgXcQ "What does the speaker discuss?" --title "My Video" -v

# JSON出力
python main.py VIDEO_ID "query" --json

# キャッシュ無視して再取得
python main.py VIDEO_ID "query" --refresh
```

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
| `CONTEXT_BUDGET_TOKENS` | 6000 | LLMに渡す最大トークン数 |
| `CACHE_TTL_SECONDS` | 86400 | キャッシュ有効期間 (秒) |
| `EMBEDDING_MODEL` | all-MiniLM-L6-v2 | Sentence Transformersモデル |
| `CLAUDE_MODEL` | claude-sonnet-4-6 | 使用するClaudeモデル |

## テスト

```bash
python -m pytest tests/ -v
```
