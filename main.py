import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from fpdf import FPDF
import base64

# ================= CONFIGURATION =================
SHEET_ID = "1Geh6DEbnkdDAgTQx_G4wu4cEjchO5EPwLcNCheSICNY"
FONT_PATH = "THSARABUN BOLD.ttf" # ชื่อไฟล์ฟอนต์ต้องตรงกันเป๊ะๆ
# =================================================

# --- การเชื่อมต่อ Google Sheets ---
def init_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    return client

# --- ฟังก์ชันดึงข้อมูลจากแผ่นงาน ---
def get_data_from_sheet(sheet_name):
    try:
        client = init_connection()
        sh = client.open_by_key(SHEET_ID)
        worksheet = sh.worksheet(sheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการดึงข้อมูลจาก {sheet_name}: {e}")
        return pd.DataFrame()

# --- ฟังก์ชันสร้าง PDF รองรับภาษาไทย ---
def export_to_pdf(df, user_id):
    # ใช้ fpdf2 (จะเรียกใช้งานเหมือน fpdf ปกติแต่รองรับ Unicode)
    pdf = FPDF()
    pdf.add_page()
    
    # 1. ลงทะเบียนและใช้ฟอนต์ไทย
    try:
        pdf.add_font('THSarabun', '', FONT_PATH, uni=True)
        pdf.set_font('THSarabun', '', 18)
    except:
        st.warning("ไม่พบไฟล์ฟอนต์ THSARABUN BOLD.ttf ระบบจะใช้ฟอนต์มาตรฐานแทน (ภาษาไทยอาจไม่แสดงผล)")
        pdf.set_font("Arial", 'B', 16)

    # หัวข้อรายงาน
    pdf.cell(0, 15, f"รายงานข้อมูลผู้ใช้งาน: {user_id}", ln=True, align='C')
    pdf.ln(5)
    
    # ส่วนของเนื้อหาตาราง
    pdf.set_font('THSarabun', '', 12)
    
    # วนลูปคอลัมน์
    cols = list(df.columns)
    for col in cols:
        pdf.cell(40, 10, str(col), border=1, align='C')
    pdf.ln()
    
    # วนลูปข้อมูลในแถว
    for index, row in df.iterrows():
        for item in row:
            pdf.cell(40, 10, str(item), border=1)
        pdf.ln()
        
    # ส่งค่าออกเป็น bytes
    return pdf.output() 

# --- ระบบจัดการ Login ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = ""

if not st.session_state.logged_in:
    st.title("🔐 เข้าสู่ระบบ")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            users_df = get_data_from_sheet("users")
            if not users_df.empty:
                auth = users_df[(users_df['username'].astype(str) == str(username)) & 
                                (users_df['password'].astype(str) == str(password))]
                if not auth.empty:
                    st.session_state.logged_in = True
                    st.session_state.user_id = username
                    st.rerun()
                else:
                    st.error("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

else:
    # --- หน้าจอหลัก ---
    st.sidebar.header(f"👤 ผู้ใช้งาน: {st.session_state.user_id}")
    menu = st.sidebar.radio("เลือกเมนู", ["Data", "Data1 (PDF)", "Data2", "Data3"])
    
    if st.sidebar.button("Log out"):
        st.session_state.logged_in = False
        st.rerun()

    def show_filtered_data(sheet_name, enable_pdf=False):
        st.header(f"📄 แผ่นงาน: {sheet_name}")
        df = get_data_from_sheet(sheet_name)
        
        if not df.empty:
            if 'user' in df.columns:
                filtered_df = df[df['user'].astype(str) == str(st.session_state.user_id)]
                
                if not filtered_df.empty:
                    st.table(filtered_df) # ใช้ st.table เพื่อให้ดูง่ายบนเว็บ
                    
                    if enable_pdf:
                        if st.button("📥 ดาวน์โหลด PDF"):
                            pdf_output = export_to_pdf(filtered_df, st.session_state.user_id)
                            # สร้าง Link สำหรับดาวน์โหลด
                            b64 = base64.b64encode(pdf_output).decode()
                            href = f'<a href="data:application/pdf;base64,{b64}" download="report_{st.session_state.user_id}.pdf" style="padding:10px; background-color:#F63366; color:white; border-radius:5px; text-decoration:none;">Download PDF File</a>'
                            st.markdown(href, unsafe_allow_html=True)
                else:
                    st.info("ไม่พบข้อมูลของคุณในส่วนนี้")
            else:
                st.error("ไม่พบคอลัมน์ 'user' เพื่อใช้ในการกรองข้อมูล")
        else:
            st.info("ไม่มีข้อมูล")

    # แยกการแสดงผลตามเมนู
    if menu == "Data": show_filtered_data("data")
    elif menu == "Data1 (PDF)": show_filtered_data("data1", enable_pdf=True)
    elif menu == "Data2": show_filtered_data("data2")
    elif menu == "Data3": show_filtered_data("data3")
