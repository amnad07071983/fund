import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from fpdf import FPDF
import base64
from io import BytesIO

# ================= CONFIGURATION =================
SHEET_ID = "1Geh6DEbnkdDAgTQx_G4wu4cEjchO5EPwLcNCheSICNY"
FONT_FILE = "THSARABUN BOLD.ttf" 
# =================================================

# --- เชื่อมต่อ Google Sheets ผ่าน Secrets ---
def init_connection():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
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

# --- สร้าง PDF (แยกรูปแบบสำหรับ data และอื่นๆ) ---
def create_pdf(df, user_id, sheet_name):
    pdf = FPDF()
    pdf.add_page()
    
    try:
        pdf.add_font('THSarabun', '', FONT_FILE, uni=True)
        pdf.set_font('THSarabun', '', 18)
    except:
        pdf.set_font("Arial", size=14)

    pdf.cell(0, 10, f"รายงานข้อมูล ({sheet_name}) - User: {user_id}", ln=True, align='C')
    pdf.ln(5)
    
    if not df.empty:
        # กรณีแผ่นงาน "data" ให้แสดงผลแบบแนวตั้ง (List View)
        if sheet_name == "data":
            pdf.set_font('THSarabun', '', 14)
            for _, row in df.iterrows():
                for col in df.columns:
                    # หัวข้อ (พื้นหลังสีเทาอ่อน)
                    pdf.set_fill_color(240, 240, 240)
                    pdf.cell(50, 10, str(col), border=1, fill=True)
                    # ข้อมูล
                    pdf.cell(140, 10, str(row[col]), border=1)
                    pdf.ln()
                pdf.ln(10) # เว้นระยะห่างระหว่างกลุ่มข้อมูล
        
        # กรณีแผ่นงานอื่นๆ ให้แสดงแบบตารางแนวนอน (Table View)
        else:
            pdf.set_font('THSarabun', '', 12)
            col_width = 190 / len(df.columns)
            # ส่วนหัวตาราง
            for col in df.columns:
                pdf.cell(col_width, 10, str(col), border=1, align='C')
            pdf.ln()
            # ส่วนข้อมูล
            for _, row in df.iterrows():
                for item in row:
                    pdf.cell(col_width, 10, str(item), border=1)
                pdf.ln()
    
    return pdf.output(dest='S').encode('latin-1')

# --- ฟังก์ชันแปลงข้อมูลเป็น Excel ---
def to_excel(df):
    output = BytesIO()
    # ตรวจสอบว่าได้ติดตั้ง xlsxwriter ในระบบแล้ว
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

# --- ระบบ Session & UI ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 ลงชื่อเข้าใช้ระบบ")
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
    menu = st.sidebar.radio("เมนู", ["ข้อมูลสรุป", "เงินออม", "เงินกู้ยืม", "หลักทรัพย์ค้ำประกัน"])
    
    if st.sidebar.button("ออกจากระบบ"):
        st.session_state.logged_in = False
        st.rerun()

    def show_page(name):
        st.subheader(f"📄 ข้อมูลจาก {name}")
        df = get_data(name)
        
        if not df.empty and 'user' in df.columns:
            filtered = df[df['user'].astype(str) == st.session_state.user_id]
            
            if not filtered.empty:
                st.dataframe(filtered)
                st.write("---")
                
                # --- ส่วนปุ่ม Download ---
                c1, c2 = st.columns(2)
                
                with c1:
                    try:
                        pdf_bytes = create_pdf(filtered, st.session_state.user_id, name)
                        st.download_button(
                            label="📥 Download PDF",
                            data=pdf_bytes,
                            file_name=f"report_{name}.pdf",
                            mime="application/pdf"
                        )
                    except Exception as e:
                        st.error(f"ไม่สามารถสร้าง PDF ได้: {e}")

                with c2:
                    try:
                        excel_data = to_excel(filtered)
                        st.download_button(
                            label="📥 Download Excel",
                            data=excel_data,
                            file_name=f"report_{name}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    except Exception as e:
                        st.error(f"ไม่สามารถสร้าง Excel ได้: {e}")
            else:
                st.info("ไม่มีข้อมูลของคุณในระบบ")
        else:
            st.warning(f"ไม่พบข้อมูลที่ต้องการในแผ่นงาน {name}")

    # การเรียกใช้งานตามเมนู
    if menu == "ข้อมูลสรุป": 
        show_page("data")
    elif menu == "เงินออม": 
        show_page("data1")
    elif menu == "เงินกู้ยืม": 
        show_page("data2")
    elif menu == "หลักทรัพย์ค้ำประกัน": 
        show_page("data3")
