import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from fpdf import FPDF
import base64

# ================= CONFIGURATION =================
# นำ ID ของ Google Sheet มาใส่ที่นี่
SHEET_ID = "1Geh6DEbnkdDAgTQx_G4wu4cEjchO5EPwLcNCheSICNY"
# =================================================

# --- การเชื่อมต่อ Google Sheets ---
def init_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    return client

# --- ฟังก์ชันดึงข้อมูลจากแผ่นงานที่ระบุ ---
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

# --- ฟังก์ชันสร้างและดาวน์โหลด PDF (สำหรับหน้า Data1) ---
def export_to_pdf(df, user_id):
    pdf = FPDF()
    pdf.add_page()
    
    # ตั้งค่าฟอนต์ (หากไม่มีฟอนต์ไทยในโฟลเดอร์ ให้ใช้ Arial แทนก่อน)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f"Data Report for: {user_id}", ln=True, align='C')
    pdf.ln(10)
    
    # ส่วนหัวตาราง
    pdf.set_font("Arial", 'B', 10)
    cols = list(df.columns)
    for col in cols:
        pdf.cell(40, 10, str(col), border=1)
    pdf.ln()
    
    # ข้อมูลในตาราง
    pdf.set_font("Arial", size=10)
    for index, row in df.iterrows():
        for item in row:
            pdf.cell(40, 10, str(item), border=1)
        pdf.ln()
        
    return pdf.output(dest='S').encode('latin-1')

# --- ส่วนควบคุม Session State ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = ""

# --- หน้าจอ Login ---
if not st.session_state.logged_in:
    st.title("🔐 เข้าสู่ระบบ")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            users_df = get_data_from_sheet("users")
            if not users_df.empty:
                # ตรวจสอบ user และ password
                auth = users_df[(users_df['username'] == username) & (users_df['password'].astype(str) == str(password))]
                if not auth.empty:
                    st.session_state.logged_in = True
                    st.session_state.user_id = username
                    st.success("ล็อกอินสำเร็จ!")
                    st.rerun()
                else:
                    st.error("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
            else:
                st.warning("ไม่สามารถดึงข้อมูลรายชื่อผู้ใช้งานได้")

# --- หน้าจอหลักเมื่อ Login แล้ว ---
else:
    st.sidebar.header(f"👤 ผู้ใช้งาน: {st.session_state.user_id}")
    menu = st.sidebar.radio("เลือกเมนู", ["Data (ทั่วไป)", "Data1 (ส่งออก PDF)", "Data2", "Data3"])
    
    if st.sidebar.button("Log out"):
        st.session_state.logged_in = False
        st.rerun()

    # ฟังก์ชันกรองข้อมูลตาม User ปัจจุบัน
    def show_filtered_data(sheet_name, enable_pdf=False):
        st.header(f"📄 ข้อมูลจากแผ่นงาน: {sheet_name}")
        df = get_data_from_sheet(sheet_name)
        
        if not df.empty:
            # กรองข้อมูลตามคอลัมน์ 'user'
            if 'user' in df.columns:
                filtered_df = df[df['user'] == st.session_state.user_id]
                
                if not filtered_df.empty:
                    st.dataframe(filtered_df, use_container_width=True)
                    
                    # เงื่อนไขการส่งออก PDF สำหรับ Data1
                    if enable_pdf:
                        if st.button("📥 ดาวน์โหลดข้อมูลเป็น PDF"):
                            try:
                                pdf_data = export_to_pdf(filtered_df, st.session_state.user_id)
                                b64 = base64.b64encode(pdf_data).decode()
                                href = f'<a href="data:application/octet-stream;base64,{b64}" download="report_{sheet_name}.pdf" style="text-decoration:none; background-color:#F63366; color:white; padding:10px 20px; border-radius:5px;">คลิกที่นี่เพื่อบันทึกไฟล์ PDF</a>'
                                st.markdown(href, unsafe_allow_html=True)
                            except Exception as e:
                                st.error(f"ไม่สามารถสร้าง PDF ได้: {e} (แนะนำให้เช็คข้อมูลภาษาไทยหรือฟอนต์)")
                else:
                    st.info("ไม่พบข้อมูลที่ตรงกับผู้ใช้งานของคุณ")
            else:
                st.error(f"ไม่พบคอลัมน์ 'user' ในแผ่นงาน {sheet_name}")
        else:
            st.info("ไม่มีข้อมูลในแผ่นงานนี้")

    # เรียกใช้ตามเมนูที่เลือก
    if menu == "Data (ทั่วไป)":
        show_filtered_data("data")
    elif menu == "Data1 (ส่งออก PDF)":
        show_filtered_data("data1", enable_pdf=True)
    elif menu == "Data2":
        show_filtered_data("data2")
    elif menu == "Data3":
        show_filtered_data("data3")
