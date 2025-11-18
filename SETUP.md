# セットアップ手順

## 1. GitHub Personal Access Token の作成

1. [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens) にアクセス
2. "Generate new token (classic)" をクリック
3. 設定:
   - Note: `github-to-calendar`
   - Expiration: 任意（長期運用なら90日以上推奨）
   - Scopes: `repo` にチェック
4. "Generate token" をクリックしてトークンをコピー

## 2. Google Calendar API の設定

### 2.1 プロジェクト作成
1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 新規プロジェクトを作成（例: `github-to-calendar`）

### 2.2 Calendar API 有効化
1. "APIs & Services" > "Enable APIs and Services"
2. "Google Calendar API" を検索して有効化

### 2.3 サービスアカウント作成
1. "APIs & Services" > "Credentials"
2. "Create Credentials" > "Service Account"
3. 名前を入力して作成
4. 作成したサービスアカウントをクリック
5. "Keys" タブ > "Add Key" > "Create new key"
6. JSON を選択してダウンロード

### 2.4 カレンダー共有設定
1. Google Calendar を開く
2. 対象カレンダーの設定 > "Share with specific people"
3. サービスアカウントのメールアドレス（`xxx@xxx.iam.gserviceaccount.com`）を追加
4. 権限: "Make changes to events"

### 2.5 カレンダーID の確認
1. カレンダー設定 > "Integrate calendar"
2. "Calendar ID" をコピー（例: `xxxxx@group.calendar.google.com`）

## 3. GitHub Secrets の設定

リポジトリの Settings > Secrets and variables > Actions で以下を追加:

| Secret名 | 値 |
|----------|-----|
| `GH_PAT` | GitHub Personal Access Token |
| `GOOGLE_CREDENTIALS` | サービスアカウントJSONをBase64エンコードした文字列 |
| `CALENDAR_ID` | Google Calendar ID |

### Base64 エンコード方法

```bash
# macOS/Linux
cat credentials.json | base64

# Windows (PowerShell)
[Convert]::ToBase64String([IO.File]::ReadAllBytes("credentials.json"))
```

## 4. 動作確認

1. Actions タブを開く
2. "Daily GitHub to Calendar Sync" を選択
3. "Run workflow" で手動実行
4. ログを確認

## トラブルシューティング

### "No matching event found"
- 対象日にタイトルが数字のみのイベントが存在するか確認
- カレンダーがサービスアカウントと共有されているか確認

### "Permission denied"
- サービスアカウントの権限が "Make changes to events" になっているか確認
- Calendar API が有効になっているか確認

### "No activities found"
- 前日にGitHub活動があったか確認
- `GH_PAT` のスコープに `repo` が含まれているか確認
