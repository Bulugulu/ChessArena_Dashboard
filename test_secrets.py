import streamlit as st
import os
import json
from supabase import create_client, Client
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Metric
from google.oauth2.service_account import Credentials
from google.api_core import exceptions as google_exceptions
from postgrest import exceptions as postgrest_exceptions

def check_secrets():
    """Prints the status of required secrets."""
    st.header("1. Secrets Configuration Check")
    secrets = {
        "GA4_PROPERTY_ID": st.secrets.get("GA4_PROPERTY_ID"),
        "GA4_SERVICE_ACCOUNT_JSON": st.secrets.get("GA4_SERVICE_ACCOUNT_JSON"),
        "SUPABASE_URL": st.secrets.get("SUPABASE_URL"),
        "SUPABASE_SERVICE_ROLE_KEY": st.secrets.get("SUPABASE_SERVICE_ROLE_KEY"),
    }
    all_secrets_found = True
    for secret_name, secret_value in secrets.items():
        if secret_value:
            st.success(f"✅ Found `{secret_name}`")
        else:
            st.error(f"❌ `{secret_name}` not found. Please set it in `.streamlit/secrets.toml`.")
            all_secrets_found = False
    st.info("Your secrets file should be located at `.streamlit/secrets.toml`")
    return all_secrets_found

def test_supabase_connection():
    """Tests the connection to Supabase and performs a simple query."""
    st.header("2. Supabase Connection Test")
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
        supabase: Client = create_client(url, key)
        
        # Test connection by fetching count from a table. 'profiles' is a common default.
        # This will fail if the table doesn't exist, which is a good test.
        response = supabase.table('profiles').select('*', count='exact').limit(0).execute()
        
        st.success("✅ Supabase connection successful.")
        st.info(f"Successfully fetched data. Found `{response.count}` rows in `profiles` table.")
        return True
    except postgrest_exceptions.APIError as e:
        st.error("❌ Supabase API Error: Could not connect or query.")
        st.code(f"Error: {e.message}\nDetails: {e.details}")
        st.warning("Common issues: Incorrect `SUPABASE_URL` or `SUPABASE_SERVICE_ROLE_KEY`. Ensure the `profiles` table exists.")
        return False
    except Exception as e:
        st.error(f"❌ An unexpected error occurred with Supabase: {e}")
        return False

def test_ga4_connection():
    """Tests the connection to Google Analytics Data API."""
    st.header("3. GA4 Connection Test")
    try:
        property_id = st.secrets["GA4_PROPERTY_ID"]
        service_account_json_str = st.secrets["GA4_SERVICE_ACCOUNT_JSON"]
        
        # The JSON string needs to be parsed into a dictionary
        credentials_dict = json.loads(service_account_json_str)
        credentials = Credentials.from_service_account_info(credentials_dict)
        
        client = BetaAnalyticsDataClient(credentials=credentials)
        
        # Simple test query to check if the connection and permissions are valid
        request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date="yesterday", end_date="today")],
            metrics=[Metric(name="activeUsers")]
        )
        response = client.run_report(request)
        
        st.success("✅ GA4 connection successful.")
        # You can optionally display some data from the response to confirm it's working
        # For example, number of rows in the response
        st.info(f"Successfully ran a test report. Found `{len(response.rows)}` rows of data.")
        return True
    except json.JSONDecodeError:
        st.error("❌ GA4 Error: `GA4_SERVICE_ACCOUNT_JSON` is not a valid JSON string.")
        st.warning("Please ensure you've copied the entire service account JSON file content.")
        return False
    except google_exceptions.PermissionDenied as e:
        st.error("❌ GA4 Permission Denied.")
        st.code(f"Error: {e.message}")
        st.warning("Common issues: Service account email might not have 'Viewer' role in GA4 Property Access Management.")
        return False
    except google_exceptions.InvalidArgument as e:
        st.error("❌ GA4 Invalid Argument.")
        st.code(f"Error: {e.message}")
        st.warning("Common issue: `GA4_PROPERTY_ID` might be incorrect.")
        return False
    except Exception as e:
        st.error(f"❌ An unexpected error occurred with GA4: {e}")
        return False

if __name__ == "__main__":
    st.title("Dashboard Connection Tester")

    if not os.path.exists(".streamlit/secrets.toml"):
        st.error("`.streamlit/secrets.toml` file not found.")
        st.info("Please copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and add your secrets.")
    else:
        secrets_found = check_secrets()
        if secrets_found:
            st.markdown("---")
            supabase_ok = test_supabase_connection()
            st.markdown("---")
            ga4_ok = test_ga4_connection()
            st.markdown("---")
            
            if supabase_ok and ga4_ok:
                st.balloons()
                st.success("🎉 All connections are working correctly!")
            else:
                st.error("One or more connections failed. Please review the error messages above.")
