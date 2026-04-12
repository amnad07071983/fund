import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from fpdf import FPDF
import base64

# ================= CONFIGURATION =================
SHEET_ID = "1Geh6DEbnkdDAgTQx_G4wu4cEjchO5EPwLcNCheSICNY"
FONT_FILE = "THSARABUN BOLD.ttf" 
# =================================================

# --- เชื่อมต่อ Google Sheets ผ่าน Secrets ---
def init_connection():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # ดึงข้อมูลจาก Streamlit Secrets โดยตรง
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(creds_info), scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"การเชื่อมต่อผิดพลาด: {e}")
        return None

def get_data(sheet_name):
    client = init_connection()
    if client:
        try:
            sh = client.open_by_key(SHEET_ID)
            worksheet = sh.worksheet(sheet_name)
            return pd.DataFrame(worksheet.get_all_records())
        except Exception as e:
            st.error(f"Error แผ่นงาน {sheet_name}: {e}")
    return pd.DataFrame()

# --- สร้าง PDF รองรับภาษาไทย ---
def create_pdf(df, user_id):
    pdf = FPDF()
    pdf.add_page()
    try:
        pdf.add_font('THSarabun', '', FONT_FILE)
        pdf.set_font('THSarabun', '', 18)
    except:
        pdf.set_font("Arial", size=14)

    pdf.cell(0, 10, f"รายงานข้อมูล User: {user_id}", ln=True, align='C')
    pdf.ln(5)
    
    # วาดตาราง
    pdf.set_font('THSarabun', '', 12)
    for col in df.columns:
        pdf.cell(38, 10, str(col), border=1, align='C')
    pdf.ln()
    
    for _, row in df.iterrows():
        for item in row:
            pdf.cell(38, 10, str(item), border=1)
        pdf.ln()
        
    return pdf.output()

# --- ระบบ Session & UI ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 Login System")
    with st.form("login_box"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("เข้าสู่ระบบ"):
            users_df = get_data("users")
            if not users_df.empty:
                auth = users_df[(users_df['username'].astype(str) == u) & 
                                 (users_df['password'].astype(str) == p)]
                if not auth.empty:
                    st.session_state.logged_in = True
                    st.session_state.user_id = u
                    st.rerun()
                else:
                    st.error("Username หรือ Password ไม่ถูกต้อง")
else:
    st.sidebar.success(f"User: {st.session_state.user_id}")
    menu = st.sidebar.radio("เมนู", ["Data", "Data1 (PDF)", "Data2", "Data3"])
    
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    def show_page(name, pdf_mode=False):
        st.subheader(f"📄 ข้อมูลจาก {name}")
        df = get_data(name)
        if not df.empty and 'user' in df.columns:
            filtered = df[df['user'].astype(str) == st.session_state.user_id]
            if not filtered.empty:
                st.dataframe(filtered)
                if pdf_mode:
                    if st.button("Download PDF"):
                        pdf_bytes = create_pdf(filtered, st.session_state.user_id)
                        b64 = base64.b64encode(pdf_bytes).decode()
                        href = f'<a href="data:application/pdf;base64,{b64}" download="report.pdf" style="background:#F63366;color:white;padding:10px;border-radius:5px;text-decoration:none;">Download File</a>'
                        st.markdown(href, unsafe_allow_html=True)
            else:
                st.info("ไม่มีข้อมูลของคุณ")

    if menu == "Data": show_page("data")
    elif menu == "Data1 (PDF)": show_page("data1", True)
    elif menu == "Data2": show_page("data2")
    elif menu == "Data3": show_page("data3")
