#!/usr/bin/env python3
"""
Fetches one or more iCal (.ics) calendar feeds, merges their events,
and writes out a single RSS 2.0 feed (docs/feed.xml).

Calendar URLs are read from the CALENDAR_URLS environment variable,
as a comma-separated list. Each entry can optionally have a friendly
label prefixed like  Label|https://...ics , e.g.:

  CALENDAR_URLS="Personal|https://calendar.google.com/.../basic.ics,Officiating|https://www.arbitersports.com/.../feed.ics"

Only events in the future (or within LOOKBACK_DAYS in the past) are
included, and only the next LOOKAHEAD_DAYS are included, to keep the
feed a reasonable size.
"""

import os
import sys
import hashlib
from datetime import datetime, timedelta, date, timezone
from zoneinfo import ZoneInfo

CENTRAL = ZoneInfo("America/Chicago")  # auto-adjusts for CST/CDT
from email.utils import format_datetime
from xml.sax.saxutils import escape

import requests
from icalendar import Calendar

LOOKBACK_DAYS = 0
LOOKAHEAD_DAYS = 60
OUTPUT_PATH = "docs/feed.xml"

# Set these two for your public feed
FEED_TITLE = "My Merged Calendar Feed"
FEED_LINK = os.environ.get("FEED_PUBLIC_URL", "https://example.github.io/ical-to-rss/feed.xml")
FEED_DESCRIPTION = "Auto-generated daily from Google Calendar + Arbiter iCal feeds."


def parse_calendar_env():
    raw = os.environ.get("CALENDAR_URLS", "")
    if not raw.strip():
        print("ERROR: CALENDAR_URLS environment variable is empty.", file=sys.stderr)
        sys.exit(1)

    sources = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "|" in chunk:
            label, url = chunk.split("|", 1)
        else:
            label, url = "Calendar", chunk
        sources.append((label.strip(), url.strip()))
    return sources


def to_datetime(value):
    """Normalize icalendar date/datetime values to timezone-aware datetimes."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    return None


def fetch_events(label, url):
    events = []
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"WARNING: failed to fetch '{label}' feed: {e}", file=sys.stderr)
        return events

    try:
        cal = Calendar.from_ical(resp.content)
    except Exception as e:
        print(f"WARNING: failed to parse '{label}' feed: {e}", file=sys.stderr)
        return events

    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        summary = str(component.get("summary", "(no title)"))
        location = str(component.get("location", "")) or ""
        description = str(component.get("description", "")) or ""
        uid = str(component.get("uid", ""))

        dtstart = component.get("dtstart")
        dtstart = to_datetime(dtstart.dt) if dtstart else None
        if dtstart is None:
            continue

        dtend = component.get("dtend")
        dtend = to_datetime(dtend.dt) if dtend else None

        events.append({
            "label": label,
            "summary": summary,
            "location": location,
            "description": description,
            "uid": uid or hashlib.md5(f"{label}{summary}{dtstart}".encode()).hexdigest(),
            "start": dtstart,
            "end": dtend,
        })

    return events


def build_rss(events):
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=LOOKBACK_DAYS)
    window_end = now + timedelta(days=LOOKAHEAD_DAYS)

    events = [e for e in events if window_start <= e["start"] <= window_end]
    events.sort(key=lambda e: e["start"])

    items_xml = []
    for e in events:
        start_central = e["start"].astimezone(CENTRAL)
        title = f"[{e['label']}] {e['summary']} — {start_central.strftime('%a %b %d, %Y %I:%M %p %Z')}"
        desc_parts = []
        if e["location"]:
            desc_parts.append(f"Location: {e['location']}")
        if e["end"]:
            end_central = e["end"].astimezone(CENTRAL)
            desc_parts.append(f"Ends: {end_central.strftime('%a %b %d, %Y %I:%M %p %Z')}")
        if e["description"]:
            desc_parts.append(e["description"])
        description = " | ".join(desc_parts) if desc_parts else "No additional details."

        pub_date = format_datetime(e["start"])
        guid = escape(e["uid"])

        items_xml.append(f"""    <item>
      <title>{escape(title)}</title>
      <description>{escape(description)}</description>
      <pubDate>{pub_date}</pubDate>
      <guid isPermaLink="false">{guid}</guid>
    </item>""")

    build_date = format_datetime(now)

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{escape(FEED_TITLE)}</title>
    <link>{escape(FEED_LINK)}</link>
    <description>{escape(FEED_DESCRIPTION)}</description>
    <lastBuildDate>{build_date}</lastBuildDate>
{chr(10).join(items_xml)}
  </channel>
</rss>
"""
    return rss


def main():
    sources = parse_calendar_env()
    all_events = []
    for label, url in sources:
        evs = fetch_events(label, url)
        print(f"Fetched {len(evs)} events from '{label}'")
        all_events.extend(evs)

    rss = build_rss(all_events)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(rss)

    print(f"Wrote {OUTPUT_PATH} with events from {len(sources)} calendar(s).")


if __name__ == "__main__":
    main()
