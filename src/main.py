#!/usr/bin/env python3
"""
GitHub活動をGoogleカレンダーに記録するスクリプト
"""

import os
import sys
import json
import base64
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

from github import Github, GithubException
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# .envファイルから環境変数を読み込む
load_dotenv()


def get_github_activities(token: str, target_date: datetime) -> tuple[dict[str, list[str]], str]:
    """
    指定日のGitHub活動を取得（Search API使用）
    Returns: (activities, error)
    """
    try:
        g = Github(token, per_page=100)
        user = g.get_user()
        username = user.login
    except GithubException as e:
        return {}, f"GitHub auth failed: {e}"

    activities: dict[str, list[str]] = {}
    
    start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    date_str = target_date.strftime("%Y-%m-%d")

    try:
        # 1. Search APIでコミットを検索
        commit_query = f"author:{username} author-date:{date_str}"
        commits = g.search_commits(query=commit_query)

        commit_count = 0
        repo_commits = {}

        for commit in commits:
            commit_count += 1
            parts = commit.html_url.split('/')
            repo_name = parts[4]  # リポジトリ名のみ

            if repo_name not in repo_commits:
                repo_commits[repo_name] = []

            msg = commit.commit.message.split('\n')[0][:80] # 少し長めに取得
            repo_commits[repo_name].append(msg)

        print(f"Debug: Found {commit_count} commits for {date_str}")
        
        # コミット情報の整形
        for repo_name, msgs in repo_commits.items():
            if repo_name not in activities:
                activities[repo_name] = []
            
            total_commits = len(msgs)
            
            # 代表的なコミットを選定 (feat/fix優先)
            # 優先度: feat > fix > その他
            feat_commits = [m for m in msgs if m.lower().startswith('feat')]
            fix_commits = [m for m in msgs if m.lower().startswith('fix')]
            other_commits = [m for m in msgs if not m.lower().startswith(('feat', 'fix'))]
            
            selected_msgs = []
            # featから最大2つ
            selected_msgs.extend(feat_commits[:2])
            
            # 足りなければfixから
            if len(selected_msgs) < 2:
                selected_msgs.extend(fix_commits[:2 - len(selected_msgs)])
                
            # まだ足りなければその他から
            if len(selected_msgs) < 2:
                selected_msgs.extend(other_commits[:2 - len(selected_msgs)])
            
            # それでも空なら(あり得ないはずだが)先頭を入れる
            if not selected_msgs and msgs:
                selected_msgs.append(msgs[0])

            # 出力フォーマット作成
            # 例: - 5 commits: feat: xxx, fix: yyy
            summary_text = f"{total_commits} commits"
            details = ", ".join(selected_msgs)
            activities[repo_name].append(f"- {summary_text}: {details}")

        # 2. Search APIでPull Requestsを検索 (作成 or マージ)
        # Note: OR検索はサポートされていない場合があるため、2回検索してマージする
        pr_queries = [
            f"author:{username} type:pr created:{date_str}",
            f"author:{username} type:pr merged:{date_str}"
        ]
        
        seen_prs = set()
        pr_count = 0
        
        for query in pr_queries:
            prs = g.search_issues(query=query)
            for pr in prs:
                if pr.number in seen_prs:
                    continue
                seen_prs.add(pr.number)
                pr_count += 1

                repo_name = pr.repository.name  # リポジトリ名のみ
                if repo_name not in activities:
                    activities[repo_name] = []

                events = []
                # Created判定
                if pr.created_at and start <= pr.created_at < end:
                    events.append("(created)")
                
                # Merged判定
                # Note: search_issuesの戻り値はIssueオブジェクトなので、正確なマージ情報を得るにはPullRequestオブジェクトが必要
                if pr.state == "closed" and pr.closed_at and start <= pr.closed_at < end:
                    try:
                        # 必要な場合のみ詳細を取得 (API call)
                        detailed_pr = pr.as_pull_request()
                        if detailed_pr.merged and detailed_pr.merged_at and start <= detailed_pr.merged_at < end:
                            events.append("(merged)")
                    except Exception:
                        # 権限エラー等は無視
                        pass
                
                for event_type in events:
                    activities[repo_name].append(f"- PR #{pr.number}: {pr.title} {event_type}")

        print(f"Debug: Found {pr_count} pull requests (unique) for {date_str}")

        # 3. Search APIでIssuesを検索 (作成 or クローズ)
        issue_queries = [
            f"author:{username} type:issue created:{date_str}",
            f"author:{username} type:issue closed:{date_str}"
        ]
        
        seen_issues = set()
        issue_count = 0
        
        for query in issue_queries:
            issues = g.search_issues(query=query)
            for issue in issues:
                if issue.number in seen_issues:
                    continue
                seen_issues.add(issue.number)
                issue_count += 1

                repo_name = issue.repository.name  # リポジトリ名のみ
                if repo_name not in activities:
                    activities[repo_name] = []

                events = []
                if issue.created_at and start <= issue.created_at < end:
                    events.append("(created)")
                
                if issue.state == "closed" and issue.closed_at and start <= issue.closed_at < end:
                    events.append("(closed)")
                
                for event_type in events:
                    activities[repo_name].append(f"- Issue #{issue.number}: {issue.title} {event_type}")

        print(f"Debug: Found {issue_count} issues (unique) for {date_str}")

    except GithubException as e:
        return {}, f"Failed to search activities: {e}"

    return activities, ""


def format_activities(activities: dict[str, list[str]], target_date: datetime) -> str:
    """活動をプレーンテキスト形式にフォーマット"""
    if not activities:
        return ""

    lines = [f"GitHub Activity ({target_date.strftime('%Y-%m-%d')})", ""]

    for repo_name, items in sorted(activities.items()):
        lines.append(f"[{repo_name}]")
        lines.extend(items)
        lines.append("")

    return "\n".join(lines)


def count_activities(activities: dict[str, list[str]]) -> int:
    """活動の総数をカウント"""
    return sum(len(items) for items in activities.values())


def get_color_id(activity_count: int) -> str:
    """活動数に応じた色IDを返す"""
    if activity_count == 0:
        return "8"  # グレー
    elif activity_count <= 3:
        return "9"  # 青
    elif activity_count <= 10:
        return "10"  # 緑
    elif activity_count <= 20:
        return "6"  # オレンジ
    else:
        return "11"  # 赤


def update_calendar(credentials_json: str, calendar_id: str, target_date: datetime, content: str, activities: dict[str, list[str]]) -> str:
    """
    カレンダーイベントの説明欄を更新
    Returns: error message (empty if success)
    """
    # 活動数を計算して色を決定
    activity_count = count_activities(activities)
    color_id = get_color_id(activity_count)
    # 認証
    try:
        creds_dict = json.loads(base64.b64decode(credentials_json))
    except Exception as e:
        return f"Failed to decode credentials: {e}"

    try:
        creds = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/calendar"]
        )
        service = build("calendar", "v3", credentials=creds)
    except Exception as e:
        return f"Failed to create calendar service: {e}"

    # 対象日のイベントを検索
    start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    try:
        events = service.events().list(
            calendarId=calendar_id,
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True
        ).execute()
    except HttpError as e:
        return f"Failed to list events: {e}"

    # タイトルが"GitHub"のイベントを探す
    for event in events.get("items", []):
        title = event.get("summary", "")
        if title != "GitHub":
            continue

        # 説明欄に追記 + 色を更新
        current_desc = event.get("description", "")
        separator = "\n\n---\n\n" if current_desc else ""
        event["description"] = current_desc + separator + content
        event["colorId"] = color_id

        try:
            service.events().update(
                calendarId=calendar_id,
                eventId=event["id"],
                body=event
            ).execute()
        except HttpError as e:
            return f"Failed to update event: {e}"

        print(f"Updated event: {title}")
        return ""

    # イベントがない場合は新規作成
    date_str = target_date.strftime("%Y-%m-%d")
    new_event = {
        "summary": "GitHub",
        "description": content,
        "start": {"date": date_str},
        "end": {"date": date_str},
        "colorId": color_id,
    }

    try:
        created = service.events().insert(
            calendarId=calendar_id,
            body=new_event
        ).execute()
        print(f"Created event: {date_str}")
        return ""
    except HttpError as e:
        return f"Failed to create event: {e}"


def main() -> int:
    """
    メイン処理
    Returns: exit code (0: success, 1: error)
    """
    # 環境変数
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        print("Error: GITHUB_TOKEN not set", file=sys.stderr)
        return 1

    google_creds = os.environ.get("GOOGLE_CREDENTIALS")
    if not google_creds:
        print("Error: GOOGLE_CREDENTIALS not set", file=sys.stderr)
        return 1

    calendar_id = os.environ.get("CALENDAR_ID")
    if not calendar_id:
        print("Error: CALENDAR_ID not set", file=sys.stderr)
        return 1

    timezone = os.environ.get("TIMEZONE", "Asia/Tokyo")
    tz = ZoneInfo(timezone)

    # 対象日（TARGET_DATE指定 or 前日）
    target_date_str = os.environ.get("TARGET_DATE")
    if target_date_str:
        try:
            target_date = datetime.strptime(target_date_str, "%Y-%m-%d").replace(tzinfo=tz)
        except ValueError:
            print(f"Error: Invalid TARGET_DATE format: {target_date_str} (expected YYYY-MM-DD)", file=sys.stderr)
            return 1
    else:
        target_date = datetime.now(tz) - timedelta(days=1)

    print(f"Fetching activities for {target_date.strftime('%Y-%m-%d')}")

    # 活動取得
    activities, err = get_github_activities(github_token, target_date)
    if err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    if not activities:
        print("No activities found")
        return 0

    # フォーマット
    content = format_activities(activities, target_date)
    print(content)

    # カレンダー更新
    err = update_calendar(google_creds, calendar_id, target_date, content, activities)
    if err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
