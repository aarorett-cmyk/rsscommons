#!/usr/bin/env python3
"""
Fetches one or more iCal (.ics) calendar feeds, merges their events,
and writes out a single RSS 2.0 feed (docs/feed.xml).

Calendar URLs are read from the CALENDAR_URLS environment variable,
as a comma-separated list. Each entry can optionally have a friendly
label prefixed like  Label|https://...ics , e.g.:

  CALENDAR_URLS="Bay Port|https://.../calendar.ics,Sports|https://.../schedule.ics"

Only events that have not finished yet are included, up to
LOOKAHEAD_DAYS into the future. Times are shown in Central time.
All-day events are shown by date only (no time).
"""

import os
import sys
import hashlib
from datetime import datetime, timedelta, date, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

import requests
from icalendar import Calendar

CENTRAL = ZoneInfo("America/Chicago")  # auto-adjusts for CST/CDT

LOOKBACK_DAYS = 0
LOOKAHEAD_DAYS = 60
OUTPUT_PATH = "docs/feed.xml"

FEED_TITLE = "My Merged Calendar Feed"
FEED_LINK = os.environ.get("FEED_PUBLIC_URL", "https://example.github.io/ical-to-rss/feed.xml")
FEED_DESCRIPTION = "Auto-generated daily from the Bay Port calendar and Arbiter sports schedule."


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


def normalize(value):
    """
    Turn an icalendar value into (aware_datetime, is_all_day).
    All-day events (plain dates) become midnight Central on that date,
    so they are never shifted onto the neighbouring day.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            # Floating time: treat as Central local time
            return value.replace(tzinfo=CENTRAL), False
        return value, False
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=CENTRAL), True
    return None, False


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

        dtstart_prop = component.get("dtstart")
        if dtstart_prop is None:
            continue
        start, all_day = normalize(dtstart_prop.dt)
        if start is None:
            continue

        dtend_prop = component.get("dtend")

        # Some calendar systems write all-day events as a bare midnight-UTC
        # timestamp with no end time. Treat those as all-day on that UTC date
        # so they aren't shifted back onto the previous evening in Central time.
        if (not all_day and dtend_prop is None
                and start.utcoffset() == timedelta(0)
                and (start.hour, start.minute, start.second) == (0, 0, 0)):
            utc_day = start.astimezone(timezone.utc).date()
            start = datetime(utc_day.year, utc_day.month, utc_day.day, tzinfo=CENTRAL)
            all_day = True

        end = None
        if dtend_prop is not None:
            end, _ = normalize(dtend_prop.dt)
        if end is None:
            end = start + (timedelta(days=1) if all_day else timedelta(0))

        events.append({
            "label": label,
            "summary": summary,
            "location": location,
            "description": description,
            "uid": uid or hashlib.md5(f"{label}{summary}{start}".encode()).hexdigest(),
            "start": start,
            "end": end,
            "all_day": all_day,
        })

    return events


def fmt_dt(dt):
    return dt.astimezone(CENTRAL).strftime("%a %b %d, %Y %I:%M %p %Z")


def fmt_day(dt):
    return dt.strftime("%a %b %d, %Y")


def build_rss(events):
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=LOOKBACK_DAYS)
    window_end = now + timedelta(days=LOOKAHEAD_DAYS)

    # Keep anything that hasn't finished yet (all-day events end at the
    # start of the following day) and starts within the look-ahead window.
    events = [e for e in events if e["end"] >= window_start and e["start"] <= window_end]
    events.sort(key=lambda e: e["start"])

    items_xml = []
    for e in events:
        if e["all_day"]:
            title = f"[{e['label']}] {e['summary']} — {fmt_day(e['start'])} (all day)"
        else:
            title = f"[{e['label']}] {e['summary']} — {fmt_dt(e['start'])}"

        desc_parts = []
        if e["location"]:
            desc_parts.append(f"Location: {e['location']}")
        if not e["all_day"] and e["end"] > e["start"]:
            desc_parts.append(f"Ends: {fmt_dt(e['end'])}")
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
