# CLAUDE.md

Claude Code用の作業ルール。

## 最優先ルール

実装・修正・調査を開始する前に、必ず以下のファイルを確認する。

- /docs/project-context.md
- /docs/todo.md
- /docs/decisions.md
- /docs/handover.md

## 作業順序

1. context確認（上記ファイル）
2. 影響範囲確認
3. 実装または調査
4. 動作確認
5. context更新案の出力

## 作業完了後の出力

作業完了後は、以下の更新案を出力する。

- project-context.md 更新案
- todo.md 更新案
- decisions.md 更新案（設計判断・仕様変更があった場合のみ）
- handover.md 更新案

## 目的

チャット履歴に依存せず、リポジトリ内のcontextファイルを中心にプロジェクトを継続管理する。
長期プロジェクトでは、チャット履歴より /docs/project-context.md を優先する。
