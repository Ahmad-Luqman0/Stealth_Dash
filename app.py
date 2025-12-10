"""
╔════════════════════════════════════════════════════════════════════════╗
║        STEALTH MONITOR - COMPREHENSIVE ANALYTICS DASHBOARD            ║
║                    Multi-Page Visualization Dashboard                  ║
║                    Enhanced with Download Features                     ║
╚════════════════════════════════════════════════════════════════════════╝

FEATURES:
  - Multi-page dashboard with navigation
  - Overview: Key metrics, KPIs, and summary stats
  - User Analysis: Individual user productivity tracking
  - Session Details: Detailed session breakdown
  - Trends: Time-series analysis and patterns
  - App/URL Analysis: Application and website usage breakdown
  - Interactive charts with Plotly
  - Real-time auto-refresh
  - Export capabilities (CSV and Full Report with Graphs)

USAGE:
  streamlit run app1.py
"""

import streamlit as st
from pymongo import MongoClient
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from collections import defaultdict
import io
import base64
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    PageBreak,
    Image,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# ==================== PAGE CONFIGURATION ====================
st.set_page_config(
    page_title="Stealth Monitor Analytics",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "Stealth Monitor Analytics Dashboard"},
)

# Auto-refresh every 30 seconds
st_autorefresh(interval=30 * 1000, key="dashboard_refresh")


# ==================== MONGODB CONNECTION ====================
@st.cache_resource
def init_connection():
    """Initialize MongoDB connection"""
    try:
        # Try to get connection string from Streamlit secrets
        try:
            connection_string = st.secrets["mongodb"]["connection_string"]
        except (KeyError, FileNotFoundError):
            st.error("MongoDB connection string not configured!")
            st.info(
                "Please add your MongoDB connection string to Streamlit Cloud:\n\n"
                "1. Go to your app settings\n"
                "2. Click on 'Secrets'\n"
                '3. Add:\n```\n[mongodb]\nconnection_string = "your_connection_string_here"\n```'
            )
            st.stop()

        client = MongoClient(
            connection_string,
            serverSelectionTimeoutMS=5000,
        )
        client.admin.command("ping")
        return client
    except Exception as e:
        st.error(f"MongoDB Connection Failed: {e}")
        st.stop()


client = init_connection()
db = client["stealth_monitor"]
users_collection = db["users"]
activities_collection = db["activities"]
screenshots_collection = db["screenshots"]


# ==================== HELPER FUNCTIONS ====================
def seconds_to_hms(seconds):
    """Convert seconds to HH:MM:SS format"""
    if pd.isna(seconds) or seconds == 0:
        return "00:00:00"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_time_metric(seconds):
    """Format time for metric display"""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"


@st.cache_data(ttl=30)
def get_all_users():
    """Get list of all users"""
    users = list(users_collection.find({}, {"username": 1, "_id": 0}))
    return [u["username"] for u in users]


@st.cache_data(ttl=30)
def get_user_data(username):
    """Get complete user data"""
    return users_collection.find_one({"username": username})


@st.cache_data(ttl=30)
def get_date_range_data(username, start_date, end_date):
    """Get user data for a date range"""
    user_doc = get_user_data(username)
    if not user_doc or "dates" not in user_doc:
        return []

    filtered_dates = []
    for date_entry in user_doc["dates"]:
        date_obj = datetime.strptime(date_entry["date"], "%Y-%m-%d").date()
        if start_date <= date_obj <= end_date:
            filtered_dates.append(date_entry)

    return filtered_dates


def extract_usage_data(usage_breakdown):
    """Extract and aggregate usage data from breakdown"""
    usage_data = []
    for category, items in usage_breakdown.items():
        for app_name, app_data in items.items():
            usage_data.append(
                {
                    "category": category.capitalize(),
                    "application": app_name,
                    "total_time": app_data.get("total_time", 0),
                    "visits": len(app_data.get("visits", [])),
                }
            )
    return usage_data


# ==================== EXPORT FUNCTIONS ====================
@st.cache_data
def convert_df_to_csv(df):
    """Convert DataFrame to CSV"""
    return df.to_csv(index=False).encode("utf-8")


def fig_to_base64(fig):
    """Convert Plotly figure to base64 encoded image"""
    img_bytes = fig.to_image(format="png", width=800, height=400)
    return base64.b64encode(img_bytes).decode()


def create_pdf_report(title, data_dict, figures_dict=None):
    """
    Create a PDF report with data tables and graphs

    Args:
        title: Report title
        data_dict: Dictionary of {section_name: dataframe}
        figures_dict: Dictionary of {figure_name: plotly_figure}
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50,
    )

    # Container for the 'Flowable' objects
    elements = []

    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=24,
        textColor=colors.HexColor("#2c3e50"),
        spaceAfter=30,
        alignment=TA_CENTER,
    )

    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=16,
        textColor=colors.HexColor("#34495e"),
        spaceAfter=12,
        spaceBefore=12,
    )

    # Add title
    elements.append(Paragraph(title, title_style))
    elements.append(Spacer(1, 12))

    # Add timestamp
    timestamp = Paragraph(
        f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        styles["Normal"],
    )
    elements.append(timestamp)
    elements.append(Spacer(1, 20))

    # Add data tables
    for section_name, df in data_dict.items():
        # Section heading
        elements.append(Paragraph(section_name, heading_style))
        elements.append(Spacer(1, 12))

        # Prepare table data
        if not df.empty:
            # Limit to first 50 rows for PDF
            display_df = df.head(50)
            table_data = [display_df.columns.tolist()] + display_df.values.tolist()

            # Create table
            col_widths = [letter[0] / len(df.columns)] * len(df.columns)
            table = Table(table_data, colWidths=col_widths)

            # Style the table
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3498db")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                        ("FONTSIZE", (0, 1), (-1, -1), 8),
                    ]
                )
            )

            elements.append(table)
            elements.append(Spacer(1, 20))
        else:
            elements.append(Paragraph("No data available", styles["Normal"]))
            elements.append(Spacer(1, 12))

    # Add graphs
    if figures_dict:
        elements.append(PageBreak())
        elements.append(Paragraph("Visual Analytics", title_style))
        elements.append(Spacer(1, 20))

        for fig_name, fig in figures_dict.items():
            try:
                # Section heading for graph
                elements.append(Paragraph(fig_name, heading_style))
                elements.append(Spacer(1, 12))

                # Convert figure to image and add to PDF
                img_buffer = io.BytesIO()
                fig.write_image(img_buffer, format="png", width=700, height=400)
                img_buffer.seek(0)

                img = Image(img_buffer, width=6 * inch, height=3.5 * inch)
                elements.append(img)
                elements.append(Spacer(1, 20))
            except Exception as e:
                elements.append(
                    Paragraph(f"Could not render graph: {str(e)}", styles["Normal"])
                )
                elements.append(Spacer(1, 12))

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer


# ==================== SIDEBAR NAVIGATION ====================
st.sidebar.title("Navigation")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Select Dashboard Page",
    [
        "Overview",
        "User Analysis",
        "Session Details",
        "Trends & Patterns",
        "App & URL Analysis",
        "Screenshots",
    ],
)

st.sidebar.markdown("---")
st.sidebar.info(f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ==================== PAGE: OVERVIEW ====================
if page == "Overview":
    st.title("Overview Dashboard")
    st.markdown("### System-wide productivity metrics and KPIs")

    # Get all users
    all_users = get_all_users()

    if not all_users:
        st.error("No users found in database")
        st.stop()

    # Aggregate metrics across all users
    total_users = len(all_users)
    total_sessions = 0
    total_productive = 0
    total_wasted = 0
    total_idle = 0
    total_neutral = 0

    # Date filter
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date", datetime.now().date() - timedelta(days=7)
        )
    with col2:
        end_date = st.date_input("End Date", datetime.now().date())

    # Aggregate data
    user_stats = []
    for username in all_users:
        date_data = get_date_range_data(username, start_date, end_date)

        user_productive = 0
        user_wasted = 0
        user_idle = 0
        user_neutral = 0
        user_sessions = 0

        for date_entry in date_data:
            for session in date_entry.get("sessions", []):
                user_sessions += 1
                total_sessions += 1

                user_productive += session.get("productive_time", 0)
                user_wasted += session.get("wasted_time", 0)
                user_idle += session.get("idle_time", 0)
                user_neutral += session.get("neutral_time", 0)

        total_productive += user_productive
        total_wasted += user_wasted
        total_idle += user_idle
        total_neutral += user_neutral

        if user_sessions > 0:
            user_stats.append(
                {
                    "username": username,
                    "sessions": user_sessions,
                    "productive": user_productive,
                    "wasted": user_wasted,
                    "idle": user_idle,
                    "neutral": user_neutral,
                    "total": user_productive + user_wasted + user_idle + user_neutral,
                }
            )

    # Key Metrics Row
    st.markdown("### Key Performance Indicators")
    col1, col2, col3, col4, col5 = st.columns(5)

    total_time = total_productive + total_wasted + total_idle + total_neutral

    with col1:
        st.metric("Total Users", total_users, help="Total number of monitored users")

    with col2:
        st.metric("Total Sessions", total_sessions, help="Total monitoring sessions")

    with col3:
        productivity_rate = (
            (total_productive / total_time * 100) if total_time > 0 else 0
        )
        st.metric(
            "Productivity Rate",
            f"{productivity_rate:.1f}%",
            help="Percentage of productive time",
        )

    with col4:
        st.metric(
            "Total Active Time",
            format_time_metric(total_time),
            help="Total monitored time (excluding breaks)",
        )

    with col5:
        avg_session_time = total_time / total_sessions if total_sessions > 0 else 0
        st.metric(
            "Avg Session",
            format_time_metric(avg_session_time),
            help="Average session duration",
        )

    st.markdown("---")

    # Activity Distribution Chart
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### Activity Distribution")
        activity_data = pd.DataFrame(
            {
                "Activity": ["Productive", "Neutral", "Wasted", "Idle"],
                "Time (seconds)": [
                    total_productive,
                    total_neutral,
                    total_wasted,
                    total_idle,
                ],
                "Percentage": [
                    total_productive / total_time * 100 if total_time > 0 else 0,
                    total_neutral / total_time * 100 if total_time > 0 else 0,
                    total_wasted / total_time * 100 if total_time > 0 else 0,
                    total_idle / total_time * 100 if total_time > 0 else 0,
                ],
            }
        )

        fig_pie = px.pie(
            activity_data,
            values="Time (seconds)",
            names="Activity",
            title="Overall Activity Breakdown",
            color="Activity",
            color_discrete_map={
                "Productive": "#2ecc71",
                "Neutral": "#3498db",
                "Wasted": "#e74c3c",
                "Idle": "#95a5a6",
            },
            hole=0.4,
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        st.markdown("### Time Breakdown")
        st.dataframe(
            activity_data.assign(
                **{"Time": activity_data["Time (seconds)"].apply(seconds_to_hms)}
            )[["Activity", "Time", "Percentage"]].style.format(
                {"Percentage": "{:.1f}%"}
            ),
            hide_index=True,
            use_container_width=True,
        )

    # User Comparison
    if user_stats:
        st.markdown("---")
        st.markdown("### User Performance Comparison")

        df_users = pd.DataFrame(user_stats)
        df_users["productivity_rate"] = (
            df_users["productive"] / df_users["total"] * 100
        ).fillna(0)
        df_users = df_users.sort_values("productivity_rate", ascending=False)

        fig_bar = px.bar(
            df_users,
            x="username",
            y=["productive", "neutral", "wasted", "idle"],
            title="User Activity Comparison",
            labels={"value": "Time (seconds)", "username": "User"},
            barmode="stack",
            color_discrete_map={
                "productive": "#2ecc71",
                "neutral": "#3498db",
                "wasted": "#e74c3c",
                "idle": "#95a5a6",
            },
        )
        fig_bar.update_layout(hovermode="x unified")
        st.plotly_chart(fig_bar, use_container_width=True)

        # User table with metrics
        st.markdown("### User Statistics Table")
        df_display = df_users.copy()
        df_display["total_time"] = df_display["total"].apply(seconds_to_hms)
        df_display["productive_time"] = df_display["productive"].apply(seconds_to_hms)
        df_display["productivity_rate"] = df_display["productivity_rate"].apply(
            lambda x: f"{x:.1f}%"
        )

        st.dataframe(
            df_display[
                [
                    "username",
                    "sessions",
                    "total_time",
                    "productive_time",
                    "productivity_rate",
                ]
            ].rename(
                columns={
                    "username": "User",
                    "sessions": "Sessions",
                    "total_time": "Total Time",
                    "productive_time": "Productive Time",
                    "productivity_rate": "Productivity %",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

        # Download buttons
        st.markdown("### Download Options")
        col1, col2 = st.columns(2)

        with col1:
            csv_data = convert_df_to_csv(df_users)
            st.download_button(
                label="Download CSV Report",
                data=csv_data,
                file_name=f"overview_user_stats_{start_date}_{end_date}.csv",
                mime="text/csv",
                help="Download raw data as CSV file",
            )

        with col2:
            try:
                # Prepare data for PDF
                pdf_tables = {
                    "User Statistics": df_display[
                        [
                            "username",
                            "sessions",
                            "total_time",
                            "productive_time",
                            "productivity_rate",
                        ]
                    ],
                    "Activity Breakdown": activity_data[
                        ["Activity", "Time", "Percentage"]
                    ],
                }

                # Prepare figures for PDF
                pdf_figures = {
                    "Activity Distribution": fig_pie,
                    "User Performance Comparison": fig_bar,
                }

                pdf_buffer = create_pdf_report(
                    f"Overview Report ({start_date} to {end_date})",
                    pdf_tables,
                    pdf_figures,
                )

                st.download_button(
                    label="Download Full Report (PDF)",
                    data=pdf_buffer,
                    file_name=f"overview_report_{start_date}_{end_date}.pdf",
                    mime="application/pdf",
                    help="Download comprehensive report with graphs and data",
                )
            except Exception as e:
                st.warning(
                    f"PDF generation requires additional packages. Install with: pip install reportlab kaleido"
                )

# ==================== PAGE: USER ANALYSIS ====================
elif page == "User Analysis":
    st.title("User Analysis")
    st.markdown("### Detailed productivity analysis for individual users")

    all_users = get_all_users()

    if not all_users:
        st.error("No users found")
        st.stop()

    # User selection
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        selected_user = st.selectbox("Select User", all_users)
    with col2:
        start_date = st.date_input(
            "From", datetime.now().date() - timedelta(days=7), key="user_start"
        )
    with col3:
        end_date = st.date_input("To", datetime.now().date(), key="user_end")

    # Get user data
    user_data = get_user_data(selected_user)
    if not user_data:
        st.error("No data found for this user")
        st.stop()

    # Get date range data
    date_data = get_date_range_data(selected_user, start_date, end_date)

    if not date_data:
        st.warning("No data available for selected date range")
        st.stop()

    # Aggregate user metrics
    total_sessions = 0
    total_productive = 0
    total_wasted = 0
    total_idle = 0
    total_neutral = 0
    daily_stats = []

    for date_entry in date_data:
        date_str = date_entry["date"]
        day_productive = 0
        day_wasted = 0
        day_idle = 0
        day_neutral = 0
        day_sessions = 0

        for session in date_entry.get("sessions", []):
            total_sessions += 1
            day_sessions += 1

            prod = session.get("productive_time", 0)
            waste = session.get("wasted_time", 0)
            idle = session.get("idle_time", 0)
            neutral = session.get("neutral_time", 0)

            total_productive += prod
            total_wasted += waste
            total_idle += idle
            total_neutral += neutral

            day_productive += prod
            day_wasted += waste
            day_idle += idle
            day_neutral += neutral

        day_total = day_productive + day_wasted + day_idle + day_neutral
        daily_stats.append(
            {
                "date": date_str,
                "sessions": day_sessions,
                "productive": day_productive,
                "wasted": day_wasted,
                "idle": day_idle,
                "neutral": day_neutral,
                "total": day_total,
                "productivity_rate": (
                    (day_productive / day_total * 100) if day_total > 0 else 0
                ),
            }
        )

    total_time = total_productive + total_wasted + total_idle + total_neutral
    productivity_rate = (total_productive / total_time * 100) if total_time > 0 else 0

    # User KPIs
    st.markdown("### User Performance Metrics")
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total Sessions", total_sessions)
    with col2:
        st.metric("Productivity Rate", f"{productivity_rate:.1f}%")
    with col3:
        st.metric("Productive Time", format_time_metric(total_productive))
    with col4:
        st.metric("Wasted Time", format_time_metric(total_wasted))
    with col5:
        st.metric("Total Time", format_time_metric(total_time))

    st.markdown("---")

    # Daily trend chart
    st.markdown("### Daily Productivity Trend")
    df_daily = pd.DataFrame(daily_stats)
    df_daily["date"] = pd.to_datetime(df_daily["date"])
    df_daily = df_daily.sort_values("date")

    fig_trend = go.Figure()

    fig_trend.add_trace(
        go.Scatter(
            x=df_daily["date"],
            y=df_daily["productive"],
            name="Productive",
            fill="tonexty",
            line=dict(color="#2ecc71", width=2),
        )
    )

    fig_trend.add_trace(
        go.Scatter(
            x=df_daily["date"],
            y=df_daily["wasted"],
            name="Wasted",
            fill="tonexty",
            line=dict(color="#e74c3c", width=2),
        )
    )

    fig_trend.add_trace(
        go.Scatter(
            x=df_daily["date"],
            y=df_daily["idle"],
            name="Idle",
            fill="tonexty",
            line=dict(color="#95a5a6", width=2),
        )
    )

    fig_trend.update_layout(
        title="Time Distribution Over Days",
        xaxis_title="Date",
        yaxis_title="Time (seconds)",
        hovermode="x unified",
        height=400,
    )

    st.plotly_chart(fig_trend, use_container_width=True)

    # Productivity rate trend
    fig_prod_rate = px.line(
        df_daily,
        x="date",
        y="productivity_rate",
        title="Productivity Rate Trend",
        markers=True,
        labels={"productivity_rate": "Productivity %", "date": "Date"},
    )
    fig_prod_rate.update_traces(line_color="#3498db", line_width=3)
    fig_prod_rate.add_hline(
        y=productivity_rate,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Avg: {productivity_rate:.1f}%",
    )
    st.plotly_chart(fig_prod_rate, use_container_width=True)

    # Daily statistics table
    st.markdown("### Daily Statistics")
    df_display = df_daily.copy()
    df_display["total_time"] = df_display["total"].apply(seconds_to_hms)
    df_display["productive_time"] = df_display["productive"].apply(seconds_to_hms)
    df_display["productivity_%"] = df_display["productivity_rate"].apply(
        lambda x: f"{x:.1f}%"
    )
    df_display["date"] = df_display["date"].dt.strftime("%Y-%m-%d")

    st.dataframe(
        df_display[
            ["date", "sessions", "total_time", "productive_time", "productivity_%"]
        ].rename(
            columns={
                "date": "Date",
                "sessions": "Sessions",
                "total_time": "Total Time",
                "productive_time": "Productive Time",
            }
        ),
        hide_index=True,
        use_container_width=True,
    )

    # Download buttons
    st.markdown("### Download Options")
    col1, col2 = st.columns(2)

    with col1:
        csv_data = convert_df_to_csv(df_daily)
        st.download_button(
            label="Download CSV Report",
            data=csv_data,
            file_name=f"user_analysis_{selected_user}_{start_date}_{end_date}.csv",
            mime="text/csv",
            help="Download raw data as CSV file",
        )

    with col2:
        try:
            # Prepare data for PDF
            pdf_tables = {
                "Daily Statistics": df_display[
                    [
                        "date",
                        "sessions",
                        "total_time",
                        "productive_time",
                        "productivity_%",
                    ]
                ]
            }

            # Prepare figures for PDF
            pdf_figures = {
                "Daily Productivity Trend": fig_trend,
                "Productivity Rate Trend": fig_prod_rate,
            }

            pdf_buffer = create_pdf_report(
                f"User Analysis Report - {selected_user} ({start_date} to {end_date})",
                pdf_tables,
                pdf_figures,
            )

            st.download_button(
                label="Download Full Report (PDF)",
                data=pdf_buffer,
                file_name=f"user_analysis_{selected_user}_{start_date}_{end_date}.pdf",
                mime="application/pdf",
                help="Download comprehensive report with graphs and data",
            )
        except Exception as e:
            st.warning(
                f"PDF generation requires additional packages. Install with: pip install reportlab kaleido"
            )

# ==================== PAGE: SESSION DETAILS ====================
elif page == "Session Details":
    st.title("Session Details")
    st.markdown("### Detailed breakdown of individual monitoring sessions")

    all_users = get_all_users()

    if not all_users:
        st.error("No users found")
        st.stop()

    # User and date selection
    col1, col2 = st.columns(2)
    with col1:
        selected_user = st.selectbox("Select User", all_users, key="session_user")
    with col2:
        user_data = get_user_data(selected_user)
        if user_data and "dates" in user_data:
            dates_list = [d["date"] for d in user_data["dates"]]
            selected_date = st.selectbox(
                "Select Date", sorted(dates_list, reverse=True)
            )
        else:
            st.warning("No dates available for this user")
            st.stop()

    # Get sessions for selected date
    sessions = []
    for date_entry in user_data["dates"]:
        if date_entry["date"] == selected_date:
            sessions = date_entry.get("sessions", [])
            break

    if not sessions:
        st.warning("No sessions found for selected date")
        st.stop()

    # Sessions overview
    st.markdown("### Sessions Overview")
    session_summary = []
    for session in sessions:
        session_summary.append(
            {
                "Session ID": session["session_id"],
                "Start": session["start_time"],
                "End": session["end_time"],
                "Duration": seconds_to_hms(session.get("total_time", 0)),
                "Productive": seconds_to_hms(session.get("productive_time", 0)),
                "Wasted": seconds_to_hms(session.get("wasted_time", 0)),
                "Idle": seconds_to_hms(session.get("idle_time", 0)),
                "Shift": session.get("session_shift", "N/A"),
            }
        )

    df_sessions = pd.DataFrame(session_summary)
    st.dataframe(df_sessions, hide_index=True, use_container_width=True)

    # Select session for detailed analysis
    st.markdown("---")
    session_ids = [s["session_id"] for s in sessions]
    selected_session_id = st.selectbox(
        "Select Session for Detailed Analysis", session_ids
    )

    # Get selected session data
    selected_session = next(
        s for s in sessions if s["session_id"] == selected_session_id
    )

    # Session metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Duration", seconds_to_hms(selected_session.get("total_time", 0)))
    with col2:
        prod_time = selected_session.get("productive_time", 0)
        total_time = selected_session.get("total_time", 1)
        st.metric("Productivity", f"{prod_time/total_time*100:.1f}%")
    with col3:
        st.metric("Start Time", selected_session["start_time"])
    with col4:
        st.metric("End Time", selected_session["end_time"])

    st.markdown("---")

    # Activity breakdown pie chart
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Activity Distribution")
        activity_data = {
            "Activity": ["Productive", "Neutral", "Wasted", "Idle"],
            "Time": [
                selected_session.get("productive_time", 0),
                selected_session.get("neutral_time", 0),
                selected_session.get("wasted_time", 0),
                selected_session.get("idle_time", 0),
            ],
        }
        df_activity = pd.DataFrame(activity_data)

        fig_pie = px.pie(
            df_activity,
            values="Time",
            names="Activity",
            color="Activity",
            color_discrete_map={
                "Productive": "#2ecc71",
                "Neutral": "#3498db",
                "Wasted": "#e74c3c",
                "Idle": "#95a5a6",
            },
            hole=0.4,
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        st.markdown("### Time Breakdown")
        df_activity["Time (HH:MM:SS)"] = df_activity["Time"].apply(seconds_to_hms)
        df_activity["Percentage"] = (
            df_activity["Time"] / df_activity["Time"].sum() * 100
        ).apply(lambda x: f"{x:.1f}%")
        st.dataframe(
            df_activity[["Activity", "Time (HH:MM:SS)", "Percentage"]],
            hide_index=True,
            use_container_width=True,
        )

    # Usage breakdown
    st.markdown("---")
    st.markdown("### Application & Website Usage")

    usage_breakdown = selected_session.get("usage_breakdown", {})
    usage_data = extract_usage_data(usage_breakdown)

    if usage_data:
        df_usage = pd.DataFrame(usage_data)
        df_usage = df_usage.sort_values("total_time", ascending=False)

        # Top applications bar chart
        fig_apps = px.bar(
            df_usage.head(15),
            x="total_time",
            y="application",
            color="category",
            title="Top 15 Applications/Websites by Time",
            labels={
                "total_time": "Time (seconds)",
                "application": "Application/Website",
            },
            orientation="h",
            color_discrete_map={
                "Productive": "#2ecc71",
                "Neutral": "#3498db",
                "Wasted": "#e74c3c",
                "Idle": "#95a5a6",
            },
        )
        fig_apps.update_layout(height=500)
        st.plotly_chart(fig_apps, use_container_width=True)

        # Detailed usage table
        df_usage_display = df_usage.copy()
        df_usage_display["time_formatted"] = df_usage_display["total_time"].apply(
            seconds_to_hms
        )
        df_usage_display = df_usage_display[
            ["application", "category", "time_formatted", "visits"]
        ].rename(
            columns={
                "application": "Application/Website",
                "category": "Category",
                "time_formatted": "Total Time",
                "visits": "Visits",
            }
        )

        st.markdown("#### Detailed Usage Table")
        st.dataframe(df_usage_display, hide_index=True, use_container_width=True)

        # Download buttons
        st.markdown("### Download Options")
        col1, col2 = st.columns(2)

        with col1:
            csv_data = convert_df_to_csv(df_usage)
            st.download_button(
                label="Download Session CSV",
                data=csv_data,
                file_name=f"session_{selected_session_id}_{selected_date}.csv",
                mime="text/csv",
                help="Download session usage data as CSV",
            )

        with col2:
            try:
                # Prepare data for PDF
                pdf_tables = {
                    "Session Information": pd.DataFrame(
                        [
                            {
                                "Session ID": selected_session_id,
                                "Date": selected_date,
                                "Start": selected_session["start_time"],
                                "End": selected_session["end_time"],
                                "Duration": seconds_to_hms(
                                    selected_session.get("total_time", 0)
                                ),
                            }
                        ]
                    ),
                    "Activity Breakdown": df_activity[
                        ["Activity", "Time (HH:MM:SS)", "Percentage"]
                    ],
                    "Application Usage": df_usage_display.head(30),
                }

                # Prepare figures for PDF
                pdf_figures = {
                    "Activity Distribution": fig_pie,
                    "Top Applications": fig_apps,
                }

                pdf_buffer = create_pdf_report(
                    f"Session Details Report - {selected_session_id} ({selected_date})",
                    pdf_tables,
                    pdf_figures,
                )

                st.download_button(
                    label="Download Full Report (PDF)",
                    data=pdf_buffer,
                    file_name=f"session_report_{selected_session_id}_{selected_date}.pdf",
                    mime="application/pdf",
                    help="Download comprehensive session report with graphs",
                )
            except Exception as e:
                st.warning(
                    f"PDF generation requires additional packages. Install with: pip install reportlab kaleido"
                )

# ==================== PAGE: TRENDS & PATTERNS ====================
elif page == "Trends & Patterns":
    st.title("Trends & Patterns")
    st.markdown("### Long-term productivity trends and pattern analysis")

    all_users = get_all_users()

    if not all_users:
        st.error("No users found")
        st.stop()

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        selected_user = st.selectbox("Select User", all_users, key="trends_user")
    with col2:
        start_date = st.date_input(
            "From", datetime.now().date() - timedelta(days=30), key="trends_start"
        )
    with col3:
        end_date = st.date_input("To", datetime.now().date(), key="trends_end")

    # Get data
    date_data = get_date_range_data(selected_user, start_date, end_date)

    if not date_data:
        st.warning("No data available for selected date range")
        st.stop()

    # Aggregate hourly data
    hourly_data = defaultdict(
        lambda: {"productive": 0, "wasted": 0, "idle": 0, "neutral": 0, "count": 0}
    )
    daily_data = []
    weekly_data = defaultdict(
        lambda: {"productive": 0, "wasted": 0, "idle": 0, "neutral": 0}
    )

    for date_entry in date_data:
        date_str = date_entry["date"]
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        weekday = date_obj.strftime("%A")

        day_productive = 0
        day_wasted = 0
        day_idle = 0
        day_neutral = 0

        for session in date_entry.get("sessions", []):
            # Extract hour from start_time
            try:
                start_time = datetime.strptime(session["start_time"], "%H:%M:%S")
                hour = start_time.hour

                hourly_data[hour]["productive"] += session.get("productive_time", 0)
                hourly_data[hour]["wasted"] += session.get("wasted_time", 0)
                hourly_data[hour]["idle"] += session.get("idle_time", 0)
                hourly_data[hour]["neutral"] += session.get("neutral_time", 0)
                hourly_data[hour]["count"] += 1
            except:
                pass

            # Daily aggregation
            day_productive += session.get("productive_time", 0)
            day_wasted += session.get("wasted_time", 0)
            day_idle += session.get("idle_time", 0)
            day_neutral += session.get("neutral_time", 0)

            # Weekly aggregation
            weekly_data[weekday]["productive"] += session.get("productive_time", 0)
            weekly_data[weekday]["wasted"] += session.get("wasted_time", 0)
            weekly_data[weekday]["idle"] += session.get("idle_time", 0)
            weekly_data[weekday]["neutral"] += session.get("neutral_time", 0)

        day_total = day_productive + day_wasted + day_idle + day_neutral
        daily_data.append(
            {
                "date": date_str,
                "weekday": weekday,
                "productive": day_productive,
                "wasted": day_wasted,
                "idle": day_idle,
                "neutral": day_neutral,
                "total": day_total,
            }
        )

    # Hourly productivity pattern
    st.markdown("### Hourly Productivity Pattern")
    hourly_df = pd.DataFrame(
        [
            {
                "hour": f"{h:02d}:00",
                "productive": data["productive"],
                "wasted": data["wasted"],
                "idle": data["idle"],
                "neutral": data["neutral"],
            }
            for h, data in sorted(hourly_data.items())
        ]
    )

    fig_hourly = None
    if not hourly_df.empty:
        fig_hourly = go.Figure()
        fig_hourly.add_trace(
            go.Bar(
                name="Productive",
                x=hourly_df["hour"],
                y=hourly_df["productive"],
                marker_color="#2ecc71",
            )
        )
        fig_hourly.add_trace(
            go.Bar(
                name="Neutral",
                x=hourly_df["hour"],
                y=hourly_df["neutral"],
                marker_color="#3498db",
            )
        )
        fig_hourly.add_trace(
            go.Bar(
                name="Wasted",
                x=hourly_df["hour"],
                y=hourly_df["wasted"],
                marker_color="#e74c3c",
            )
        )
        fig_hourly.add_trace(
            go.Bar(
                name="Idle",
                x=hourly_df["hour"],
                y=hourly_df["idle"],
                marker_color="#95a5a6",
            )
        )

        fig_hourly.update_layout(
            barmode="stack",
            title="Activity Distribution by Hour of Day",
            xaxis_title="Hour",
            yaxis_title="Time (seconds)",
            height=400,
            hovermode="x unified",
        )
        st.plotly_chart(fig_hourly, use_container_width=True)

    # Weekly pattern
    st.markdown("### Weekly Productivity Pattern")
    weekday_order = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    weekly_df = pd.DataFrame(
        [
            {
                "weekday": day,
                "productive": weekly_data[day]["productive"],
                "wasted": weekly_data[day]["wasted"],
                "idle": weekly_data[day]["idle"],
                "neutral": weekly_data[day]["neutral"],
            }
            for day in weekday_order
            if day in weekly_data
        ]
    )

    fig_weekly = None
    if not weekly_df.empty:
        fig_weekly = px.bar(
            weekly_df,
            x="weekday",
            y=["productive", "neutral", "wasted", "idle"],
            title="Activity Distribution by Day of Week",
            labels={"value": "Time (seconds)", "weekday": "Day"},
            barmode="stack",
            color_discrete_map={
                "productive": "#2ecc71",
                "neutral": "#3498db",
                "wasted": "#e74c3c",
                "idle": "#95a5a6",
            },
        )
        st.plotly_chart(fig_weekly, use_container_width=True)

    # Daily timeline
    st.markdown("### Daily Timeline")
    df_daily = pd.DataFrame(daily_data)
    df_daily["date"] = pd.to_datetime(df_daily["date"])
    df_daily = df_daily.sort_values("date")
    df_daily["productivity_rate"] = (
        df_daily["productive"] / df_daily["total"] * 100
    ).fillna(0)

    fig_timeline = go.Figure()
    fig_timeline.add_trace(
        go.Scatter(
            x=df_daily["date"],
            y=df_daily["productive"],
            name="Productive",
            stackgroup="one",
            fillcolor="#2ecc71",
        )
    )
    fig_timeline.add_trace(
        go.Scatter(
            x=df_daily["date"],
            y=df_daily["neutral"],
            name="Neutral",
            stackgroup="one",
            fillcolor="#3498db",
        )
    )
    fig_timeline.add_trace(
        go.Scatter(
            x=df_daily["date"],
            y=df_daily["wasted"],
            name="Wasted",
            stackgroup="one",
            fillcolor="#e74c3c",
        )
    )
    fig_timeline.add_trace(
        go.Scatter(
            x=df_daily["date"],
            y=df_daily["idle"],
            name="Idle",
            stackgroup="one",
            fillcolor="#95a5a6",
        )
    )

    fig_timeline.update_layout(
        title="Daily Activity Timeline",
        xaxis_title="Date",
        yaxis_title="Time (seconds)",
        height=400,
        hovermode="x unified",
    )
    st.plotly_chart(fig_timeline, use_container_width=True)

    # Download buttons
    st.markdown("### Download Options")
    col1, col2 = st.columns(2)

    with col1:
        # Prepare CSV data
        df_daily_export = df_daily.copy()
        df_daily_export["date"] = df_daily_export["date"].dt.strftime("%Y-%m-%d")
        csv_data = convert_df_to_csv(df_daily_export)
        st.download_button(
            label="Download Trends CSV",
            data=csv_data,
            file_name=f"trends_{selected_user}_{start_date}_{end_date}.csv",
            mime="text/csv",
            help="Download trends data as CSV",
        )

    with col2:
        try:
            # Prepare data for PDF
            df_display = df_daily.copy()
            df_display["date"] = df_display["date"].dt.strftime("%Y-%m-%d")

            pdf_tables = {
                "Daily Trends": df_display[
                    ["date", "weekday", "productive", "wasted", "idle", "neutral"]
                ].head(30),
                "Weekly Summary": weekly_df if not weekly_df.empty else pd.DataFrame(),
            }

            # Prepare figures for PDF
            pdf_figures = {}
            if fig_hourly:
                pdf_figures["Hourly Pattern"] = fig_hourly
            if fig_weekly:
                pdf_figures["Weekly Pattern"] = fig_weekly
            pdf_figures["Daily Timeline"] = fig_timeline

            pdf_buffer = create_pdf_report(
                f"Trends & Patterns Report - {selected_user} ({start_date} to {end_date})",
                pdf_tables,
                pdf_figures,
            )

            st.download_button(
                label="Download Full Report (PDF)",
                data=pdf_buffer,
                file_name=f"trends_report_{selected_user}_{start_date}_{end_date}.pdf",
                mime="application/pdf",
                help="Download comprehensive trends report with graphs",
            )
        except Exception as e:
            st.warning(
                f"PDF generation requires additional packages. Install with: pip install reportlab kaleido"
            )


# ==================== PAGE: APP & URL ANALYSIS ====================
elif page == "App & URL Analysis":
    st.title("Application & Website Usage Analysis")
    st.markdown("### Detailed breakdown of application and website usage")

    all_users = get_all_users()

    if not all_users:
        st.error("No users found")
        st.stop()

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        selected_user = st.selectbox("Select User", all_users, key="app_user")
    with col2:
        start_date = st.date_input(
            "From", datetime.now().date() - timedelta(days=7), key="app_start"
        )
    with col3:
        end_date = st.date_input("To", datetime.now().date(), key="app_end")

    date_data = get_date_range_data(selected_user, start_date, end_date)

    if not date_data:
        st.warning("No data available for selected date range")
        st.stop()

    # Aggregate usage data
    app_usage = defaultdict(
        lambda: {"productive": 0, "wasted": 0, "idle": 0, "neutral": 0, "visits": 0}
    )

    for date_entry in date_data:
        for session in date_entry.get("sessions", []):
            usage_breakdown = session.get("usage_breakdown", {})

            for category, items in usage_breakdown.items():
                for app_name, app_data in items.items():
                    app_usage[app_name][category] += app_data.get("total_time", 0)
                    app_usage[app_name]["visits"] += len(app_data.get("visits", []))

    # Convert to DataFrame
    usage_list = []
    for app_name, data in app_usage.items():
        total_time = (
            data["productive"] + data["wasted"] + data["idle"] + data["neutral"]
        )

        # Determine primary category
        primary_category = max(
            ["productive", "wasted", "idle", "neutral"], key=lambda k: data[k]
        )

        usage_list.append(
            {
                "application": app_name,
                "category": primary_category.capitalize(),
                "total_time": total_time,
                "productive": data["productive"],
                "wasted": data["wasted"],
                "idle": data["idle"],
                "neutral": data["neutral"],
                "visits": data["visits"],
            }
        )

    df_usage = pd.DataFrame(usage_list)
    df_usage = df_usage.sort_values("total_time", ascending=False)

    # Top applications
    st.markdown("### Top Applications/Websites")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### By Total Time")
        top_by_time = df_usage.head(10)
        fig_top_time = px.bar(
            top_by_time,
            y="application",
            x="total_time",
            color="category",
            title="Top 10 by Time Spent",
            labels={"total_time": "Time (seconds)", "application": "Application"},
            orientation="h",
            color_discrete_map={
                "Productive": "#2ecc71",
                "Neutral": "#3498db",
                "Wasted": "#e74c3c",
                "Idle": "#95a5a6",
            },
        )
        st.plotly_chart(fig_top_time, use_container_width=True)

    with col2:
        st.markdown("#### By Number of Visits")
        top_by_visits = df_usage.nlargest(10, "visits")
        fig_top_visits = px.bar(
            top_by_visits,
            y="application",
            x="visits",
            color="category",
            title="Top 10 by Visits",
            labels={"visits": "Number of Visits", "application": "Application"},
            orientation="h",
            color_discrete_map={
                "Productive": "#2ecc71",
                "Neutral": "#3498db",
                "Wasted": "#e74c3c",
                "Idle": "#95a5a6",
            },
        )
        st.plotly_chart(fig_top_visits, use_container_width=True)

    # Category distribution
    st.markdown("---")
    st.markdown("### Usage by Category")

    category_totals = df_usage.groupby("category")["total_time"].sum().reset_index()

    fig_category = px.pie(
        category_totals,
        values="total_time",
        names="category",
        title="Time Distribution by Category",
        color="category",
        color_discrete_map={
            "Productive": "#2ecc71",
            "Neutral": "#3498db",
            "Wasted": "#e74c3c",
            "Idle": "#95a5a6",
        },
    )
    st.plotly_chart(fig_category, use_container_width=True)

    # Detailed table
    st.markdown("---")
    st.markdown("### Detailed Usage Table")

    df_display = df_usage.copy()
    df_display["time_formatted"] = df_display["total_time"].apply(seconds_to_hms)
    df_display_table = df_display[
        ["application", "category", "time_formatted", "visits"]
    ].rename(
        columns={
            "application": "Application/Website",
            "category": "Primary Category",
            "time_formatted": "Total Time",
            "visits": "Total Visits",
        }
    )

    st.dataframe(
        df_display_table, hide_index=True, use_container_width=True, height=600
    )

    # Download buttons
    st.markdown("### Download Options")
    col1, col2 = st.columns(2)

    with col1:
        csv_data = convert_df_to_csv(df_usage)
        st.download_button(
            label="Download App Usage CSV",
            data=csv_data,
            file_name=f"app_usage_{selected_user}_{start_date}_{end_date}.csv",
            mime="text/csv",
            help="Download application usage data as CSV",
        )

    with col2:
        try:
            # Prepare data for PDF
            pdf_tables = {
                "Top Applications": df_display_table.head(30),
                "Category Summary": category_totals,
            }

            # Prepare figures for PDF
            pdf_figures = {
                "Top Applications by Time": fig_top_time,
                "Top Applications by Visits": fig_top_visits,
                "Category Distribution": fig_category,
            }

            pdf_buffer = create_pdf_report(
                f"Application Usage Report - {selected_user} ({start_date} to {end_date})",
                pdf_tables,
                pdf_figures,
            )

            st.download_button(
                label="Download Full Report (PDF)",
                data=pdf_buffer,
                file_name=f"app_usage_report_{selected_user}_{start_date}_{end_date}.pdf",
                mime="application/pdf",
                help="Download comprehensive app usage report with graphs",
            )
        except Exception as e:
            st.warning(
                f"PDF generation requires additional packages. Install with: pip install reportlab kaleido"
            )

# ==================== PAGE: SCREENSHOTS ====================
elif page == "Screenshots":
    st.title("Screenshots")
    st.markdown("### View captured screenshots from monitoring sessions")

    all_users = get_all_users()

    if not all_users:
        st.error("No users found")
        st.stop()

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        selected_user = st.selectbox("Select User", all_users, key="screenshot_user")
    with col2:
        start_date = st.date_input(
            "From", datetime.now().date() - timedelta(days=7), key="screenshot_start"
        )
    with col3:
        end_date = st.date_input("To", datetime.now().date(), key="screenshot_end")

    # Query screenshots collection
    try:
        screenshots = list(
            screenshots_collection.find(
                {
                    "username": selected_user,
                    "timestamp": {
                        "$gte": start_date.isoformat(),
                        "$lte": (end_date + timedelta(days=1)).isoformat(),
                    },
                }
            )
            .sort("timestamp", -1)
            .limit(100)
        )

        if not screenshots:
            st.info("No screenshots found for the selected criteria")
        else:
            st.success(f"Found {len(screenshots)} screenshots")

            # Display screenshots metadata
            screenshot_data = []
            for sc in screenshots:
                screenshot_data.append(
                    {
                        "Timestamp": sc.get("timestamp", "N/A"),
                        "Session ID": sc.get("session_id", "N/A"),
                        "Resolution": sc.get("screen_resolution", "N/A"),
                        "Size": f"{sc.get('file_size_bytes', 0) / 1024:.1f} KB",
                        "Path": sc.get("path", "N/A"),
                    }
                )

            df_screenshots = pd.DataFrame(screenshot_data)
            st.dataframe(df_screenshots, hide_index=True, use_container_width=True)

            # Download button for screenshots metadata
            csv_data = convert_df_to_csv(df_screenshots)
            st.download_button(
                label="Download Screenshots Metadata CSV",
                data=csv_data,
                file_name=f"screenshots_{selected_user}_{start_date}_{end_date}.csv",
                mime="text/csv",
                help="Download screenshots metadata as CSV",
            )

    except Exception as e:
        st.error(f"Error fetching screenshots: {e}")

# ==================== FOOTER ====================
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #7f8c8d; padding: 20px;'>"
    f"Data refreshes every 30 seconds | Last update: {datetime.now().strftime('%H:%M:%S')}"
    "</div>",
    unsafe_allow_html=True,
)
