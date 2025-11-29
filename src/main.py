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
    except GithubException as e:
        return {}, f"GitHub auth failed: {e}"

    activities: dict[str, list[str]] = {}
    username = user.login

    start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    date_str = target_date.strftime("%Y-%m-%d")

    try:
        # 1. Search APIでコミットを検索 (author-dateとcommitter-dateの両方)
        # GitHubの貢献グラフに表示されるのはauthor-dateベース
        commit_query = f"author:{username} author-date:{date_str}"
        commits = g.search_commits(query=commit_query)

        commit_count = 0
        for commit in commits:
            commit_count += 1
            # html_urlから抽出:リポジトリ名を取得 https://github.com/owner/repo/commit/sha
            parts = commit.html_url.split('/')
            repo_name = f"{parts[3]}/{parts[4]}"

            if repo_name not in activities:
                activities[repo_name] = []

            msg = commit.commit.message.split('\n')[0][:50]
            activities[repo_name].append(f"- {msg} (commit)")

        print(f"Debug: Found {commit_count} commits for {date_str}")

        # 2. Search APIでPull Requestsを検索
        pr_query = f"author:{username} created:{date_str} type:pr"
        prs = g.search_issues(query=pr_query)

        pr_count = 0
        for pr in prs:
            pr_count += 1
            repo_name = pr.repository.full_name
            if repo_name not in activities:
                activities[repo_name] = []

            # PRの状態を確認
            if pr.state == "closed" and pr.pull_request:
                # merged_at属性が存在するか確認
                merged_at = getattr(pr.pull_request, 'merged_at', None)
                if merged_at and start <= merged_at < end:
                    activities[repo_name].append(f"- PR #{pr.number}: {pr.title} (merged)")
                else:
                    activities[repo_name].append(f"- PR #{pr.number}: {pr.title} (created)")
            else:
                activities[repo_name].append(f"- PR #{pr.number}: {pr.title} (created)")

        print(f"Debug: Found {pr_count} pull requests for {date_str}")

        # 3. Search APIでIssuesを検索
        issue_query = f"author:{username} created:{date_str} type:issue"
        issues = g.search_issues(query=issue_query)

        issue_count = 0
        for issue in issues:
            issue_count += 1
            repo_name = issue.repository.full_name
            if repo_name not in activities:
                activities[repo_name] = []

            # Issueの状態
            if issue.state == "closed" and issue.closed_at and start <= issue.closed_at < end:
                activities[repo_name].append(f"- Issue #{issue.number}: {issue.title} (closed)")
            else:
                activities[repo_name].append(f"- Issue #{issue.number}: {issue.title} (created)")

        print(f"Debug: Found {issue_count} issues for {date_str}")

    except GithubException as e:
        return {}, f"Failed to search activities: {e}"

    return activities, ""


def get_commits(repo, author: str, start: datetime, end: datetime) -> tuple[list[str], str]:
    """コミット一覧を取得"""
    try:
        commits = repo.get_commits(author=author, since=start, until=end)
        results = []
        for commit in commits:
            msg = commit.commit.message.split('\n')[0][:50]
            results.append(f"- {msg} (commit)")
        return results, ""
    except GithubException as e:
        return [], str(e)


def get_pull_requests(repo, start: datetime, end: datetime) -> tuple[list[str], str]:
    """PR一覧を取得"""
    try:
        prs = repo.get_pulls(state="all", sort="updated", direction="desc")
        results = []
        for pr in prs:
            # 古いPRはスキップ
            if pr.updated_at < start:
                break
            if pr.created_at and start <= pr.created_at < end:
                results.append(f"- PR #{pr.number}: {pr.title} (created)")
            if pr.merged_at and start <= pr.merged_at < end:
                results.append(f"- PR #{pr.number}: {pr.title} (merged)")
        return results, ""
    except GithubException as e:
        return [], str(e)


def get_issues(repo, start: datetime, end: datetime) -> tuple[list[str], str]:
    """Issue一覧を取得"""
    try:
        issues = repo.get_issues(state="all", sort="updated", direction="desc")
        results = []
        for issue in issues:
            if issue.pull_request:
                continue
            # 古いissueはスキップ
            if issue.updated_at < start:
                break
            if issue.created_at and start <= issue.created_at < end:
                results.append(f"- Issue #{issue.number}: {issue.title} (created)")
            if issue.closed_at and start <= issue.closed_at < end:
                results.append(f"- Issue #{issue.number}: {issue.title} (closed)")
        return results, ""
    except GithubException as e:
        return [], str(e)


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


def update_calendar(credentials_json: str, calendar_id: str, target_date: datetime, content: str) -> str:
    """
    カレンダーイベントの説明欄を更新
    Returns: error message (empty if success)
    """
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

    # タイトルが数字のみのイベントを探す
    for event in events.get("items", []):
        title = event.get("summary", "")
        if not title.isdigit():
            continue

        # 説明欄に追記
        current_desc = event.get("description", "")
        separator = "\n\n---\n\n" if current_desc else ""
        event["description"] = current_desc + separator + content

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
        "summary": date_str,
        "description": content,
        "start": {"date": date_str},
        "end": {"date": date_str},
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
    err = update_calendar(google_creds, calendar_id, target_date, content)
    if err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
