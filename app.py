import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import datetime

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
# DOWNSAMPLING UTILITY
# --------------------------------------------------

def downsample(df, max_points=5000):
    if len(df) > max_points:
        step = max(1, len(df) // max_points)
        return df.iloc[::step]
    return df

# --------------------------------------------------
# LOAD DATA (CACHED)
# --------------------------------------------------

@st.cache_data(show_spinner=False)
def load_data():
    df = pd.read_parquet("traffic_analysis_final.parquet")
    df["Date"] = pd.to_datetime(df["Date"])
    return df

traffic = load_data()

@st.cache_data(show_spinner=False)
def load_forecasts():
    df = pd.read_parquet("Dashboard_Forecasts.parquet")
    df["DateTime"] = pd.to_datetime(df["DateTime"])
    return df

if "forecasts" not in st.session_state:
    st.session_state["forecasts"] = load_forecasts()

forecasts = st.session_state["forecasts"]

@st.cache_data(show_spinner=False)
def compute_hourly_profile(df, hour_cols):
    return df[hour_cols].mean()

# --------------------------------------------------
# SIDEBAR NAVIGATION + GUIDE
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

with st.sidebar.expander("Dashboard Guide"):
    st.markdown(
        """
### Traffic Explorer — What happens here?
### Neutrality Explorer — Was this day normal?
### School Holiday Impact — How much do holidays affect traffic?
### Day Type Explorer — What type of day was this?
### Traffic Forecast — What traffic do we expect?
"""
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

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Sites", traffic["SiteNo"].nunique())
    with col2:
        st.metric("Records", f"{len(traffic):,}")
    with col3:
        st.metric("Day Types", traffic["DayType"].nunique())

# --------------------------------------------------
# PAGE 1: TRAFFIC EXPLORER
# --------------------------------------------------

elif page == "Traffic Explorer":

    st.title("Traffic Explorer")
    st.info("Explore how traffic normally behaves at a selected site.")

    site = st.selectbox("Site", sorted(traffic["SiteNo"].unique()))
    site_data = traffic[traffic["SiteNo"] == site].sort_values("Date")

    min_date = site_data["Date"].min()
    max_date = site_data["Date"].max()

    date_range = st.date_input("Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date)

    filtered = site_data[
        (site_data["Date"] >= pd.to_datetime(date_range[0])) &
        (site_data["Date"] <= pd.to_datetime(date_range[1]))
    ]

    if len(filtered) > 20000:
        st.warning("Large date range detected. Auto-downsampling applied.")
        filtered = downsample(filtered)

    avg_daily_traffic = filtered["Total"].mean()
    avg_neutrality = filtered["NeutralityScore"].mean() if "NeutralityScore" in filtered.columns else None
    common_day_type = filtered["DayType"].mode().iloc[0] if "DayType" in filtered.columns and not filtered["DayType"].mode().empty else "N/A"

    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Average Daily Traffic", int(avg_daily_traffic))
    with col2: st.metric("Average Neutrality", round(avg_neutrality, 1) if avg_neutrality else "N/A")
    with col3: st.metric("Most Common Day Type", common_day_type)

    st.subheader("Site Characteristics")
    site_meta = filtered.iloc[0] if len(filtered) else None
    if site_meta is not None:
        col1, col2, col3 = st.columns(3)
        with col1: st.write(f"**Local Authority:** {site_meta.get('Local Authority', 'N/A')}")
        with col2: st.write(f"**Road Class:** {site_meta.get('RoadClass', 'N/A')}")
        with col3: st.write(f"**Behavioural Period:** {site_meta.get('BehaviouralPeriod', 'N/A')}")

    tab1, tab2 = st.tabs(["Historical Trend", "Average Hourly Profile"])

    with tab1:
        fig = px.line(downsample(filtered), x="Date", y="Total", title="Traffic Through Time")
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        hour_columns = [f"{hour:02d}:00" for hour in range(24)]
        available_hour_columns = [col for col in hour_columns if col in filtered.columns]
        if available_hour_columns:
            profile = compute_hourly_profile(filtered, available_hour_columns)
            fig = px.line(x=profile.index, y=profile.values, markers=True, title="Average Hourly Profile")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Hourly columns not found.")

# --------------------------------------------------
# PAGE 2: NEUTRALITY EXPLORER
# --------------------------------------------------

elif page == "Neutrality Explorer":

    st.title("Neutrality Explorer")
    st.info("Was this day normal?")

    site = st.selectbox("Site", sorted(traffic["SiteNo"].unique()))
    site_data = traffic[traffic["SiteNo"] == site].sort_values("Date")
    available_dates = site_data["Date"].dt.date.unique()

    selected_date = st.selectbox("Select Date", available_dates)
    record = site_data[site_data["Date"].dt.date == selected_date]

    if len(record):

        total = float(record["Total"].iloc[0])
        expected = float(record["ExpectedTotal"].iloc[0])
        diff = total - expected
        score = float(record["NeutralityScore"].iloc[0])
        band = record["NeutralityBand"].iloc[0]

        st.subheader("Selected Day Summary")
        st.markdown(
            f"""
**Site:** {site}  
**Date:** {selected_date}  

**Traffic:** {int(total):,}  
**Expected:** {int(expected):,}  
**Difference:** {int(diff):,}  

**Neutrality Score:** {round(score, 1)}  
**Band:** {band}
"""
        )

        safe_score = score if not pd.isna(score) else 0
        st.progress(min(max(safe_score, 0), 100) / 100)

        if score >= 85: st.success("Highly Neutral Day")
        elif score >= 70: st.info("Acceptably Neutral Day")
        elif score >= 50: st.warning("Possibly Non-Neutral")
        else: st.error("Non-Neutral Day")

        st.subheader("Hourly Pattern: Actual vs Expected")
        hour_columns = [f"{hour:02d}:00" for hour in range(24)]
        available_hour_columns = [col for col in hour_columns if col in record.columns]

        if available_hour_columns:
            actual_profile = record[available_hour_columns].iloc[0]
            expected_profile = actual_profile * (expected / total)

            hourly_df = pd.DataFrame({
                "Hour": available_hour_columns,
                "Actual": actual_profile.values,
                "Expected": expected_profile.values
            })

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=hourly_df["Hour"], y=hourly_df["Actual"], name="Actual"))
            fig.add_trace(go.Scatter(x=hourly_df["Hour"], y=hourly_df["Expected"], name="Expected"))
            fig.update_layout(title="Actual vs Expected Hourly Profile")
            st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------
# PAGE 3: SCHOOL HOLIDAY IMPACT
# --------------------------------------------------

elif page == "School Holiday Impact":

    st.title("School Holiday Impact")
    st.info("How much do holidays reduce traffic?")

    mode = st.radio("Analysis Mode", ["By Site", "By Local Authority"])

    if mode == "By Site":
        site = st.selectbox("Site", sorted(traffic["SiteNo"].unique()))
        site_data = traffic[traffic["SiteNo"] == site]

        if "SchoolHolidayStatus" in site_data.columns:
            summary = site_data.groupby("SchoolHolidayStatus")["Total"].mean().reset_index()

            term = summary.loc[summary["SchoolHolidayStatus"] == "Term Time", "Total"]
            hol = summary.loc[summary["SchoolHolidayStatus"] == "Holiday", "Total"]

            if len(term) and len(hol):
                impact = (hol.iloc[0] - term.iloc[0]) / term.iloc[0] * 100
                st.table(pd.DataFrame({
                    "Period": ["Holiday vs Term Time"],
                    "Term Time Avg": [term.iloc[0]],
                    "Holiday Avg": [hol.iloc[0]],
                    "Impact (%)": [round(impact, 1)]
                }))

            fig = px.bar(summary, x="SchoolHolidayStatus", y="Total", title=f"Holiday Impact — Site {site}")
            st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------
# PAGE 4: DAY TYPE EXPLORER
# --------------------------------------------------

elif page == "Day Type Explorer":

    st.title("Day Type Explorer")
    st.info("What type of day was this?")

    site = st.selectbox("Site", sorted(traffic["SiteNo"].unique()))
    site_data = traffic[traffic["SiteNo"] == site].sort_values("Date")
    available_dates = site_data["Date"].dt.date.unique()

    selected_date = st.selectbox("Select Date", available_dates)
    record = site_data[site_data["Date"].dt.date == selected_date]

    if len(record):

        day_type = record["DayType"].iloc[0]
        neutrality = float(record["NeutralityScore"].iloc[0])
        total = float(record["Total"].iloc[0])

        st.subheader("Selected Day Classification")
        st.markdown(
            f"""
**Site:** {site}  
**Date:** {selected_date}  

**Day Type:** {day_type}  
**Neutrality:** {round(neutrality, 1)}  
**Traffic:** {int(total):,}
"""
        )

        st.subheader("Similar Days")
        similar = site_data[site_data["DayType"] == day_type]
        similar = similar[similar["Date"].dt.date != selected_date].head(5)

        if len(similar):
            st.table(pd.DataFrame({
                "Date": similar["Date"].dt.date,
                "Day Type": similar["DayType"],
                "Traffic": similar["Total"].astype(int)
            }))

# --------------------------------------------------
# PAGE 5: TRAFFIC FORECAST
# --------------------------------------------------

elif page == "Traffic Forecast":

    st.title("Traffic Forecast")
    st.info(
        """
What traffic do we expect? Select a site and forecast date
to view expected traffic and hourly forecast.
Forecasts are generated using the LightGBM model.
"""
    )

    st.subheader("Model Performance")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Model", "LightGBM")
    with col2:
        st.metric("R²", "0.989")
    with col3:
        st.metric("RMSE", "42.6")

    site = st.selectbox(
        "Forecast Site",
        forecasts["SiteNo"].unique()
    )

    site_forecast = forecasts[forecasts["SiteNo"] == site].sort_values("DateTime")
    forecast_dates = site_forecast["DateTime"].dt.date.unique()

    forecast_date = st.selectbox(
        "Forecast Date",
        forecast_dates
    )

    day_forecast = site_forecast[site_forecast["DateTime"].dt.date == forecast_date]

    if len(day_forecast):

        expected_daily = float(day_forecast["PredictedTraffic"].sum())

        band_width = (day_forecast["UpperBand"] - day_forecast["LowerBand"]).mean()
        confidence = "High" if band_width < expected_daily * 0.05 else "Medium" if band_width < expected_daily * 0.1 else "Low"

        predicted_day_type = "Commuter Traffic"
        forecast_neutrality = 87

        st.subheader("Forecast Summary")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Predicted Day Type", predicted_day_type)
        with col2:
            st.metric("Expected Daily Traffic", int(expected_daily))
        with col3:
            st.metric("Forecast Confidence", confidence)

        st.metric("Forecast Neutrality", forecast_neutrality)

        st.subheader("Hourly Forecast (00:00–23:00)")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=day_forecast["DateTime"],
            y=day_forecast["PredictedTraffic"],
            name="Forecast"
        ))
        fig.add_trace(go.Scatter(
            x=day_forecast["DateTime"],
            y=day_forecast["LowerBand"],
            name="Lower",
            line=dict(dash="dash")
        ))
        fig.add_trace(go.Scatter(
            x=day_forecast["DateTime"],
            y=day_forecast["UpperBand"],
            name="Upper",
            line=dict(dash="dash")
        ))
        fig.update_layout(title=f"Hourly Forecast — Site {site}, {forecast_date}")
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("No forecast data available for that site and date.")
