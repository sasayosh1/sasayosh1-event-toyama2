"""Synchronise Toyama event information to Google Calendar.

Run `python gcal_sync.py` after setting up Google OAuth credentials.
Requires `credentials.json` in the same directory (generated from Google
Cloud Console OAuth client ID) and the SQLite DB `events.db` will be
created/updated automatically.
"""

from __future__ import annotations

import os
import base64
import hashlib
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

import scrape

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CAL_ID = "primary"  # Change if you want to use a secondary calendar
DB_PATH = Path(__file__).with_name("events.db")


def _auth():
    """Return authorised Google Calendar service.

    CI 環境ではブラウザが使えないため、事前に取得した token.json を利用する。
    ローカル実行で token.json が無ければブラウザフローを走らせて生成する。"""
    # token.json の内容を環境変数から取得
    token_b64 = os.getenv("GOOGLE_TOKEN_B64")
    if token_b64:
        token_json = base64.b64decode(token_b64).decode("utf-8")
        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
        return build("calendar", "v3", credentials=creds)

    # credentials.json の内容を環境変数から取得
    creds_b64 = os.getenv("GOOGLE_CREDENTIALS_B64")
    if not creds_b64:
        raise SystemExit("GOOGLE_TOKEN_B64 or GOOGLE_CREDENTIALS_B64 not found in environment variables.")

    creds_json = base64.b64decode(creds_b64).decode("utf-8")
    flow = InstalledAppFlow.from_client_secrets_info(json.loads(creds_json), SCOPES)
    creds = flow.run_local_server(port=0)
    
    # Save for reuse (optional, for local development)
    # token_path.write_text(creds.to_json())
    return build("calendar", "v3", credentials=creds)


def _ensure_db(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            key TEXT PRIMARY KEY,
            gcal_id TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _event_key(ev: dict) -> str:
    raw = f"{ev['title']}{ev['start']}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _event_body(ev: dict) -> dict:
    # Google Calendar API の all-day イベントは end.date が "終了日の翌日" である必要がある
    # ev["start"] は date オブジェクトを想定
    start_date = ev["start"]
    end_date = ev.get("end")

    if end_date is None or end_date == start_date:
        # 終日イベントの場合、終了日は開始日の翌日
        end_date = start_date + timedelta(days=1)
    
    body = {
        "summary": ev["title"],
        "location": ev.get("location") or "",
        "description": ev["url"],
        "start": {"date": start_date.isoformat()},
        "end": {"date": end_date.isoformat()},
        "source": {
            "title": ev["site"],
            "url": ev["url"],
        },
    }
    return body


def main():
    service = _auth()
    conn = sqlite3.connect(DB_PATH)
    _ensure_db(conn)
    cur = conn.cursor()

    inserted = updated = 0

    for ev in scrape.all_events():
        key = _event_key(ev)
        cur.execute("SELECT gcal_id FROM events WHERE key=?", (key,))
        row = cur.fetchone()
        body = _event_body(ev)

        if row:
            # Update existing
            service.events().update(calendarId=CAL_ID, eventId=row[0], body=body).execute()
            updated += 1
        else:
            g_ev = service.events().insert(calendarId=CAL_ID, body=body).execute()
            cur.execute("INSERT OR REPLACE INTO events(key, gcal_id) VALUES(?,?)", (key, g_ev["id"]))
            inserted += 1

    conn.commit()
    conn.close()

    print(f"Inserted {inserted}, updated {updated} events to Google Calendar.")


if __name__ == "__main__":
    main()
