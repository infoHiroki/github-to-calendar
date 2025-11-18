# GitHub to Calendar

> 基本設計原則は `~/.claude/CLAUDE.md` を参照

GitHubの日次活動をGoogleカレンダーのジャーナリングイベントに自動記録するシステム。

## 技術スタック

- Python 3.11+
- GitHub Actions (毎日 7:00 JST)
- PyGithub, google-api-python-client

## 構成

- `src/main.py` - メインスクリプト
- `.github/workflows/daily-sync.yml` - スケジュール実行

## 開発コマンド

```bash
# 依存関係インストール
pip install -r requirements.txt

# ローカル実行
python src/main.py
```

## 環境変数

- `GITHUB_TOKEN` - GitHub PAT (repo スコープ)
- `GOOGLE_CREDENTIALS` - サービスアカウントJSON (Base64)
- `CALENDAR_ID` - 対象カレンダーID
