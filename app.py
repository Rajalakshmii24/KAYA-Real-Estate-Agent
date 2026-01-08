import streamlit as st
import ollama
import sqlite3
import json
import pandas as pd
from datetime import datetime
from io import BytesIO

# --- 1. BRANDING & MOBILE-READY STYLE ---
st.set_page_config(page_title="KAYA Real Estate", page_icon="🔑", layout="wide")

st.markdown("""
    <style>
    /* 1. Hide Streamlit Branding (GitHub, Cloud, Footer) */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .stApp { background-color: #0c0d11; color: #e0e0e0; }
    
    /* 2. Titles and Input Labels in Gold */
    h1, h2, h3 { color: #d4af37 !important; text-align: center; font-family: 'Playfair Display', serif; }
    
    /* Styling labels for Full Name, Email, Mobile */
    label[data-testid="stWidgetLabel"] {
        color: #d4af37 !important;
        font-weight: bold !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    /* 3. AI Bot Message Text Color */
    /* This targets the text inside the assistant chat message */
    div[data-testid="stChatMessage"]:nth-child(even) p {
        color: #d4af37 !important;
    }
    
    .stButton > button { width: 100%; border-radius: 10px; border: 1px solid #d4af37; background-color: #16181d; color: #d4af37; font-weight: bold; margin-bottom: 5px; }
    
    /* Message Box Styling */
    .stChatMessage { border-radius: 15px; border: 1px solid #2d2f39; margin-bottom: 10px; font-size: 14px; }
    div[data-testid="stChatMessage"]:nth-child(even) { 
        background-color: #1c1e26 !important; 
        border-left: 5px solid #d4af37; 
    }
    
    [data-testid="stSidebar"] { background-color: #111217; border-right: 1px solid #2d2f39; }
    .sidebar-title { color: #d4af37; font-size: 0.8rem; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATABASE INITIALIZATION ---
def init_db():
    conn = sqlite3.connect('kaya_leads.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS chat_history 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                     name TEXT, email TEXT, mobile TEXT, messages TEXT, 
                     lead_data TEXT, status TEXT, timestamp TEXT)''')
    conn.commit()
    return conn

db = init_db()

def save_registry_to_db(name, email, mobile):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO chat_history (name, email, mobile, messages, lead_data, status, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, email, mobile, json.dumps([]), json.dumps({}), "Pending", timestamp)
    )
    db.commit()
    return cursor.lastrowid

# --- 3. SESSION INITIALIZATION ---
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "messages" not in st.session_state:
    st.session_state.messages, st.session_state.current_step = [], "greeting"
    st.session_state.lead_data = {"unit": None, "purpose": None, "budget": None, "area": None}
    st.session_state.session_id = None 

# --- 4. FRONT PAGE ---
if not st.session_state.logged_in:
    st.markdown("<br><h1>K.A.Y.A REAL ESTATE</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        reg_name = st.text_input("Full Name")
        reg_email = st.text_input("Email ID")
        reg_mobile = st.text_input("Mobile Number")
        if st.button("ENTER TO CHAT"):
            if reg_name and reg_email and reg_mobile:
                st.session_state.user_data = {"name": reg_name, "email": reg_email, "mobile": reg_mobile}
                st.session_state.session_id = save_registry_to_db(reg_name, reg_email, reg_mobile)
                st.session_state.logged_in = True
                st.rerun()
    st.stop()

# --- 5. CHAT LOGIC ---
def get_flow():
    ld = st.session_state.lead_data
    is_rent = ld.get("purpose") == "Rent"
    budget_msg = "What is your yearly rental budget?" if is_rent else "What is your ideal budget range?"
    return {
        "greeting": {"msg": f"Welcome, {st.session_state.user_data['name']} to KAYA Real Estate. I am your digital concierge. Are you looking to find a new property today?", "suggestions": ["Yes, I'm looking!", "Just browsing"]},
        "unit": {"msg": "Excellent. What kind of unit are you looking for?", "suggestions": ["Studio / 1BR", "2BR or 3BR", "Villa / Penthouse"]},
        "purpose": {"msg": "Are you looking to Rent or Buy?", "suggestions": ["Rent", "Buy"]},
        "budget": {"msg": budget_msg, "suggestions": ["50k-100k", "1.5M-3M", "Luxury"]},
        "area": {"msg": "Which area in Dubai do you prefer?", "suggestions": ["Downtown", "Marina", "Dunes Village"]},
        "qanda": {"msg": "I've noted your preferences. Any specific questions?", "suggestions": ["No, I'm ready", "Talk to an agent"]},
        "closing": {"msg": "I've noted your preferences. Thank you. Your request is now priority. A KAYA team member will connect with you shortly via WhatsApp. Have a prestigious day!", "suggestions": []}
    }

def handle_input(user_text):
    st.session_state.messages.append({"role": "user", "content": user_text})
    # Step logic
    ld = st.session_state.lead_data
    if st.session_state.current_step == "unit": ld["unit"] = user_text
    elif st.session_state.current_step == "purpose": ld["purpose"] = user_text
    elif st.session_state.current_step == "budget": ld["budget"] = user_text
    elif st.session_state.current_step == "area": ld["area"] = user_text
    
    if not ld["unit"]: st.session_state.current_step = "unit"
    elif not ld["purpose"]: st.session_state.current_step = "purpose"
    elif not ld["budget"]: st.session_state.current_step = "budget"
    elif not ld["area"]: st.session_state.current_step = "area"
    else: st.session_state.current_step = "qanda"
    
    if user_text in ["No, I'm ready", "Talk to an agent"]: st.session_state.current_step = "closing"
    
    st.session_state.messages.append({"role": "assistant", "content": get_flow()[st.session_state.current_step]["msg"]})
    db.execute("UPDATE chat_history SET messages = ?, lead_data = ? WHERE id = ?", 
               (json.dumps(st.session_state.messages), json.dumps(st.session_state.lead_data), st.session_state.session_id))
    db.commit()

# --- 6. SIDEBAR ---
with st.sidebar:
    st.markdown("<div class='sidebar-title'>CRM Panel</div>", unsafe_allow_html=True)
    if st.session_state.session_id:
        res = db.execute("SELECT status FROM chat_history WHERE id = ?", (st.session_state.session_id,)).fetchone()
        cur_stat = res[0] if res else "Pending"
        opts = ["Pending", "Agent Talking", "Success", "Unsuccessful"]
        new_stat = st.selectbox("Status", opts, index=opts.index(cur_stat))
        if new_stat != cur_stat:
            db.execute("UPDATE chat_history SET status = ? WHERE id = ?", (new_stat, st.session_state.session_id))
            db.commit()
            st.rerun()

    if st.button("📊 Export Excel"):
        df = pd.read_sql_query("SELECT name, email as 'Email ID', mobile as 'Mobile Number', lead_data, status as 'Status' FROM chat_history", db)
        def create_desc(j):
            d = json.loads(j)
            return f"{d.get('unit','Inquiry')} in {d.get('area','Dubai')}"
        df['Description'] = df['lead_data'].apply(create_desc)
        final_df = df[['name', 'Email ID', 'Mobile Number', 'Description', 'Status']]
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            final_df.to_excel(writer, index=False)
        st.download_button("📥 Download", output.getvalue(), "KAYA_Leads.xlsx")

    st.write("---")
    if st.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.rerun()

# --- 7. MAIN UI ---
st.markdown("<h1>KAYA PRIVATE CONCIERGE</h1>", unsafe_allow_html=True)
for m in st.session_state.messages or [{"role": "assistant", "content": get_flow()["greeting"]["msg"]}]:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if st.session_state.current_step != "closing":
    sugs = get_flow()[st.session_state.current_step]["suggestions"]
    cols = st.columns(len(sugs))
    for i, choice in enumerate(sugs):
        if cols[i].button(choice): handle_input(choice); st.rerun()

if prompt := st.chat_input("Message KAYA..."): handle_input(prompt); st.rerun()