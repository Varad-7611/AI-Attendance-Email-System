import streamlit as st
import os
import re
import json
import time
import pandas as pd
from dotenv import load_dotenv

# Import our backend agent components
from config.config import Config
from agent.drive_scanner import DriveScanner
from agent.sheet_reader import SheetReader
from agent.attendance_processor import AttendanceProcessor
from agent.ai_sheet_analyzer import AISheetAnalyzer
from agent.ai_email_generator import AIEmailGenerator
from agent.email_sender import EmailSender
from config.secret_loader import get_secret_with_aliases

# Page Configuration
st.set_page_config(
    page_title="AI Attendance Agent",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Premium Styling & Animations (Glassmorphism & Gradients)
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Space+Grotesk:wght@400;700&display=swap" rel="stylesheet">
<style>
    /* Main container fonts and theme overrides */
    html, body, [class*="css"], .stApp {
        font-family: 'Outfit', sans-serif;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 700;
    }

    /* GitHub Corner Link styling */
    .github-corner {
        position: fixed;
        top: 0;
        right: 0;
        z-index: 9999;
        border: 0;
    }
    
    /* Elegant Title Banner */
    .header-container {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 2.5rem;
        border-radius: 20px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.15);
        color: white;
        margin-bottom: 2rem;
        position: relative;
        overflow: hidden;
        animation: fadeIn 1.2s ease-out;
    }
    
    .header-container::after {
        content: '';
        position: absolute;
        width: 15rem;
        height: 15rem;
        background: rgba(255, 255, 255, 0.05);
        border-radius: 50%;
        top: -5rem;
        right: -5rem;
    }

    /* CSS Keyframe Animations */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .animated-card {
        animation: fadeIn 0.8s ease-out;
    }

    /* Glassmorphic Metrics Card */
    .metric-card {
        background: rgba(255, 255, 255, 0.06);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 1.5rem;
        border-radius: 16px;
        text-align: center;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
    }
    
    .metric-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 30px rgba(30, 60, 114, 0.15);
        border: 1px solid rgba(30, 60, 114, 0.3);
    }
    
    .metric-val {
        font-size: 2.5rem;
        font-weight: 800;
        margin: 0.5rem 0;
        background: linear-gradient(135deg, #12c2e9 0%, #c471ed 50%, #f64f59 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    /* Styled Badge tags for tables */
    .badge {
        padding: 0.3rem 0.8rem;
        border-radius: 30px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-block;
    }
    
    .badge-present {
        background-color: rgba(46, 204, 113, 0.15);
        color: #2ecc71;
        border: 1px solid rgba(46, 204, 113, 0.3);
    }
    
    .badge-absent {
        background-color: rgba(231, 76, 60, 0.15);
        color: #e74c3c;
        border: 1px solid rgba(231, 76, 60, 0.3);
    }

    /* Submitting Status Terminal scrolling style */
    .terminal-box {
        background-color: #0d1117;
        font-family: 'Courier New', Courier, monospace;
        color: #39ff14;
        padding: 1rem;
        border-radius: 10px;
        max-height: 300px;
        overflow-y: auto;
        border: 1px solid #30363d;
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)


# Helper: Parse GDrive URL or Folder ID
def extract_gdrive_id(url: str):
    url = url.strip()
    # Direct spreadsheet ID
    sheet_match = re.search(r"spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    if sheet_match:
        return sheet_match.group(1), "spreadsheet"
    # Folder ID
    folder_match = re.search(r"folders/([a-zA-Z0-9_-]+)", url)
    if folder_match:
        return folder_match.group(1), "folder"
    # Fallback to ID
    if "id=" in url:
        id_match = re.search(r"id=([a-zA-Z0-9_-]+)", url)
        if id_match:
            return id_match.group(1), "folder"
    if not url.startswith("http") and url != "":
        return url, "spreadsheet"
    return None, None

# Load initial env variables
load_dotenv()
try:
    default_config = Config.load()
except Exception:
    default_config = {
        "email_address": "",
        "email_password": "",
        "smtp_from_email": "",
        "smtp_from_name": "AI Attendance",
        "groq_api_key": "",
        "groq_model": "llama-3.3-70b-versatile",
        "google_drive_folder_id": "",
        "service_account_source": None
    }

# ----------------- SIDEBAR CONFIG -----------------
st.sidebar.markdown("<h2 style='text-align: center; margin-bottom: 0.5rem;'>⚙️ Configuration</h2>", unsafe_allow_html=True)
st.sidebar.markdown("<p style='text-align: center; font-size:0.9rem; color:#aaa;'>Configure your SMTP notifications & AI parameters below.</p>", unsafe_allow_html=True)

st.sidebar.divider()

# SMTP Credentials Section
st.sidebar.markdown("### ✉️ SMTP Sender Settings")
smtp_username = st.sidebar.text_input(
    "USERNAME EMAIL",
    value="",
    placeholder="Paste SMTP username email",
    help="SMTP Account username or authentication address."
)
smtp_password = st.sidebar.text_input(
    "PASSWORD",
    value="",
    placeholder="Paste SMTP password or app password",
    type="password",
    help="SMTP authentication password / Gmail App Password."
)
smtp_from_email = st.sidebar.text_input(
    "EMAIL",
    value="",
    placeholder="Paste sender email address",
    help="The sender email address appearing on student alerts."
)
smtp_from_name = st.sidebar.text_input(
    "NAME",
    value="",
    placeholder="Paste sender display name",
    help="Display name of the sender (e.g. DYP Attendance Bureau)."
)

# SMTP Server particulars (Read only/Defaults in instruction format)
st.sidebar.markdown("**SMTP Default Parameters**")
col_s1, col_s2 = st.sidebar.columns(2)
with col_s1:
    st.text_input("SMTP HOST", value="smtp.gmail.com", disabled=True)
with col_s2:
    st.text_input("SMTP PORT", value="587", disabled=True)

st.sidebar.divider()

# LLM Section
st.sidebar.markdown("### 🦙 Groq AI Engine")
groq_api_key = st.sidebar.text_input(
    "Groq API Key",
    value="",
    placeholder="Paste Groq API key",
    type="password",
    help="API key for Groq Cloud completions."
)
groq_model = st.sidebar.selectbox(
    "Groq Model",
    options=["llama-3.3-70b-versatile",],
    index=0
)

st.sidebar.divider()
st.sidebar.markdown("### Google Service Account")
service_account_upload = st.sidebar.file_uploader(
    "Upload service account JSON",
    type=["json"],
    help="Upload your Google service account JSON if Streamlit secrets are not configured."
)
service_account_json_text = st.sidebar.text_area(
    "Or paste service account JSON",
    value="",
    height=140,
    placeholder='{"type":"service_account", "...": "..."}',
    help="Paste the full Google service account JSON here as an alternative to uploading the file."
)

runtime_service_account_source = default_config.get("service_account_source")
if service_account_upload is not None:
    runtime_service_account_source = json.load(service_account_upload)
elif service_account_json_text.strip():
    try:
        runtime_service_account_source = json.loads(service_account_json_text)
    except json.JSONDecodeError:
        runtime_service_account_source = None
        st.sidebar.error("Invalid service account JSON. Please paste a valid JSON object.")

# Active State Stores
if 'scanned_data' not in st.session_state:
    st.session_state['scanned_data'] = None
if 'sheet_results' not in st.session_state:
    st.session_state['sheet_results'] = None
if 'selected_spreadsheet_id' not in st.session_state:
    st.session_state['selected_spreadsheet_id'] = None
if 'selected_spreadsheet_name' not in st.session_state:
    st.session_state['selected_spreadsheet_name'] = ""
if 'email_previews' not in st.session_state:
    st.session_state['email_previews'] = {}

# ----------------- MAIN APP INTERFACE -----------------
# Header Banner
st.markdown("""
<div class="header-container">
    <h1 style="margin:0; font-size: 2.8rem; letter-spacing: -0.5px;">⚡ Attendance Management AI Agent</h1>
    <p style="margin: 0.5rem 0 0 0; font-size: 1.1rem; opacity: 0.85; font-weight: 300;">
        Autonomously scan college spreadsheets from Google Drive, map column layout via AI, and dispatch alert notifications.
    </p>
</div>
""", unsafe_allow_html=True)

# Google Drive URL Paste box
st.markdown("### 🔗 Google Drive Folder or Spreadsheet URL")
drive_url = st.text_input(
    "Paste Google Drive Folder or direct Spreadsheet URL below:",
    value=get_secret_with_aliases("GOOGLE_DRIVE_FOLDER_URL", default=""),
    placeholder="https://drive.google.com/drive/folders/... or https://docs.google.com/spreadsheets/d/...",
    label_visibility="collapsed"
)

# Extract and validate Google Drive ID
g_id, g_type = extract_gdrive_id(drive_url)

if g_id:
    # Service account check
    service_account_source = runtime_service_account_source
    if not service_account_source:
        st.warning("Google service account credentials are missing. Upload or paste the JSON in the sidebar, or add it in Streamlit secrets.")
    elif isinstance(service_account_source, dict):
        st.caption("Google service account loaded securely from Streamlit secrets.")
    elif not os.path.exists(service_account_source):
        st.warning(f"⚠️ Service account file `{service_account_source}` not found. Scanning might fail.")

    if g_type == "folder" and service_account_source:
        # Folder Scanner flow
        st.info("📂 Google Drive Folder URL detected. Scanning list of spreadsheets...")
        try:
            folder_scanner = DriveScanner(service_account_source, g_id)
            sheets_in_folder = folder_scanner.list_spreadsheets_in_folder()
            if sheets_in_folder:
                # Custom selection box for sheet
                sheet_names = [f["name"] for f in sheets_in_folder]
                selected_sheet_name = st.selectbox(
                    "Select Spreadsheet to Analyze:", 
                    options=sheet_names,
                    index=0
                )
                
                # Retrieve specific ID
                chosen_sheet = [f for f in sheets_in_folder if f["name"] == selected_sheet_name][0]
                st.session_state['selected_spreadsheet_id'] = chosen_sheet["id"]
                st.session_state['selected_spreadsheet_name'] = chosen_sheet["name"]
            else:
                st.error("❌ No Google Spreadsheet files found in the specified folder.")
                st.session_state['selected_spreadsheet_id'] = None
        except Exception as e:
            st.error(f"Failed to scan folder contents: {e}")
            st.session_state['selected_spreadsheet_id'] = None
    elif service_account_source:
        # Direct sheet flow
        st.session_state['selected_spreadsheet_id'] = g_id
        st.session_state['selected_spreadsheet_name'] = "Direct Spreadsheet"

    # Action buttons
    if st.session_state['selected_spreadsheet_id']:
        st.markdown("<br>", unsafe_allow_html=True)
        col_scan, col_clear = st.columns([1.5, 8.5])
        with col_scan:
            scan_clicked = st.button("🚀 Analyze Spreadsheet", use_container_width=True)
        with col_clear:
            if st.button("🧹 Clear Results", use_container_width=False) and st.session_state['scanned_data'] is not None:
                st.session_state['scanned_data'] = None
                st.session_state['sheet_results'] = None
                st.session_state['email_previews'] = {}
                st.rerun()

        if scan_clicked:
            if not groq_api_key:
                st.error("🔑 Please input a valid Groq API Key in the sidebar configuration.")
            else:
                status_block = st.empty()
                with st.spinner("Analyzing spreadsheet structure & extracting schedules with AI..."):
                    try:
                        spreadsheet_id = st.session_state['selected_spreadsheet_id']
                        
                        # 1. Read sheet tabs
                        status_block.info("🔍 Loading Sheet reader & querying tabs...")
                        reader = SheetReader(service_account_source)
                        tabs = reader.get_sheet_names(spreadsheet_id)
                        
                        # 2. Setup AI layout analyser
                        status_block.info("🦙 Initializing AI Agent structural analyzer...")
                        ai_analyzer = AISheetAnalyzer(groq_api_key, groq_model)
                        
                        cumulative_records = []
                        sheet_analytics = {}

                        # Analyze tabs
                        for tab in tabs:
                            status_block.info(f"📊 Reading sample rows from sheet page: **{tab}**")
                            # Read first 30 rows to get layout mapping
                            raw_rows = reader.read_sheet(spreadsheet_id, range_name=f"'{tab}'!A1:Z50")
                            if len(raw_rows) < 2:
                                status_block.warning(f"⚠️ Page `{tab}` contains insufficient or empty records. Skipping.")
                                continue
                                
                            # Perform AI mapping
                            status_block.info(f"🧠 Querying Groq to map variables of page: **{tab}**")
                            ai_mapping = ai_analyzer.analyze_sheet_structure(raw_rows)
                            
                            if not ai_mapping or 'roll_no_col_index' not in ai_mapping:
                                status_block.warning(f"⚠️ AI mapping failed for page `{tab}`. Checking default columns parsing fallback.")
                                ai_mapping = None
                            
                            # Read complete dataset range for processing
                            full_rows = reader.read_sheet(spreadsheet_id, range_name=f"'{tab}'")
                            processor = AttendanceProcessor(full_rows, ai_mapping)
                            
                            student_details = processor.get_all_students_details()
                            
                            # Record analytics
                            sheet_analytics[tab] = {
                                "total": len(student_details),
                                "present": len([s for s in student_details if s['status'] == 'Present']),
                                "absent": len([s for s in student_details if s['status'] == 'Absent']),
                                "mapping": ai_mapping
                            }
                            
                            # Standardize mapping to main table
                            for student in student_details:
                                student['sheet_tab'] = tab
                                cumulative_records.append(student)
                                
                        status_block.empty()
                        
                        if cumulative_records:
                            st.session_state['scanned_data'] = cumulative_records
                            st.session_state['sheet_results'] = sheet_analytics
                            st.success(f"✓ Analysis complete! Processed **{len(cumulative_records)}** students across **{len(sheet_analytics)}** spreadsheet tab(s).")
                        else:
                            st.error("❌ Failed to parse any student records. Ensure the sheet is readable and shared with Google service account.")
                            st.session_state['scanned_data'] = None
                    except Exception as ex:
                        status_block.empty()
                        st.error(f"An error occurred during agent scan: {ex}")
                        st.session_state['scanned_data'] = None
else:
    st.warning("🔗 Please paste a valid Google Drive URL or direct Spreadsheet URL to begin scanning.")

# ----------------- DISPLAY METRICS & DATA -----------------
if st.session_state['scanned_data'] is not None:
    records = st.session_state['scanned_data']
    df = pd.DataFrame(records)
    
    total_students = len(df)
    absent_df = df[df['status'] == 'Absent']
    present_df = df[df['status'] == 'Present']
    total_absent = len(absent_df)
    total_present = len(present_df)
    
    # Visual Metrics Columns
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 📊 Consolidated Summary Metrics")
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.markdown(f"""
        <div class="metric-card animated-card">
            <div style="font-size: 1.1rem; color: #777; font-weight:600;">Total Students Scanned</div>
            <div class="metric-val">{total_students}</div>
            <div style="font-size: 0.85rem; color: #555;">Across all spreadsheet tabs</div>
        </div>
        """, unsafe_allow_html=True)
    with col_m2:
        st.markdown(f"""
        <div class="metric-card animated-card">
            <div style="font-size: 1.1rem; color: #2ecc71; font-weight:600;">Present Students</div>
            <div class="metric-val" style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">{total_present}</div>
            <div style="font-size: 0.85rem; color: #555;">Attended all lectures</div>
        </div>
        """, unsafe_allow_html=True)
    with col_m3:
        st.markdown(f"""
        <div class="metric-card animated-card">
            <div style="font-size: 1.1rem; color: #e74c3c; font-weight:600;">Absent Students</div>
            <div class="metric-val" style="background: linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">{total_absent}</div>
            <div style="font-size: 0.85rem; color: #555;">Marked absent in &ge;1 lectures</div>
        </div>
        """, unsafe_allow_html=True)
    with col_m4:
        rate = round((total_present / total_students) * 100) if total_students > 0 else 0
        st.markdown(f"""
        <div class="metric-card animated-card">
            <div style="font-size: 1.1rem; color: #f39c12; font-weight:600;">Overall Attendance Rate</div>
            <div class="metric-val" style="background: linear-gradient(135deg, #f857a6 0%, #ff5858 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">{rate}%</div>
            <div style="font-size: 0.85rem; color: #555;">Calculated average percentage</div>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Tabs
    tab_dashboard, tab_absent_actions = st.tabs([
        "👥 Student Attendance Database", 
        "🚨 Absent alerts & AI Email Panel"
    ])
    
    with tab_dashboard:
        st.markdown("### 🎓 Complete Students Attendance Log")
        
        # Filter buttons
        filter_status = st.segmented_control(
            "Filter Attendance Status:",
            options=["All", "Present", "Absent"],
            default="All"
        )
        
        display_df = df.copy()
        if filter_status == "Present":
            display_df = present_df
        elif filter_status == "Absent":
            display_df = absent_df
            
        # Format table for neat HTML presentation
        display_records = []
        for idx, row in display_df.iterrows():
            absent_details_str = ", ".join([f"{l['subject']} ({l['timing']})" for l in row['absent_lectures']])
            if not absent_details_str:
                absent_details_str = "None (Present)"
                
            status_badge = f'<span class="badge badge-present">Present</span>' if row['status'] == 'Present' else f'<span class="badge badge-absent">Absent</span>'
            
            display_records.append({
                "Roll No": row['roll_no'],
                "Name": row['name'],
                "Email": row['email'],
                "Tab (Class)": row['sheet_tab'],
                "Status": status_badge,
                "Missed Sessions (Timings)": absent_details_str
            })
            
        if display_records:
            log_html_df = pd.DataFrame(display_records)
            st.write(log_html_df.to_html(escape=False, index=False), unsafe_allow_html=True)
        else:
            st.info("No records matching the filter criteria found.")
            
    with tab_absent_actions:
        st.markdown("### 📧 Send Absence Alert Notifications")
        if total_absent == 0:
            st.success("🎉 Excellent! No students are marked absent today.")
        else:
            st.warning(f"⚠️ There are **{total_absent}** students marked as absent. You can generate alert templates using AI & send emails.")
            
            # Allow custom Subject line
            current_date_str = time.strftime("%d-%m-%Y")
            custom_subject = st.text_input("Custom Email Subject Line:", value=f"Attendance Alert | {current_date_str}")
            
            st.divider()
            
            # Select target student to preview AI generated mail
            selected_absent_email = st.selectbox(
                "Select absent student to inspect / preview email:",
                options=absent_df['email'].tolist(),
                format_func=lambda email: f"{absent_df[absent_df['email'] == email]['name'].values[0]} ({email})"
            )
            
            if selected_absent_email:
                student_record = absent_df[absent_df['email'] == selected_absent_email].iloc[0].to_dict()
                
                col_act1, col_act2 = st.columns([2, 8])
                with col_act1:
                    generate_preview = st.button("✨ Generate AI Email Preview", use_container_width=True)
                
                # Check cache for preview
                if generate_preview:
                    with st.spinner("Invoking AIEmailGenerator (Groq/Llama)..."):
                        try:
                            # Use default dummy or calculate actual attendance if you search files
                            # For simplicity we report a mock monthly average or 78% standard if we don't have cumulative historical sheets
                            mock_avg_attendance = 78
                            
                            generator = AIEmailGenerator(groq_api_key, groq_model)
                            html_email = generator.generate_email_content(student_record, current_date_str, mock_avg_attendance)
                            st.session_state['email_previews'][selected_absent_email] = html_email
                        except Exception as e:
                            st.error(f"Failed to generate AI Email content: {e}")
                            
                if selected_absent_email in st.session_state['email_previews']:
                    st.write("**Email Preview (HTML Render):**")
                    st.html(st.session_state['email_previews'][selected_absent_email])
                    
                    st.write("**Raw HTML Code:**")
                    st.code(st.session_state['email_previews'][selected_absent_email], language="html")
            
            st.divider()
            st.markdown("### 🚀 Dispatch Bulk Notification Emails")
            st.write("Clicking the dispatch button below will connect via SMTP and send customized attendance alert notifications to all parent/student email addresses listed as absent.")
            
            # SMTP Setup check
            smtp_configured = bool(smtp_username and smtp_password and smtp_from_email)
            if not smtp_configured:
                st.error("❌ SMTP Credentials (Username / Password) must be completed in the sidebar to enable sending alerts.")
                
            dispatch_button = st.button("✉️ Dispatch Email Notifications to All Absent Students", disabled=not smtp_configured)
            
            if dispatch_button:
                terminal_placeholder = st.empty()
                logs_out = []
                
                logs_out.append(f"[{time.strftime('%H:%M:%S')}] Connecting to SMTP server {smtp_from_name} ({smtp_from_email})...")
                terminal_placeholder.markdown(f'<div class="terminal-box">{"<br>".join(logs_out)}</div>', unsafe_allow_html=True)
                
                try:
                    # 1. Initialize Email Sender
                    sender = EmailSender(
                        email_address=smtp_username,
                        email_password=smtp_password,
                        from_email=smtp_from_email,
                        from_name=smtp_from_name
                    )
                    
                    # 2. Iterate absent list and email
                    success_count = 0
                    failure_count = 0
                    
                    # AI Generator for emails
                    generator = AIEmailGenerator(groq_api_key, groq_model)
                    
                    for idx, s_row in absent_df.iterrows():
                        to_email = s_row['email']
                        name = s_row['name']
                        
                        logs_out.append(f"[{time.strftime('%H:%M:%S')}] Analyzing & generating HTML for {name} ({to_email})...")
                        terminal_placeholder.markdown(f'<div class="terminal-box">{"<br>".join(logs_out)}</div>', unsafe_allow_html=True)
                        
                        try:
                            # Check cache or generate email contents
                            if to_email in st.session_state['email_previews']:
                                content_html = st.session_state['email_previews'][to_email]
                            else:
                                content_html = generator.generate_email_content(s_row.to_dict(), current_date_str, 78)
                                st.session_state['email_previews'][to_email] = content_html
                                
                            logs_out.append(f"[{time.strftime('%H:%M:%S')}] Dispatching SMTP message to {to_email}...")
                            terminal_placeholder.markdown(f'<div class="terminal-box">{"<br>".join(logs_out)}</div>', unsafe_allow_html=True)
                            
                            sender.send_email(to_email, custom_subject, content_html)
                            success_count += 1
                            logs_out.append(f"[{time.strftime('%H:%M:%S')}] ✅ Email successfully delivered to {name}!")
                        except Exception as inner_ex:
                            failure_count += 1
                            logs_out.append(f"[{time.strftime('%H:%M:%S')}] ❌ Failed to notify {name}: {inner_ex}")
                            
                        terminal_placeholder.markdown(f'<div class="terminal-box">{"<br>".join(logs_out)}</div>', unsafe_allow_html=True)
                        
                    st.success(f"Dispatched completed! Successfully Sent: {success_count} emails, Failed: {failure_count} emails.")
                except Exception as top_ex:
                    st.error(f"SMTP dispatch process interrupted: {top_ex}")
