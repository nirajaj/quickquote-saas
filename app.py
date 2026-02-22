import streamlit as st
from supabase import create_client, Client
from groq import Groq
from fpdf import FPDF
import json
import datetime
import random
from streamlit_mic_recorder import mic_recorder
import time

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="QuickQuote SaaS", page_icon="⚡", layout="centered")

st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stButton>button {width: 100%; border-radius: 8px; height: 3em; background-color: #2563EB; color: white; font-weight: bold;}
    .google-btn {
        display: flex; align-items: center; justify-content: center;
        background-color: white; color: #333; border: 1px solid #ccc;
        padding: 10px; border-radius: 5px; text-decoration: none;
        font-weight: bold; font-family: Arial, sans-serif; margin-top: 20px;
    }
    .google-btn:hover {background-color: #f1f1f1;}
    .support-text {
        text-align: center; font-size: 0.8em; color: #666; margin-top: 20px; padding-top: 20px; border-top: 1px solid #eee;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. INITIALIZE SUPABASE (CACHED) ---
@st.cache_resource
def get_supabase_client():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        return None

supabase = get_supabase_client()

if not supabase:
    st.error("❌ Database Connection Failed. Please checks secrets.toml.")
    st.stop()

# Load Groq Key
try:
    groq_key = st.secrets["groq"]["key"]
except:
    st.error("❌ Groq Key missing in secrets.toml")
    st.stop()

# --- 3. ROBUST AUTHENTICATION LOGIC ---

if 'user' not in st.session_state:
    st.session_state.user = None

def check_login():
    """Handles the login flow and session management"""
    
    # 1. Handle Return from Google (The Redirect)
    query_params = st.query_params
    auth_code = query_params.get("code")
    
    if auth_code:
        try:
            # Exchange the code for a session using the CACHED client
            session = supabase.auth.exchange_code_for_session({"auth_code": auth_code})
            st.session_state.user = session.user.email
            
            # Clear URL to prevent loop
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.query_params.clear()
    
    # 2. Check if we already have a session (Remember Me)
    if not st.session_state.user:
        try:
            session = supabase.auth.get_session()
            if session:
                st.session_state.user = session.user.email
        except:
            pass

# Run the auth check immediately
check_login()

# --- 4. DATABASE & PAYMENT FUNCTIONS ---
def get_user_data(email):
    # Fetch user data safely
    response = supabase.table("user_credits").select("*").eq("email", email).execute()
    if len(response.data) > 0:
        return response.data[0]
    else:
        # Create new user if not exists
        new_user = {"email": email, "credits": 2, "plan": "free"}
        supabase.table("user_credits").insert(new_user).execute()
        return new_user

def update_credits(email, new_amount, new_plan=None):
    data = {"credits": new_amount}
    if new_plan: data["plan"] = new_plan
    supabase.table("user_credits").update(data).eq("email", email).execute()

def handle_payment_success(email):
    # Check if returning from Stripe
    if st.query_params.get("payment") == "success":
        current_data = get_user_data(email)
        new_total = current_data['credits'] + 400
        update_credits(email, new_total, "Pro Monthly")
        
        st.balloons()
        st.success("🎉 Payment Successful! 400 Credits Added.")
        st.query_params.clear()
        time.sleep(3)
        st.rerun()

# --- 5. PDF ENGINE (PROFESSIONAL) ---
class ProPDF(FPDF):
    def header(self): pass
    def footer(self):
        self.set_y(-15); self.set_font('Arial', 'I', 8); self.set_text_color(128); self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def create_pro_pdf(company_name, client_data):
    pdf = ProPDF(); pdf.add_page()
    # Banner
    pdf.set_fill_color(30, 58, 138); pdf.rect(0, 0, 210, 40, 'F')
    # Text
    pdf.set_font("Arial", 'B', 24); pdf.set_text_color(255); pdf.set_xy(10, 10); pdf.cell(100, 15, company_name, 0, 0, 'L')
    pdf.set_font("Arial", 'B', 16); pdf.set_xy(150, 10); pdf.cell(50, 10, "INVOICE", 0, 1, 'R')
    pdf.set_font("Arial", '', 10); pdf.set_xy(150, 20); pdf.cell(50, 5, f"#{random.randint(1000, 9999)}", 0, 1, 'R')
    pdf.set_xy(150, 25); pdf.cell(50, 5, str(datetime.date.today()), 0, 1, 'R')
    # Bill To
    pdf.set_y(50); pdf.set_text_color(30, 58, 138); pdf.set_font("Arial", 'B', 12); pdf.cell(0, 8, "BILL TO:", 0, 1)
    pdf.set_text_color(0); pdf.set_font("Arial", '', 11); pdf.cell(0, 6, client_data.get('client_name', 'Customer'), 0, 1); pdf.ln(10)
    # Table
    pdf.set_font("Arial", 'B', 10); pdf.set_fill_color(243, 244, 246); pdf.set_draw_color(209, 213, 219)
    pdf.cell(110, 10, "  Description", 'B', 0, 'L', 1); pdf.cell(20, 10, "Qty", 'B', 0, 'C', 1); pdf.cell(30, 10, "Price", 'B', 0, 'R', 1); pdf.cell(30, 10, "Total  ", 'B', 1, 'R', 1)
    # Items
    pdf.set_font("Arial", '', 10); total_sum = 0
    for item in client_data.get('items', []):
        try: total = float(item.get('quantity', 1)) * float(item.get('price', 0))
        except: total = 0
        total_sum += total
        pdf.cell(110, 10, f"  {item.get('description')}", 'B', 0, 'L')
        pdf.cell(20, 10, str(item.get('quantity')), 'B', 0, 'C')
        pdf.cell(30, 10, f"${float(item.get('price', 0)):,.2f}", 'B', 0, 'R')
        pdf.cell(30, 10, f"${total:,.2f}  ", 'B', 1, 'R')
    # Footer
    pdf.ln(5); pdf.set_x(170); pdf.set_font("Arial", 'B', 14); pdf.set_text_color(30, 58, 138)
    pdf.cell(30, 12, f"${total_sum:,.2f}  ", 0, 1, 'R')
    pdf.ln(20); pdf.set_text_color(0); pdf.set_font("Arial", 'B', 10); pdf.cell(0, 8, "TERMS & NOTES", 0, 1)
    pdf.set_font("Arial", '', 9); pdf.set_text_color(80); pdf.multi_cell(0, 5, client_data.get('note', 'Thank you!')); pdf.ln(5)
    pdf.cell(0, 5, f"Make checks payable to: {company_name}", 0, 1)
    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- 6. THE LOGIN SCREEN ---
if not st.session_state.user:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>⚡ QuickQuote</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #666;'>Professional AI Invoicing SaaS</p>", unsafe_allow_html=True)
        
        # New Professional Style for the Button
        st.markdown("""
            <style>
                .google-auth-btn {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    background-color: #ffffff;
                    color: #757575;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    padding: 10px 24px;
                    text-decoration: none;
                    font-family: 'Roboto', sans-serif;
                    font-weight: 500;
                    font-size: 16px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);
                    transition: all 0.3s cubic-bezier(.25,.8,.25,1);
                    margin-top: 20px;
                }
                .google-auth-btn:hover {
                    box-shadow: 0 3px 6px rgba(0,0,0,0.16), 0 3px 6px rgba(0,0,0,0.23);
                    background-color: #f8f8f8;
                }
                .google-logo {
                    width: 20px;
                    height: 20px;
                    margin-right: 12px;
                }
            </style>
        """, unsafe_allow_html=True)
        
        try:
            auth_response = supabase.auth.sign_in_with_oauth({
                "provider": "google",
                "options": {
                    "redirect_to": "http://localhost:8501", 
                    "flow_type": "pkce"
                }
            })
            google_url = auth_response.url
            
            # THE UPDATED BUTTON HTML
            st.markdown(f'''
                <a href="{google_url}" target="_self" class="google-auth-btn">
                    <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" class="google-logo">
                    Sign in with Google
                </a>
            ''', unsafe_allow_html=True)
            
            st.markdown("""
                <div class='support-text'>
                    <p><b>Need Assistance?</b></p>
                    <p>Contact support at <a href="mailto:nirajaj133@gmail.com">nirajaj133@gmail.com</a></p>
                </div>
            """, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Configuration Error: {e}")
            
    st.stop()

# --- 7. MAIN DASHBOARD (If logged in) ---

# Check for payment success message
handle_payment_success(st.session_state.user)

# Load User Data from Supabase
user_data = get_user_data(st.session_state.user)
credits = user_data['credits']
plan = user_data['plan']

# SIDEBAR
with st.sidebar:
    st.write(f"👤 **{st.session_state.user}**")
    st.write(f"🏷️ Plan: **{plan.upper()}**")
    st.divider()
    st.metric("Credits Left", credits)
    
    # Show Upgrade Button if low on credits
    if credits < 5:
        st.markdown("### 🚀 Upgrade")
        st.write("Get 400 credits for $10")
        # REPLACE THIS WITH YOUR REAL STRIPE LINK
        st.link_button("👉 Purchase Plan", "https://buy.stripe.com/test_fZueVcfDuglSg8a35DgMw00")
    
    st.divider()
    
    # SIGN OUT
    if st.button("Sign Out"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()
        
    st.markdown("---")
    st.markdown("<div style='font-size:0.8em;color:#666;'>Support:<br><a href='mailto:nirajaj133@gmail.com'>nirajaj133@gmail.com</a></div>", unsafe_allow_html=True)

# MAIN UI AREA
st.title("Create Invoice")

if credits <= 0:
    st.error("⛔ You have 0 credits.")
    st.info("Purchase the Pro plan to continue.")
    st.link_button("Unlock 400 Credits ($10)", "https://buy.stripe.com/test_fZueVcfDuglSg8a35DgMw00")
    st.stop()

company_name = st.text_input("Business Name", "My Company")

if 'invoice_notes' not in st.session_state: st.session_state.invoice_notes = ""

# --- EXAMPLE BUTTON FEATURE ---
if st.button("📝 Click to Load Example (John Doe Project)"):
    st.session_state.invoice_notes = """Client: John Doe.
Project: Master Bathroom Renovation at 45 Elm Street.

1. Installed 5 Recessed LED Lights at $80 each.
2. Labor: 10 hours at $95 per hour.
3. Materials: 3 boxes of Tile at $50 per box.
4. Disposal Fee: $100 flat rate."""
    st.rerun()

# INPUT (Hybrid: Voice or Text)
st.markdown("### 1. Job Details")
with st.container(border=True):
    col1, col2 = st.columns([1, 5])
    with col1:
        audio = mic_recorder(start_prompt="🎤 Speak", stop_prompt="🛑 Stop", key='recorder')
    with col2:
        st.write("Record voice or type manually.")

    if audio:
        try:
            client = Groq(api_key=groq_key)
            with open("temp.wav", "wb") as f: f.write(audio['bytes'])
            with open("temp.wav", "rb") as file:
                text = client.audio.transcriptions.create(file=(file.name, file.read()), model="whisper-large-v3-turbo", response_format="text")
            st.session_state.invoice_notes = text
            st.rerun()
        except: st.error("Audio Error")

    final_text = st.text_area("Description:", value=st.session_state.invoice_notes, height=150)
    st.session_state.invoice_notes = final_text

# GENERATE BUTTON
st.markdown("### 2. Generate")
if st.button(f"📄 Create Invoice (-1 Credit)"):
    if not final_text:
        st.warning("Please enter details first.")
    else:
        with st.spinner("Analyzing..."):
            
            client = Groq(api_key=groq_key)
            prompt = f"""
            Act as an accountant. Extract invoice data from: "{final_text}"
            MATH RULES:
            1. Extract the UNIT PRICE (Cost for 1 item), NOT the total sum.
            2. If user says "500 for each of 5 people", Price = 500, Qty = 5.
            3. Do not multiply numbers yourself.
            
            Return ONLY RAW JSON (No markdown, no text):
            {{ "client_name": "Name", "items": [{{"description": "Item", "quantity": 1, "price": 0}}], "note": "Note" }}
            """
            
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user", "content": prompt}])
            
            try:
                # --- FIX: SMART JSON CLEANER ---
                raw_content = res.choices[0].message.content
                # Find the first { and the last }
                start = raw_content.find("{")
                end = raw_content.rfind("}") + 1
                
                if start != -1 and end != -1:
                    clean_json = raw_content[start:end]
                    data = json.loads(clean_json)
                    
                    # Deduct credit ONLY if JSON was valid
                    new_credits = credits - 1
                    update_credits(st.session_state.user, new_credits)
                    
                    pdf_bytes = create_pro_pdf(company_name, data)
                    
                    st.balloons()
                    st.success("Invoice Ready!")
                    st.download_button("📥 Download PDF", pdf_bytes, "Invoice.pdf", "application/pdf")
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error("AI Error: Could not generate valid invoice data. Please try again.")

            except Exception as e:
                st.error(f"Parsing Error: {e}. Please check your text input.")