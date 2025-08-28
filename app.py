import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz
import json
from supabase import create_client, Client
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Metric, Dimension, FilterExpression, Filter, FilterExpressionList
from google.oauth2.service_account import Credentials
from google.api_core import exceptions as google_exceptions

# --- Page Config ---
st.set_page_config(
    page_title="Chess Arena Signups Dashboard",
    page_icon="📈",
    layout="wide"
)

# --- Configuration ---
TIMEZONE = "America/Los_Angeles" # Changed to LA Timezone
LOOKBACK_OPTIONS = [7, 14, 30]

# --- Client Initialization ---

@st.cache_resource
def init_supabase_client():
    """Initializes and returns a Supabase client."""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)

@st.cache_resource
def init_ga4_client():
    """Initializes and returns a GA4 client."""
    service_account_json_str = st.secrets["GA4_SERVICE_ACCOUNT_JSON"]
    credentials_dict = json.loads(service_account_json_str)
    credentials = Credentials.from_service_account_info(credentials_dict)
    return BetaAnalyticsDataClient(credentials=credentials)

supabase = init_supabase_client()
ga4 = init_ga4_client()
property_id = st.secrets["GA4_PROPERTY_ID"]

# --- Data Fetching Functions ---
@st.cache_data(ttl=3600) # Cache for 1 hour
def db_total_signups():
    """Fetches the total number of signups from Supabase."""
    try:
        response = supabase.table('profiles').select('*', count='exact').limit(0).execute()
        return response.count
    except Exception as e:
        st.error(f"Error fetching from Supabase: {e}")
        return 0

@st.cache_data(ttl=3600) # Cache for 1 hour
def db_signups_for_day(start_date, end_date):
    """Fetches the number of signups from Supabase for a given day."""
    try:
        response = supabase.table('profiles') \
            .select('*', count='exact') \
            .gte('created_at', start_date.isoformat()) \
            .lte('created_at', end_date.isoformat()) \
            .execute()
        return response.count
    except Exception as e:
        st.error(f"Error fetching daily signups from Supabase: {e}")
        return 0

def format_date(dt):
    """Formats a datetime object into YYYY-MM-DD string."""
    return dt.strftime('%Y-%m-%d')

@st.cache_data(ttl=3600) # Cache for 1 hour
def run_ga4_report(metric_names: tuple, start_date, end_date, dimension_names: tuple = None, filter_specs: tuple = None):
    """
    Runs a report on the Google Analytics Data API.
    - Handles requests with and without dimensions.
    - If dimensions are used, returns a dict mapping dimension values to metric values.
    - If no dimensions, returns a single integer metric value.
    - Supports ANDing multiple filters together.
    """
    try:
        metrics = [Metric(name=name) for name in metric_names]
        dimensions = [Dimension(name=name) for name in dimension_names] if dimension_names else None

        filter_expression = None
        if filter_specs:
            filters = []
            for spec in filter_specs:
                field_name, value, match_type_str = spec
                match_type = Filter.StringFilter.MatchType[match_type_str.upper()]
                filters.append(Filter(
                    field_name=field_name,
                    string_filter=Filter.StringFilter(value=value, match_type=match_type)
                ))
            
            if len(filters) == 1:
                filter_expression = FilterExpression(filter=filters[0])
            else:
                filter_expression = FilterExpression(and_group=FilterExpressionList(expressions=[FilterExpression(filter=f) for f in filters]))


        request = RunReportRequest(
            property=f"properties/{property_id}",
            metrics=metrics,
            date_ranges=[DateRange(start_date=format_date(start_date), end_date=format_date(end_date))],
            dimensions=dimensions,
            dimension_filter=filter_expression
        )
        response = ga4.run_report(request)
        
        # Handle response based on whether dimensions were requested
        if not dimensions:
            return int(response.rows[0].metric_values[0].value) if response.rows else 0
        else:
            result = {}
            for row in response.rows:
                dimension_value = row.dimension_values[0].value
                metric_value = int(row.metric_values[0].value)
                result[dimension_value] = metric_value
            return result

    except Exception as e:
        st.error(f"Error fetching from GA4: {e}")
        # Return a value that matches the expected return type
        return {} if dimension_names else 0


# --- UI Layout ---
st.title("📈 Growth Dashboard")

total_signups = db_total_signups()

# --- Custom CSS for the big metric ---
st.markdown("""
<style>
.big-metric {
    text-align: center;
}
.big-metric .stMetric-label {
    font-size: 20px;
    font-weight: bold;
    color: #888;
}
.big-metric .stMetric-value {
    font-size: 78px;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

# --- Big centered metric for Lifetime Signups ---
st.markdown('<div class="big-metric">', unsafe_allow_html=True)
st.metric(label="Total Signups (Lifetime)", value=f"{total_signups:,}")
st.markdown('</div>', unsafe_allow_html=True)


st.divider()

# --- Date Handling for Today ---
tz = pytz.timezone(TIMEZONE)
now = datetime.now(tz)
today_start_la = now.replace(hour=0, minute=0, second=0, microsecond=0)
today_end_la = now

# Convert LA times to UTC for Supabase query
today_start_utc = today_start_la.astimezone(pytz.utc)
today_end_utc = today_end_la.astimezone(pytz.utc)

# --- Date Handling for Funnel ---
lookback_days = st.selectbox(
    "Select Lookback Days for Funnel:",
    LOOKBACK_OPTIONS,
    index=1 # Default to 14 days
)

range_start = today_start_la - timedelta(days=lookback_days - 1)
range_end = today_end_la


# --- Funnel Computations ---
funnel_event_names_regex = "page_view|click_register|discord_signin"
funnel_event_counts = run_ga4_report(
    metric_names=("totalUsers",),
    dimension_names=("eventName",),
    start_date=range_start,
    end_date=range_end,
    filter_specs=(("eventName", funnel_event_names_regex, "FULL_REGEXP"),)
)

page_views = funnel_event_counts.get("page_view", 0)
register_clicks = funnel_event_counts.get("click_register", 0)
discord_signins = funnel_event_counts.get("discord_signin", 0)


funnel_steps = [
    {"Step": "Social Media Impressions", "Total": None},
    {"Step": "Landing Page Visits", "Total": page_views},
    {"Step": "Clicked Register", "Total": register_clicks},
    {"Step": "Signed in with Discord", "Total": discord_signins},
]
funnel_df = pd.DataFrame(funnel_steps)

# Calculate funnel metrics
# Base percentages on "Landing Page Visits" since "Social Media Impressions" is a placeholder
if len(funnel_df) > 1 and pd.notna(funnel_df["Total"].iloc[1]) and funnel_df["Total"].iloc[1] > 0:
    baseline_total = funnel_df["Total"].iloc[1]
    
    percentages = ["—"] # Placeholder for the first row
    for total in funnel_df["Total"].iloc[1:]:
        percentages.append(f"{(total / baseline_total):.2%}")
    funnel_df["% of Impressions"] = percentages

    drop_offs = ["—"] # Placeholder for the first row
    for i in range(1, len(funnel_df) - 1):
        current = funnel_df["Total"].iloc[i]
        next_val = funnel_df["Total"].iloc[i+1]
        if pd.notna(current) and current > 0 and pd.notna(next_val):
            drop_off_rate = 1 - (next_val / current)
            drop_offs.append(f"{drop_off_rate:.2%}")
        else:
            drop_offs.append("—")
    drop_offs.append("—")
    funnel_df["Drop-off"] = drop_offs
else:
    funnel_df["% of Impressions"] = "—"
    funnel_df["Drop-off"] = "—"

funnel_df["Total"] = funnel_df["Total"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")


# --- Final UI Rendering ---
st.header(f"Funnel (Last {lookback_days} Days)")

st.dataframe(funnel_df, use_container_width=True, hide_index=True)
