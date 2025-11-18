# GitHub to Calendar

GitHubの活動内容を自動的にGoogleカレンダーのジャーナリングイベントに記録するシステム。

## 概要

- **実行タイミング**: 毎日 7:00 (JST) に前日の活動をまとめて送信
- **記録内容**: commit、PR、issue などの活動サマリー
- **書き込み先**: タイトルが数字のみの既存イベントの説明欄に追記

## アーキテクチャ

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  GitHub Actions │────▶│ Python Script │────▶│ Google Calendar │
│  (Scheduler)    │     │              │     │      API        │
└─────────────────┘     └──────────────┘     └─────────────────┘
                              │
                              ▼
                        ┌──────────────┐
                        │  GitHub API  │
                        │ (活動取得)    │
                        └──────────────┘
```

## ディレクトリ構成

```
github-to-calendar/
├── .github/workflows/daily-sync.yml  # GitHub Actions
├── src/main.py                       # メインスクリプト
├── requirements.txt
├── README.md
└── SETUP.md                          # セットアップ手順
```

## 必要な認証情報

### GitHub Personal Access Token
- **スコープ**: `repo` (全リポジトリ読み取り)
- **保存先**: GitHub Secrets (`GITHUB_TOKEN`)

### Google Calendar API
- **認証方式**: サービスアカウント
- **必要な権限**: カレンダーの読み取り・書き込み
- **保存先**: GitHub Secrets (`GOOGLE_CREDENTIALS`)

## 処理フロー

1. **活動取得** (GitHub API)
   - 前日の commit 一覧を取得
   - 前日の PR (作成・マージ) を取得
   - 前日の issue (作成・クローズ) を取得

2. **フォーマット**
   - Logseq風の箇条書き形式に整形
   - リポジトリごとにグループ化

3. **カレンダー更新** (Google Calendar API)
   - 対象日のイベントを検索（タイトルが数字のみ）
   - 説明欄に活動内容を追記

## 出力例

```
## GitHub Activity (2024-01-15)

### user/project-a
- feat: ユーザー認証機能を追加 (commit)
- PR #12: ログイン画面の実装 (merged)

### user/project-b
- fix: バグ修正 (commit)
- Issue #5: パフォーマンス改善 (closed)
```

## 環境変数

| 変数名 | 説明 |
|--------|------|
| `GITHUB_TOKEN` | GitHub Personal Access Token |
| `GOOGLE_CREDENTIALS` | Google サービスアカウント JSON (Base64) |
| `CALENDAR_ID` | 対象の Google Calendar ID |
| `TIMEZONE` | タイムゾーン (default: `Asia/Tokyo`) |

## ローカル開発

```bash
# 依存関係インストール
pip install -r requirements.txt

# 環境変数設定
export GITHUB_TOKEN="your_token"
export GOOGLE_CREDENTIALS="base64_encoded_json"
export CALENDAR_ID="your_calendar_id"

# 実行
python src/main.py
```

## ライセンス

MIT
