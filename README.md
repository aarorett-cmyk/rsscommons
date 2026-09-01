# iCal → RSS (Google Calendar + Arbiter)

Merges one or more iCal (.ics) calendar feeds into a single RSS feed,
refreshed automatically once a day, hosted for free on GitHub Pages.

## One-time setup (about 10 minutes)

### 1. Create a GitHub account (if you don't have one)
Go to https://github.com and sign up — it's free.

### 2. Create a new repository
- Click the **+** in the top right → **New repository**
- Name it something like `ical-to-rss`
- Set it to **Public** (required for free GitHub Pages)
- Click **Create repository**

### 3. Upload these files
On the new repo's page, click **Add file → Upload files**, and drag in
everything from this folder, keeping the folder structure:
```
build_feed.py
requirements.txt
README.md
.github/workflows/build-feed.yml
```
(GitHub will let you drag the `.github` folder in directly — it preserves the path.)
Commit the files to the `main` branch.

### 4. Get your calendar URLs
- **Google Calendar**: Settings → [your calendar] → "Integrate calendar" →
  copy the **Secret address in iCal format**.
- **Arbiter**: Settings → "Get iCal Feed" / "Email me my Calendar Feed" →
  copy the URL from the email Arbiter sends you.

### 5. Add your calendar URLs as a GitHub Secret
- In your repo, go to **Settings → Secrets and variables → Actions**
- Click **New repository secret**
  - Name: `CALENDAR_URLS`
  - Value (comma-separated, `Label|URL` format):
    ```
    Personal|https://calendar.google.com/calendar/ical/.../basic.ics,Officiating|https://www.arbitersports.com/.../feed.ics
    ```
- Click **Add secret**

### 6. Enable GitHub Pages
- Go to **Settings → Pages**
- Under "Build and deployment," set **Source** to **Deploy from a branch**
- Branch: `main`, folder: `/docs` → **Save**
- GitHub will show you a URL like:
  `https://YOUR-USERNAME.github.io/ical-to-rss/`
  Your feed will be at `https://YOUR-USERNAME.github.io/ical-to-rss/feed.xml`

### 7. (Optional but recommended) Set the public feed URL secret
- Add another repository secret:
  - Name: `FEED_PUBLIC_URL`
  - Value: `https://YOUR-USERNAME.github.io/ical-to-rss/feed.xml`

### 8. Run it for the first time
- Go to the **Actions** tab in your repo
- Click **Build RSS feed** on the left → **Run workflow** → **Run workflow**
- Wait ~30 seconds, then check `docs/feed.xml` in your repo — it should be
  filled in with your events.

That's it. From now on, this runs automatically every day at 12:00 UTC and
pushes the updated `feed.xml` to GitHub Pages — no computer or server of
yours needs to be on. Subscribe to the Pages URL from step 6 in any RSS
reader.

## Adjusting things later
- **Change the schedule**: edit the `cron` line in
  `.github/workflows/build-feed.yml` (it's in UTC).
- **Change how far ahead/back events show**: edit `LOOKAHEAD_DAYS` and
  `LOOKBACK_DAYS` in `build_feed.py`.
- **Add more calendars**: just add more `Label|URL` pairs to the
  `CALENDAR_URLS` secret, comma-separated.
