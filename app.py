import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Traffic Analytics Dashboard",
    page_icon="🚗",
    layout="wide"
)

# --------------------------------------------------
# DARK MODE TOGGLE
# --------------------------------------------------

theme = st.sidebar.radio("Theme", ["Light", "Dark"])

if theme == "Dark":
    pio.templates.default = "plotly_dark"
    st.markdown(
        """
        <style>
        .stApp { background-color: #111 !important; color: #eee !important; }
        section[data-testid="stSidebar"] { background-color: #000 !important; }
        .stTextInput>div>div>input,
        .stSelectbox>div>div>select,
        .stMultiSelect>div>div>select { background-color: #1a1a1a !important; color: #eee !important; }
        .stTabs [data-baseweb="tab"] { background-color: #1a1a1a !important; color: #eee !important; }
        .stMetric { color: #eee !important; }
        .stPlotlyChart { background-color: #111 !important; }
        </style>
        """,
        unsafe_allow_html=True
    )
else:
    pio.templates.default = "plotly_white"

# --------------------------------------------------
# LAZY LOADERS
# --------------------------------------------------

@st.cache_data(show_spinner=True)
def load_traffic():
    df = pd.read_parquet("traffic_analysis_final.parquet")
    df["Date"] = pd.to_datetime(df["Date"])
    return df

@st.cache_data(show_spinner=True)
def load_forecasts():
    df = pd.read_parquet("Dashboard_Forecasts.parquet")
    df["DateTime"] = pd.to_datetime(df["DateTime"])
    return df

def downsample(df, max_points=5000):
    if len(df) > max_points:
        step = max(1, len(df) // max_points)
        return df.iloc[::step]
    return df

# --------------------------------------------------
# SIDEBAR NAVIGATION
# --------------------------------------------------

page = st.sidebar.radio(
    "Navigation",
    [
        "Home",
        "Traffic Explorer",
        "Neutrality Explorer",
        "School Holiday Impact",
        "Day Type Explorer",
        "Traffic Forecast"
    ]
)

# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------

if page == "Home":

    st.title("North East Traffic Analytics Dashboard")

    st.markdown(
        """
This dashboard was developed as part of the
**Data Science Accelerator Project**.

## Project Question  
**How Neutral is Neutral?**
"""
    )

    st.info("Data loads only when needed to improve performance.")

# --------------------------------------------------
# TRAFFIC EXPLORER
# --------------------------------------------------

elif page == "Traffic Explorer":

    st.title("Traffic Explorer")
    st.info("Explore how traffic normally behaves at a selected site.")

    traffic = load_traffic()

    site = st.selectbox("Site", sorted(traffic["SiteNo"].unique()))
    site_data = traffic[traffic["SiteNo"] == site].sort_values("Date")

    min_date = site_data["Date"].min()
    max_date = site_data["Date"].max()

    date_range = st.date_input("Date Range", value=(min_date, max_date))

    filtered = site_data[
        (site_data["Date"] >= pd.to_datetime(date_range[0])) &
        (site_data["Date"] <= pd.to_datetime(date_range[1]))
    ]

    if len(filtered) > 20000:
        st.warning("Large date range detected. Auto-downsampling applied.")
        filtered = downsample(filtered)

    avg_daily_traffic = filtered["Total"].mean()
    avg_neutrality = filtered["NeutralityScore"].mean()
    common_day_type = filtered["DayType"].mode().iloc[0] if not filtered["DayType"].mode().empty else "N/A"

    col1, col2, col3 = st.columns(3)
    col1.metric("Average Daily Traffic", int(avg_daily_traffic))
    col2.metric("Average Neutrality", round(avg_neutrality, 1))
    col3.metric("Most Common Day Type", common_day_type)

    tab1, tab2 = st.tabs(["Historical Trend", "Average Hourly Profile"])

    with tab1:
        fig = px.line(filtered, x="Date", y="Total", title="Traffic Through Time")
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        hour_columns = [col for col in filtered.columns if ":" in col]
        if hour_columns:
            profile = filtered[hour_columns].mean()
            fig = px.line(x=profile.index, y=profile.values, markers=True, title="Average Hourly Profile")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Hourly columns not found.")

# --------------------------------------------------
# NEUTRALITY EXPLORER
# --------------------------------------------------

elif page == "Neutrality Explorer":

    st.title("Neutrality Explorer")
    st.info("Was this day normal?")

    traffic = load_traffic()

    site = st.selectbox("Site", sorted(traffic["SiteNo"].unique()))
    site_data = traffic[traffic["SiteNo"] == site].sort_values("Date")

    selected_date = st.selectbox("Select Date", site_data["Date"].dt.date.unique())
    record = site_data[site_data["Date"].dt.date == selected_date]

    if len(record):

        total = float(record["Total"].iloc[0])
        expected = float(record["ExpectedTotal"].iloc[0])
        diff = total - expected
        score = float(record["NeutralityScore"].iloc[0])
        band = record["NeutralityBand"].iloc[0]

        st.subheader("Selected Day Summary")
        st.metric("Traffic", int(total))
        st.metric("Expected", int(expected))
        st.metric("Difference", int(diff))
        st.metric("Neutrality Score", round(score, 1))
        st.metric("Band", band)

# --------------------------------------------------
# SCHOOL HOLIDAY IMPACT
# --------------------------------------------------

elif page == "School Holiday Impact":

    st.title("School Holiday Impact")
    st.info("How much do holidays reduce traffic?")

    traffic = load_traffic()

    site = st.selectbox("Site", sorted(traffic["SiteNo"].unique()))
    site_data = traffic[traffic["SiteNo"] == site]

    if "SchoolHolidayStatus" in site_data.columns:
        summary = site_data.groupby("SchoolHolidayStatus")["Total"].mean().reset_index()
        fig = px.bar(summary, x="SchoolHolidayStatus", y="Total", title=f"Holiday Impact — Site {site}")
        st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------
# DAY TYPE EXPLORER
# --------------------------------------------------

elif page == "Day Type Explorer":

    st.title("Day Type Explorer")
    st.info("What type of day was this?")

    traffic = load_traffic()

    site = st.selectbox("Site", sorted(traffic["SiteNo"].unique()))
    site_data = traffic[traffic["SiteNo"] == site].sort_values("Date")

    selected_date = st.selectbox("Select Date", site_data["Date"].dt.date.unique())
    record = site_data[site_data["Date"].dt.date == selected_date]

    if len(record):
        st.metric("Day Type", record["DayType"].iloc[0])
        st.metric("Neutrality", float(record["NeutralityScore"].iloc[0]))
        st.metric("Traffic", int(record["Total"].iloc[0]))

# --------------------------------------------------
# TRAFFIC FORECAST
# --------------------------------------------------

elif page == "Traffic Forecast":

    st.title("Traffic Forecast")
    st.info("Forecasts generated using the LightGBM model.")

    forecasts = load_forecasts()

    site = st.selectbox("Forecast Site", forecasts["SiteNo"].unique())
    site_forecast = forecasts[forecasts["SiteNo"] == site].sort_values("DateTime")

    forecast_date = st.selectbox("Forecast Date", site_forecast["DateTime"].dt.date.unique())
    day_forecast = site_forecast[site_forecast["DateTime"].dt.date == forecast_date]

    if len(day_forecast):

        expected_daily = float(day_forecast["PredictedTraffic"].sum())

        fig = px.line(
            day_forecast,
            x="DateTime",
            y="PredictedTraffic",
            title=f"Hourly Forecast — Site {site}, {forecast_date}"
        )
        st.plotly_chart(fig, use_container_width=True)
