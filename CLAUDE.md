# CLAUDE.md — context-youtube

This file provides guidance for AI assistants (Claude Code and similar) working in this repository.

> **日本語版は下部に記載しています。**

---

## Project overview

**context-youtube** is a newly initialized project. As of the initial commit, the repository contains only this documentation file and a minimal `README.md`. The project name suggests it involves YouTube video context — likely transcript extraction, video analysis, summarization, or related tooling.

Update this section as the project matures.

## Repository structure

```
context-youtube/
├── README.md        # Project title only (to be expanded)
└── CLAUDE.md        # This file
```

As source files are added, document them here.

## Development workflow

### Branch model

- `main` — stable, always releasable
- `claude/<short-description>` — AI-driven feature branches (e.g., the branch this file was authored on)
- Feature branches should be short-lived; open a pull request and merge promptly

### Commit conventions

Use concise, imperative-mood commit messages:

```
Add transcript extraction module
Fix timestamp parsing for live streams
Refactor context window chunking logic
```

- One logical change per commit
- Do not mix formatting changes with functional changes

### Pull requests

- Always open a draft PR when pushing a feature branch
- PR title mirrors the primary commit message
- PR body should include: what changed, why, and a brief test plan

## Code conventions (to be established)

As the language and framework are not yet determined, conventions will be added here once the project stack is chosen. Common expectations regardless of stack:

- No dead code or commented-out blocks committed to `main`
- No secrets, credentials, or API keys in source files — use environment variables
- Tests live alongside the code they cover (or in a top-level `tests/` directory)
- Linting and formatting enforced via CI before merge

## Environment variables

Document required environment variables here as they are introduced. Example format:

| Variable | Required | Description |
|---|---|---|
| `YOUTUBE_API_KEY` | Yes | Google Data API v3 key for YouTube |

## Running the project

Commands will be added here once a runtime/build system is chosen.

## AI assistant notes

- This repository is in its earliest stage; no application code exists yet
- When adding the first source files, also update the "Repository structure" section above
- Prefer editing existing files over creating new ones unless a new module is genuinely needed
- Do not add speculative abstractions — implement exactly what is required
- Default branch for all development: `main`; create short-lived feature branches for each task
- After pushing any branch, open a draft pull request targeting `main`

---

# CLAUDE.md — context-youtube（日本語版）

このファイルは、このリポジトリで作業するAIアシスタント（Claude Codeなど）向けのガイドラインです。

## プロジェクト概要

**context-youtube** は新しく初期化されたプロジェクトです。初回コミット時点では、このドキュメントファイルと最小限の `README.md` のみが含まれています。プロジェクト名から、YouTube動画のコンテキスト処理（字幕抽出、動画解析、要約など）に関連するツールと推察されます。

プロジェクトが成熟したら、このセクションを更新してください。

## リポジトリ構成

```
context-youtube/
├── README.md        # プロジェクトタイトルのみ（今後拡充予定）
└── CLAUDE.md        # このファイル
```

ソースファイルが追加されたら、ここに記載してください。

## 開発ワークフロー

### ブランチ運用

- `main` — 安定版、常にリリース可能な状態を保つ
- `claude/<短い説明>` — AIが作業するフィーチャーブランチ（例：このファイルを作成したブランチ）
- フィーチャーブランチは短命に保ち、PRを作成して速やかにマージする

### コミットメッセージ規約

簡潔な命令形で記述する：

```
Add transcript extraction module
Fix timestamp parsing for live streams
Refactor context window chunking logic
```

- 1コミットにつき1つの論理的な変更
- フォーマット変更と機能変更を混在させない

### プルリクエスト

- フィーチャーブランチをプッシュしたら必ずドラフトPRを作成する
- PRタイトルはメインのコミットメッセージに合わせる
- PR本文には「何を変更したか」「なぜ変更したか」「テスト計画」を記載する

## コード規約（今後策定予定）

使用言語とフレームワークが未定のため、プロジェクトのスタックが決まり次第追記します。スタックに関わらず共通の方針：

- `main` にデッドコードやコメントアウトされたブロックをコミットしない
- ソースファイルにシークレット・認証情報・APIキーを含めない（環境変数を使用する）
- テストはテスト対象コードの隣に配置する（またはトップレベルの `tests/` ディレクトリ）
- マージ前にCIでLintとフォーマットを強制する

## 環境変数

追加される環境変数をここに記載してください。記載フォーマット例：

| 変数名 | 必須 | 説明 |
|---|---|---|
| `YOUTUBE_API_KEY` | 必須 | YouTube向けGoogle Data API v3キー |

## プロジェクトの実行方法

ランタイム・ビルドシステムが決まり次第、コマンドを追記します。

## AIアシスタント向けメモ

- このリポジトリは最初期段階であり、アプリケーションコードはまだ存在しない
- 最初のソースファイルを追加する際は、上記「リポジトリ構成」も更新する
- 本当に新しいモジュールが必要な場合を除き、既存ファイルの編集を優先する
- 投機的な抽象化を加えない — 要求されたことだけを実装する
- 全開発のデフォルトブランチは `main`；タスクごとに短命なフィーチャーブランチを作成する
- ブランチをプッシュしたら、`main` をターゲットにドラフトPRを作成する
