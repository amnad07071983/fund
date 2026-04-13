import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from fpdf import FPDF
from io import BytesIO

# ================= CONFIGURATION =================
# ตรวจสอบให้แน่ใจว่าไฟล์ Font อยู่ในโฟลเดอร์เดียวกับไฟล์ main.py
SHEET_ID = "1Geh6DEbnkdDAgTQx_G4wu4cEjchO5EPwLcNCheSICNY"
FONT_FILE = "THSARABUN BOLD.ttf" 
# =================================================

# เชื่อมต่อ Google Sheets
@st.cache_resource
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

# ดึงข้อมูลจาก Sheet
@st.cache_data(ttl=600)
def get_data_from_sheet(sheet_name):
    client = init_connection()
    if client:
        try:
            sh = client.open_by_key(SHEET_ID)
            worksheet = sh.worksheet(sheet_name)
            df = pd.DataFrame(worksheet.get_all_records())
            
            # ฟอร์แมตตัวเลขที่มีคอมม่า
            target_cols = ["เงินออม-เพิ่มขึ้น", "เงินออม-ลดลง", "เงินออม-คงเหลือ", 
                           "หนี้-เพิ่มขึ้น", "หนี้-ลดลง", "หนี้คงเหลือ", "ดอกเบี้ย"]
            for col in target_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                    df[col] = df[col].apply(lambda x: "{:,.2f}".format(x))
            return df
        except Exception as e:
            st.error(f"Error {sheet_name}: {e}")
    return pd.DataFrame()

# สร้างไฟล์ PDF (จุดที่แก้ไข Error)
def create_pdf(df, sheet_name):
    # ใช้ fpdf2 แนะนำให้ install ด้วย 'pip install fpdf2'
    pdf = FPDF()
    pdf.add_page()
    
    try:
        # การโหลดฟอนต์สำหรับ fpdf2 (ไม่ต้องใช้ uni=True)
        pdf.add_font('THSarabun', '', FONT_FILE)
        pdf.set_font('THSarabun', '', 16)
    except Exception as e:
        st.warning(f"ระบบหาไฟล์ฟอนต์ไทยไม่เจอ: {e}")
        pdf.set_font("Arial", size=12)

    if not df.empty:
        # วาดกรอบและแสดงข้อมูล
        total_rows = len(df.columns)
        frame_height = (total_rows * 10) + 10
        pdf.rect(10, 10, 190, frame_height)
        
        pdf.set_y(15)
        for _, row in df.iterrows():
            for col in df.columns:
                pdf.set_x(15)
                # จัดการข้อมูลให้เป็น string ก่อนใส่ใน PDF
                col_name = str(col)
                val_data = str(row[col])
                pdf.cell(60, 10, f"{col_name} : ", border=0)
                pdf.cell(115, 10, val_data, border=0, align='L')
                pdf.ln(10)
    
    # แก้ไขจุด AttributeError: คืนค่าเป็น bytes โดยตรง
    return pdf.output()

# สร้างไฟล์ Excel
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

# --- Main Logic ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 ระบบกองทุน (สมาชิก 1,000 คน)")
    with st.form("login_box"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("เข้าสู่ระบบ"):
            users_df = get_data_from_sheet("users")
            if not users_df.empty:
                auth = users_df[(users_df['username'].astype(str) == str(u)) & 
                                (users_df['password'].astype(str) == str(p))]
                if not auth.empty:
                    st.session_state.logged_in = True
                    st.session_state.user_id = str(u)
                    st.rerun()
                else:
                    st.error("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
            else:
                st.error("ไม่สามารถดึงข้อมูลผู้ใช้งานได้")
else:
    st.sidebar.write(f"สวัสดีคุณ: **{st.session_state.user_id}**")
    menu = st.sidebar.radio("เมนู", ["ข้อมูลสรุป", "เงินออม", "เงินกู้ยืม", "หลักทรัพย์ค้ำประกัน"])
    
    if st.sidebar.button("ออกจากระบบ"):
        st.session_state.logged_in = False
        st.cache_data.clear()
        st.rerun()

    mapping = {"ข้อมูลสรุป": "data", "เงินออม": "data1", "เงินกู้ยืม": "data2", "หลักทรัพย์ค้ำประกัน": "data3"}
    sheet_name = mapping[menu]
    
    st.subheader(f"📄 {menu}")
    df = get_data_from_sheet(sheet_name)
    
    if not df.empty and 'user' in df.columns:
        filtered = df[df['user'].astype(str) == st.session_state.user_id]
        if not filtered.empty:
            st.dataframe(filtered, use_container_width=True)
            st.divider()
            
            # ส่วนของการ Download
            if sheet_name == "data":
                col1, col2 = st.columns(2)
                with col1:
                    # สร้าง PDF
                    try:
                        pdf_bytes = create_pdf(filtered, sheet_name)
                        st.download_button(
                            label="📥 PDF Report",
                            data=pdf_bytes,
                            file_name=f"report_{st.session_state.user_id}.pdf",
                            mime="application/pdf"
                        )
                    except Exception as e:
                        st.error(f"ไม่สามารถสร้าง PDF ได้: {e}")
                with col2:
                    excel_bytes = to_excel(filtered)
                    st.download_button("📥 Excel Report", excel_bytes, f"report_{st.session_state.user_id}.xlsx")
            else:
                excel_bytes = to_excel(filtered)
                st.download_button("📥 Download Excel", excel_bytes, f"data_{sheet_name}.xlsx", use_container_width=True)
        else:
            st.info("ไม่พบข้อมูลของคุณ")
