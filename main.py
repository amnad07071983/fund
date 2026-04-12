import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from fpdf import FPDF
import base64

# ================= CONFIGURATION =================
SHEET_ID = "1Geh6DEbnkdDAgTQx_G4wu4cEjchO5EPwLcNCheSICNY"
FONT_NAME = "THSarabunBold"
FONT_FILE = "THSARABUN BOLD.ttf"  # ชื่อไฟล์ต้องตรงกับที่อัปโหลดขึ้น GitHub
# =================================================

# --- 1. การเชื่อมต่อ Google Sheets ---
def init_connection():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"การเชื่อมต่อฐานข้อมูลผิดพลาด: {e}")
        return None

# --- 2. ฟังก์ชันดึงข้อมูลจากแผ่นงาน ---
def get_data(sheet_name):
    client = init_connection()
    if client:
        try:
            sh = client.open_by_key(SHEET_ID)
            worksheet = sh.worksheet(sheet_name)
            return pd.DataFrame(worksheet.get_all_records())
        except Exception as e:
            st.error(f"ไม่พบแผ่นงานชื่อ '{sheet_name}': {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# --- 3. ฟังก์ชันสร้าง PDF (รองรับภาษาไทย) ---
def create_pdf(df, user_id):
    pdf = FPDF()
    pdf.add_page()
    
    # ลงทะเบียนฟอนต์ไทย
    try:
        pdf.add_font(FONT_NAME, '', FONT_FILE)
        pdf.set_font(FONT_NAME, '', 20)
    except:
        pdf.set_font("Arial", 'B', 16) # Fallback กรณีหาไฟล์ฟอนต์ไม่เจอ

    # ส่วนหัว
    pdf.cell(0, 15, f"รายงานข้อมูลสำหรับคุณ: {user_id}", ln=True, align='C')
    pdf.ln(5)
    
    # ตารางข้อมูล
    pdf.set_font(FONT_NAME, '', 14)
    # เขียนหัวตาราง
    for col in df.columns:
        pdf.cell(40, 10, str(col), border=1, align='C')
    pdf.ln()
    
    # เขียนข้อมูลแต่ละแถว
    for _, row in df.iterrows():
        for item in row:
            pdf.cell(40, 10, str(item), border=1)
        pdf.ln()
        
    return pdf.output()

# --- 4. ระบบ Login และการจัดการ Session ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 เข้าสู่ระบบ")
    with st.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            users_df = get_data("users")
            if not users_df.empty:
                # ตรวจสอบความถูกต้อง
                match = users_df[(users_df['username'].astype(str) == u) & 
                                 (users_df['password'].astype(str) == p)]
                if not match.empty:
                    st.session_state.logged_in = True
                    st.session_state.user_id = u
                    st.rerun()
                else:
                    st.error("Username หรือ Password ไม่ถูกต้อง")

# --- 5. หน้าแอปพลิเคชันหลัก ---
else:
    st.sidebar.title(f"สวัสดี, {st.session_state.user_id}")
    choice = st.sidebar.radio("เมนูหลัก", ["หน้าหลัก (Data)", "รายงาน (Data1)", "ข้อมูล Data2", "ข้อมูล Data3"])
    
    if st.sidebar.button("ออกจากระบบ"):
        st.session_state.logged_in = False
        st.rerun()

    # ฟังก์ชันแสดงผลและกรองข้อมูล
    def display_content(sheet_name, can_export=False):
        st.header(f"📊 ข้อมูลแผ่นงาน {sheet_name}")
        df = get_data(sheet_name)
        
        if not df.empty and 'user' in df.columns:
            # กรองข้อมูลเฉพาะของ User ที่ล็อกอิน
            filtered = df[df['user'].astype(str) == st.session_state.user_id]
            
            if not filtered.empty:
                st.dataframe(filtered, use_container_width=True)
                
                if can_export:
                    if st.button("📥 ส่งออกเป็น PDF"):
                        pdf_bytes = create_pdf(filtered, st.session_state.user_id)
                        b64 = base64.b64encode(pdf_bytes).decode()
                        href = f'<a href="data:application/pdf;base64,{b64}" download="report_{sheet_name}.pdf" style="text-decoration:none; background-color:#F63366; color:white; padding:10px 20px; border-radius:5px;">คลิกเพื่อดาวน์โหลด PDF</a>'
                        st.markdown(href, unsafe_allow_html=True)
            else:
                st.info("ไม่พบข้อมูลของคุณในระบบ")
        else:
            st.warning("ไม่มีข้อมูล หรือไม่พบคอลัมน์ 'user'")

    # ส่วนการแสดงหน้าตามเมนู
    if choice == "หน้าหลัก (Data)":
        display_content("data")
    elif choice == "รายงาน (Data1)":
        display_content("data1", can_export=True)
    elif choice == "ข้อมูล Data2":
        display_content("data2")
    elif choice == "ข้อมูล Data3":
        display_content("data3")
