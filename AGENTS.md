# Global AGENTS.md

この環境では、Codexを実装担当として使用する。

## 最優先ルール

実装・修正・調査を開始する前に、必ず対象リポジトリ直下に以下のファイル構成が存在するか確認する。

```
/AGENTS.md
/CLAUDE.md
/docs/project-context.md
/docs/todo.md
/docs/decisions.md
/docs/handover.md
```

存在しない場合は、実装より先に最初のタスクとして作成する。

存在する場合は、実装前に必ず内容を確認する。

## 各ファイルの役割

- /AGENTS.md：Codex用の作業ルール
- /CLAUDE.md：Claude Code用の作業ルール
- /docs/project-context.md：プロジェクト全体の目的・現状・仕様・技術構成
- /docs/todo.md：未完了タスク・次にやること
- /docs/decisions.md：仕様変更・設計判断・技術選定の記録
- /docs/handover.md：次回作業者への引き継ぎ

## 作業開始前に整理する項目

実装前に以下を整理する。

- 現在の状態
- 完了済み
- 未完了
- 次タスク
- 制約事項
- 技術構成
- 影響範囲

## 作業順序

必ず以下の順で進める。

1. context確認
2. 影響範囲確認
3. 実装または調査
4. 動作確認
5. context更新案の出力

## 作業完了後の出力

作業完了後は、以下を必ず出力する。

- project-context.md 更新案
- todo.md 更新案
- decisions.md 更新案
  ※設計判断・仕様変更・技術選定があった場合のみ
- handover.md 更新案

## 目的

このルールの目的は、チャット履歴に依存せず、リポジトリ内のcontextファイルを中心にプロジェクトを継続管理することである。

長期プロジェクトでは、チャット履歴より /docs/project-context.md を優先する。
