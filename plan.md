## Minimal Dashboard Plan (MVP)

A single-page internal dashboard that’s simple, minimal, and fast to ship. No mock mode, no password gate, no alternate hosts, no MySQL. Just the essentials.

### 1) Goals & Scope

*   **Audience**: internal team (share a link)
*   **Form factor**: one-page dashboard
*   **Stack**: Streamlit (Cloud) + GA4 + Supabase
*   **Time zone**: America/New_York (hardcoded)
*   **MVP views**:
    *   **Today (since midnight)**: First-time visits, Signups, Conversion
    *   **Lifetime**: Total signups (from DB)
    *   **Funnel (last X days)**: Impressions → Naming page visits → Register clicks → Discord signups, with % of Impressions and Drop-off

### 2) Data Sources & Ownership

*   **Google Analytics 4 (GA4)**
    *   Source of truth for today cards and funnel steps
*   **Supabase (Postgres)**
    *   Source of truth for lifetime total signups (count of rows in `profiles`)
*   Keep all funnel steps in GA4 for consistency. Use Supabase only for the lifetime total.

### 3) Metrics & Definitions (Data Dictionary)

*   **Today (midnight → now, `America/New_York`)**
    *   **First-time visits**: GA4 `newUsers`
    *   **Signups**: GA4 `eventCount` for your canonical signup event (e.g., `sign_up`)
    *   **Conversion**: `signups_today` / `newUsers_today`
*   **Lifetime**
    *   **Total signups**: Count of rows in `profiles` (Supabase)
*   **Funnel (last X days, selectable)**
    *   **Steps (canonical names / filters)**:
        *   **Impressions** → GA4 event `video_impression`
        *   **Naming page visits** → GA4 page view filtered to naming page path (e.g., `/naming`)
        *   **Register clicks** → GA4 event `register_click`
        *   **Discord signups** → GA4 event `discord_signup`
    *   **Columns**:
        *   **Total**: absolute counts by step (GA4)
        *   **% of Impressions**: `step_total` / `impressions_total`
        *   **Drop-off (to next)**: `1 − (next_step_total / this_step_total)`; last row is “—”
*   Ensure the naming page path is consistently identifiable (e.g., `page_path` contains `/naming`).

### 4) Environment Variables (Secrets)

Configure in Streamlit Cloud → App → Settings → Secrets (or local `.streamlit/secrets.toml`). Use only these four:

*   `GA4_PROPERTY_ID`
*   `GA4_SERVICE_ACCOUNT_JSON` (paste the full service-account JSON as a single string)
*   `SUPABASE_URL`
*   `SUPABASE_SERVICE_ROLE_KEY`

### 5) Setup Steps

*   **GA4**
    1.  In Google Cloud, enable **Analytics Data API**.
    2.  Create a service account; download the JSON key.
    3.  In GA4 Admin → Property Access Management, add the service account email with **Viewer** access.
    4.  Note your GA4 **Property ID**.
    5.  Confirm the event & page contracts exist and fire:
        *   **Events**: `video_impression`, `register_click`, `discord_signup`, `sign_up` (or your chosen canonical)
        *   **Naming page path** detectable via `page_path`/`page_location` filter (e.g., `/naming`)
*   **Supabase**
    1.  Confirm `profiles` table is the signup source of truth (lifetime total).
    2.  Ensure `profiles.created_at` exists (optional, if you later want daily DB trends).
    3.  Use the **Service Role key** server-side only (it stays in secrets).
*   **Streamlit Cloud (hosting)**
    1.  Create a tiny repo with `app.py` and `requirements.txt`.
    2.  Deploy on Streamlit Community Cloud.
    3.  Set the four secrets above in the app’s Secrets panel.
    4.  Share the app URL with your team.

### 6) UI Layout (Wireframe)

*   **Header**
    *   Title “Growth Dashboard”
    *   Controls:
        *   Lookback selector for funnel: {7, 14, 30} days
    *   Today is fixed (no picker), uses `America/New_York`
*   **Row A — Today**
    *   Card: First-time visits (today)
    *   Card: Signups (today)
    *   Card: Conversion (today)
*   **Row B — Lifetime**
    *   Card: Total Signups (lifetime)
*   **Row C — Funnel (Last X Days)**
    *   Table with columns: Step | Total | % of Impressions | Drop-off
    *   Rows: Impressions → Naming page visits → Register clicks → Discord signups
*   (No charts in MVP. Add later if needed.)

### 7) Pseudocode (Non-Runnable; Implementation Blueprint)

```
Config

TIMEZONE = "America/New_York"
LOOKBACK_OPTIONS = [7, 14, 30]

secrets:
  ga4_property_id
  ga4_service_account_json
  supabase_url
  supabase_service_role_key


Date Handling

now = current_datetime_in(TIMEZONE)
today_start = start_of_day(now)
today_end   = now

lookback_days = user_select_from(LOOKBACK_OPTIONS, default=7)
range_start = start_of_day(now - (lookback_days - 1) days)
range_end   = today_end


GA4 Helpers

ga4_new_users(start_date, end_date) -> number
ga4_event_count(event_name, start_date, end_date) -> number
ga4_naming_page_visits(start_date, end_date) -> number  # page filter contains "/naming"


DB Helper (Supabase)

db_total_signups() -> number  # count rows in profiles


Compute “Today” Cards

first_time = ga4_new_users(today_start, today_end)
signups_today = ga4_event_count("sign_up", today_start, today_end)
conversion_today = (signups_today / first_time) if first_time > 0 else 0
render_cards([first_time, signups_today, percent(conversion_today)])


Compute Lifetime Card

total_signups = db_total_signups()
render_card(total_signups)


Compute Funnel (Last X Days)

impressions = ga4_event_count("video_impression", range_start, range_end)
naming_visits = ga4_naming_page_visits(range_start, range_end)
register_clicks = ga4_event_count("register_click", range_start, range_end)
discord_signups = ga4_event_count("discord_signup", range_start, range_end)

steps = [
  ("Impressions", impressions),
  ("Naming Page Visits", naming_visits),
  ("Register Clicks", register_clicks),
  ("Discord Signups", discord_signups),
]

for each row i:
  total_i = steps[i].total
  pct_of_impr = (total_i / impressions) if impressions > 0 else null
  drop_off = (1 - steps[i+1].total / total_i) if i < last and total_i > 0 else null
  add_row(step_name, total_i, pct_of_impr, drop_off)

render_table(rows, format: integers & percentages)


Empty/Failure Handling (MVP)

If any query fails or returns no rows:
  show 0 or "—" for that number
  (log errors server-side if desired)
```

### 8) Libraries (Trimmed to Essentials)

*   **Keep**: `streamlit`, `google-analytics-data`, `google-auth`, `supabase` (Python client)
*   **Optional**: `pandas` (you can render tables without it if you prefer)
*   (Nothing else for MVP.)

### 9) Validation Checklist (Before Sharing)

*   [ ] GA4 service account has **Viewer** on the correct property
*   [ ] `GA4_PROPERTY_ID` matches the property you intend to query
*   [ ] Events present and named exactly: `video_impression`, `register_click`, `discord_signup`, `sign_up`
*   [ ] Naming page path filter matches production URL (e.g., `/naming`)
*   [ ] Today’s numbers match GA4 UI for the same timezone
*   [ ] Supabase `profiles` count matches expectations for lifetime total
*   [ ] Streamlit Cloud Secrets configured with the four vars
