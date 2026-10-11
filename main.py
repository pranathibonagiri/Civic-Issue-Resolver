import streamlit as st
import sqlite3
import os
from datetime import datetime
from google import genai
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv()

# Initialize Gemini Client (Backend Layer)
# Make sure GEMINI_API_KEY is set in your .env file
client = genai.Client()

# ==========================================
# 1. DATABASE LAYER (SQLite)
# ==========================================
DB_FILE = "civic_complaints.db"

def init_db():
    """Initializes the database file and creates the table if it doesn't exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            locality TEXT,
            raw_description TEXT,
            category TEXT,
            urgency TEXT,
            formal_draft TEXT,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_complaint(locality, raw_desc, category, urgency, formal_draft):
    """Inserts a new processed complaint row into the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO complaints (timestamp, locality, raw_description, category, urgency, formal_draft, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (timestamp, locality, raw_desc, category, urgency, formal_draft, "Pending Review"))
    conn.commit()
    conn.close()

def fetch_all_complaints():
    """Retrieves all complaints from the database to display on the dashboard."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, timestamp, locality, category, urgency, status, raw_description, formal_draft FROM complaints ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

# Initialize database on startup
init_db()


# ==========================================
# 2. BACKEND LAYER (Gen AI Processing)
# ==========================================
def process_civic_issue(raw_text):
    """Calls Gemini to classify metadata and generate a structured letter."""
    system_instruction = (
        "You are an expert civic governance advisor. Analyze the user's messy complaint.\n"
        "First, output EXACTLY the category matching one of these: [Roads & Traffic, Sanitation & Waste, Public Safety, Water & Utilities].\n"
        "Second, output EXACTLY the urgency level matching one of these: [Low, Medium, High].\n"
        "Third, write a formal, professional grievance letter template addressed to the municipal board.\n"
        "Format your output exactly like this:\n"
        "CATEGORY: <category>\n"
        "URGENCY: <urgency>\n"
        "LETTER:\n"
        "<letter content>"
    )
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',  # Ultra-fast model
        contents=f"Complaint: {raw_text}",
        config={"system_instruction": system_instruction}
    )
    
    # Parse out variables from the structured text response
    text = response.text
    try:
        category = text.split("CATEGORY:")[1].split("URGENCY:")[0].strip()
        urgency = text.split("URGENCY:")[1].split("LETTER:")[0].strip()
        letter = text.split("LETTER:")[1].strip()
    except Exception:
        # Fallback values if LLM shifts formatting slightly
        category, urgency, letter = "General", "Medium", text
        
    return category, urgency, letter


# ==========================================
# 3. FRONTEND LAYER (Streamlit Interface)
# ==========================================
st.set_page_config(page_title="WardWatch Civic Portal", page_icon="🏛️", layout="wide")

st.title("🏛️ WardWatch Portal")
st.subheader("Empowering Communities Through AI-Driven Civic Action")

# Tabbed Layout for User Forms vs Community Dashboard View
tab1, tab2 = st.tabs(["📥 File a Grievance", "📊 Community Dashboard"])

with tab1:
    st.markdown("### Report a Local Infrastructure Issue")
    st.caption("Type your complaint in plain, casual language. Our AI will automatically categorize it, determine urgency, and draft an official administrative letter.")
    
    with st.form("civic_form"):
        locality = st.selectbox("Select Your Locality / District", ["North Ward", "South District", "Central Metro", "East Suburbs", "West Tech Zone"])
        raw_description = st.text_area("Describe the issue in detail:", height=150, placeholder="e.g., The main drainage line near the public park is leaking foul water onto the walking track. It has been happening for 3 days and smells terrible.")
        
        submit_btn = st.form_submit_button("⚡ Process & File Grievance")
        
    if submit_btn:
        if not raw_description.strip():
            st.error("Please enter a description before submitting.")
        else:
            with st.spinner("AI is analyzing compliance parameters and saving to database..."):
                # 1. Trigger Backend AI
                category, urgency, formal_draft = process_civic_issue(raw_description)
                
                # 2. Commit to Database Layer
                save_complaint(locality, raw_description, category, urgency, formal_draft)
                
                st.success("🎉 Grievance processed and stored securely in the SQLite database!")
                
                # Dynamic Visual Feedback
                c1, c2 = st.columns(2)
                with c1:
                    st.metric("Assigned Department", category)
                with c2:
                    st.metric("Urgency Level", urgency)
                
                st.markdown("### 📝 Official Draft Generated:")
                st.info(formal_draft)

with tab2:
    st.markdown("### Public Accountability Tracker")
    st.caption("Live complaints pulled directly from the local SQLite database.")
    
    # Read Data from Database Layer
    tickets = fetch_all_complaints()
    
    if not tickets:
        st.info("No grievances have been filed in the database yet.")
    else:
        # Render high-level community stats dynamically
        total_tickets = len(tickets)
        high_priority = sum(1 for t in tickets if t[4] == "High")
        
        m1, m2 = st.columns(2)
        m1.metric("Total Filed Issues", total_tickets)
        m2.metric("Critical Alerts 🔥", high_priority)
        
        st.markdown("---")
        
        # Display each database row cleanly
        for ticket in tickets:
            t_id, t_time, t_loc, t_cat, t_urg, t_status, t_raw, t_draft = ticket
            
            with st.container():
                st.markdown(f"#### 🎫 Ticket #{t_id} | {t_cat} ({t_loc})")
                st.text(f"Logged on: {t_time} | Status: 🟡 {t_status} | Priority: {t_urg}")
                st.markdown(f"**Citizen Report:** *\"{t_raw}\"*")
                with st.expander("📄 View AI-Generated Official Administrative Draft"):
                    st.code(t_draft, language="markdown")
                st.markdown("---")