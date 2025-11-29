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
   - 前日の commit を取得（範囲クエリ）
   - 前日の PR (作成・マージ) を取得（両方を検索）
   - 前日の issue (作成・クローズ) を取得（両方を検索）

2. **フォーマット**
   - コミット数を集計し、主要なコミット（最大2件）を選定
   - リポジトリごとにグループ化
   - PR/Issueを追記

3. **カレンダー更新** (Google Calendar API)
   - 対象日のイベントを検索（タイトルが数字のみ）
   - 説明欄に活動内容を追記
   - 見つからない場合は新規作成（YYYY-MM-DD形式）

## 出力例

```
GitHub Activity (2024-01-15)

[user/project-a]
- 5 commits: feat: ユーザー認証機能を追加, fix: ログインバグ修正
- PR #12: ログイン画面の実装 (merged)

[user/project-b]
- 3 commits: fix: バグ修正, docs: README更新
- Issue #5: パフォーマンス改善 (closed)
```

**コミットの表示ルール**:
- リポジトリごとにコミット数を集計
- 主要なコミット（最大2件）のみを表示
- 優先順位: `feat` > `fix` > その他

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
