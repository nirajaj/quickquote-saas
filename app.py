import streamlit as st
from supabase import create_client, Client
from groq import Groq
from fpdf import FPDF
import json
import datetime
import random
from streamlit_mic_recorder import mic_recorder
import time
import io

# --- 1. GOOGLE VERIFICATION & SEO CONFIG ---
# This tag allows Google to verify you own the site
st.markdown("""
    <head>
        <meta name="google-site-verification" content="VJDIHjPf8oJ2yz_AvVJKkU0enZrVbkX6E8jquK6OxhM" />
    </head>
""", unsafe_allow_html=True)

st.set_page_config(
    page_title="QuickQuote | Free AI Voice Invoice Generator for Contractors",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Hidden SEO Content for Google Robots
st.markdown("""
    <div style="display:none;">
        <h1>Free Invoice Generator</h1>
        <p>Best AI voice-to-PDF invoice tool for plumbers, electricians, and freelancers. 
        Create professional invoices in seconds using your voice with QuickQuote.</p>
    </div>
""", unsafe_allow_html=True)

# Professional CSS Styling
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stButton>button {width: 100%; border-radius: 8px; height: 3.5em; background-color: #2563EB; color: white; font-weight: bold; border: none; transition: 0.3s;}
    .stButton>button:hover {background-color: #1D4ED8; transform: scale(1.02);}
    .google-auth-btn {
        display: flex; align-items: center; justify-content: center;
        background-color: #ffffff; color: #757575; border: 1px solid #ddd;
        border-radius: 4px; padding: 12px 24px; text-decoration: none;
        font-family: 'Roboto', sans-serif; font-weight: 500; font-size: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.12); margin-top: 20px;
    }
    .google-auth-btn:hover { background-color: #f8f8f8; box-shadow: 0 3px 6px rgba(0,0,0,0.16); }
    .support-text { text-align: center; font-size: 0.85em; color: #666; margin-top: 30px; border-top: 1px solid #eee; padding-top: 15px; }
</style>
""", unsafe_allow_html=True)

# --- 2. INITIALIZE CLIENTS (CACHED) ---
@st.cache_resource
def get_supabase():
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

supabase = get_supabase()
groq_key = st.secrets["groq"]["key"]

# --- 3. AUTHENTICATION HANDLER ---
if 'user' not in st.session_state: st.session_state.user = None

# Handle URL Redirect from Google
if "code" in st.query_params:
    try:
        res = supabase.auth.exchange_code_for_session({"auth_code": st.query_params["code"]})
        st.session_state.user = res.user.email
        st.query_params.clear()
        st.rerun()
    except: st.query_params.clear()

# --- 4. DATABASE FUNCTIONS ---
def get_user_data(email):
    res = supabase.table("user_credits").select("*").eq("email", email).execute()
    if res.data: return res.data[0]
    new_user = {"email": email, "credits": 2, "plan": "free"}
    supabase.table("user_credits").insert(new_user).execute()
    return new_user

def update_credits(email, new_amount, new_plan=None):
    data = {"credits": new_amount}
    if new_plan: data["plan"] = new_plan
    supabase.table("user_credits").update(data).eq("email", email).execute()

# --- 5. PDF ENGINE ---
class ProPDF(FPDF):
    def footer(self):
        self.set_y(-15); self.set_font('Arial', 'I', 8); self.set_text_color(128)
        self.cell(0, 10, f'Page {self.page_no()} | QuickQuote AI Invoicing', 0, 0, 'C')

def create_pro_pdf(company_name, client_data):
    pdf = ProPDF(); pdf.add_page()
    # Banner
    pdf.set_fill_color(30, 58, 138); pdf.rect(0, 0, 210, 40, 'F')
    # Header
    pdf.set_font("Arial", 'B', 24); pdf.set_text_color(255); pdf.set_xy(10, 10); pdf.cell(100, 15, company_name, 0, 0, 'L')
    pdf.set_font("Arial", 'B', 16); pdf.set_xy(150, 10); pdf.cell(50, 10, "INVOICE", 0, 1, 'R')
    pdf.set_font("Arial", '', 10); pdf.set_xy(150, 20); pdf.cell(50, 5, f"#{random.randint(1000, 9999)}", 0, 1, 'R')
    pdf.set_xy(150, 25); pdf.cell(50, 5, str(datetime.date.today()), 0, 1, 'R')
    # Bill To
    pdf.set_y(50); pdf.set_text_color(30, 58, 138); pdf.set_font("Arial", 'B', 12); pdf.cell(0, 8, "BILL TO:", 0, 1)
    pdf.set_text_color(0); pdf.set_font("Arial", '', 11); pdf.cell(0, 6, client_data.get('client_name', 'Valued Customer'), 0, 1); pdf.ln(10)
    # Table Header
    pdf.set_font("Arial", 'B', 10); pdf.set_fill_color(243, 244, 246); pdf.set_draw_color(209, 213, 219)
    pdf.cell(110, 10, "  Description", 1, 0, 'L', 1); pdf.cell(20, 10, "Qty", 1, 0, 'C', 1); pdf.cell(30, 10, "Price", 1, 0, 'R', 1); pdf.cell(30, 10, "Total", 1, 1, 'R', 1)
    # Table Content
    pdf.set_font("Arial", '', 10); total_sum = 0
    for item in client_data.get('items', []):
        try:
            q, p = float(item.get('quantity', 1)), float(item.get('price', 0))
            t = q * p; total_sum += t
            pdf.cell(110, 10, f"  {item.get('description')}", 1)
            pdf.cell(20, 10, str(int(q)), 1, 0, 'C')
            pdf.cell(30, 10, f"${p:,.2f}", 1, 0, 'R')
            pdf.cell(30, 10, f"${t:,.2f}", 1, 1, 'R')
        except: continue
    # Totals
    pdf.ln(5); pdf.set_font("Arial", 'B', 14); pdf.set_text_color(30, 58, 138); pdf.cell(160, 12, "TOTAL DUE:  ", 0, 0, 'R'); pdf.cell(30, 12, f"${total_sum:,.2f}", 0, 1, 'R')
    # Footer Notes
    pdf.ln(15); pdf.set_draw_color(30, 58, 138); pdf.line(10, pdf.get_y(), 200, pdf.get_y()); pdf.ln(5)
    pdf.set_text_color(0); pdf.set_font("Arial", 'B', 10); pdf.cell(0, 8, "PAYMENT INSTRUCTIONS:", 0, 1)
    pdf.set_font("Arial", '', 9); pdf.set_text_color(80); pdf.cell(0, 5, f"Account Name: {company_name}", 0, 1); pdf.cell(0, 5, "Payment Terms: Due upon receipt.", 0, 1)
    pdf.ln(5); pdf.set_font("Arial", 'B', 10); pdf.set_text_color(0); pdf.cell(0, 8, "ADDITIONAL NOTES:", 0, 1)
    pdf.set_font("Arial", 'I', 9); pdf.set_text_color(80); pdf.multi_cell(0, 5, client_data.get('note', "Thank you for your business!"))
    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- 6. THE LOGIN SCREEN ---
if not st.session_state.user:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>⚡ QuickQuote</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #666;'>Professional AI Voice Invoicing</p>", unsafe_allow_html=True)
        try:
            LIVE_URL = "https://inovicecreatefree.streamlit.app"
            auth_url = supabase.auth.sign_in_with_oauth({"provider": "google", "options": {"redirect_to": LIVE_URL, "flow_type": "pkce"}}).url
            st.markdown(f'''<a href="{auth_url}" target="_blank" class="google-auth-btn">
                <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" style="width:20px; margin-right:12px;">
                Sign in with Google</a>
                <p style="text-align:center; font-size:10px; color:#999; margin-top:5px;">(Opens in new tab)</p>''', unsafe_allow_html=True)
            st.markdown("<div class='support-text'>Support: nirajaj133@gmail.com</div>", unsafe_allow_html=True)
        except Exception as e: st.error(f"Error: {e}")
    st.stop()

# --- 7. MAIN DASHBOARD ---
# Payment Success Logic (Adds 400 Credits)
if st.query_params.get("payment") == "success":
    u = get_user_data(st.session_state.user)
    update_credits(st.session_state.user, u['credits'] + 400, "Pro Plan")
    st.balloons(); st.success("🎉 400 Credits Added Successfully!"); st.query_params.clear(); time.sleep(2); st.rerun()

user_info = get_user_data(st.session_state.user)
credits = user_info['credits']

with st.sidebar:
    st.write(f"👤 **{st.session_state.user}**")
    st.metric("Credits Left", credits)
    if credits < 10:
        st.link_button("👉 Get 400 Credits ($10)", "https://buy.stripe.com/test_fZueVcfDuglSg8a35DgMw00")
    st.divider()
    if st.button("Sign Out"):
        supabase.auth.sign_out(); st.session_state.user = None; st.rerun()

st.title("Create Invoice")
if credits <= 0:
    st.error("⛔ 0 Credits left."); st.link_button("Upgrade Now", "https://buy.stripe.com/test_fZueVcfDuglSg8a35DgMw00"); st.stop()

company_name = st.text_input("Your Business Name", "My Company Inc.")
if 'notes' not in st.session_state: st.session_state.notes = ""

# Professional Example (John Doe)
if st.button("📝 Click to Load Example (John Doe)"):
    st.session_state.notes = """Client: John Doe. 
Project: Office Repairs at 123 Main St. 
Details:
5 new LED light fixtures at $50 per item.
10 hours of electrical labor at $80 per hour.
$30 for food per person for 2 people.
$15 for transportation for 1 person."""
    st.rerun()

with st.container(border=True):
    col1, col2 = st.columns([1, 5])
    with col1: audio = mic_recorder(start_prompt="🎤 Speak", stop_prompt="🛑 Stop", key='recorder')
    if audio:
        if "last_id" not in st.session_state or st.session_state.last_id != audio['id']:
            with st.spinner("⚡ AI Processing..."):
                try:
                    client = Groq(api_key=groq_key)
                    text = client.audio.transcriptions.create(file=("audio.wav", audio['bytes']), model="whisper-large-v3-turbo", response_format="text")
                    st.session_state.notes = text; st.session_state.last_id = audio['id']; st.rerun()
                except Exception as e: st.error(f"Mic Error: {e}")
    
    final_text = st.text_area("Job Details (Edit if needed):", value=st.session_state.notes, height=180)
    st.session_state.notes = final_text

if st.button("🚀 Generate Professional PDF (-1 Credit)"):
    if not final_text: st.warning("Please enter details first.")
    else:
        with st.spinner("AI Accountant working..."):
            update_credits(st.session_state.user, credits - 1)
            client = Groq(api_key=groq_key)
            prompt = f"""Act as a professional accountant. Extract UNIT PRICES and QUANTITIES from: "{final_text}". 
            CRITICAL RULES:
            1. Extract UNIT PRICE (cost for 1).
            2. Extract correct Quantity.
            3. Do NOT do math.
            4. Generate a professional 'note' for the customer.
            Return ONLY JSON: {{ "client_name": "Name", "items": [{{"description": "Item", "quantity": 1, "price": 0.00}}], "note": "Professional message" }}"""
            
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user", "content": prompt}])
            try:
                raw = res.choices[0].message.content
                data = json.loads(raw[raw.find("{"):raw.rfind("}")+1])
                pdf = create_pro_pdf(company_name, data)
                st.balloons(); st.success("Invoice Ready!")
                st.download_button("📥 Download PDF Now", pdf, f"Invoice_{random.randint(100,999)}.pdf", "application/pdf")
            except: st.error("AI Error. Please try again.")
