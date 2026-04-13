import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from fpdf import FPDF
from io import BytesIO
import os

# ================= CONFIGURATION =================
SHEET_ID = "1Geh6DEbnkdDAgTQx_G4wu4cEjchO5EPwLcNCheSICNY"
FONT_FILE = "THSARABUN BOLD.ttf" 
LOGO_FILE = "p1.png" 
# =================================================

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

def create_pdf(df, sheet_name):
    # ใช้ fpdf2
    pdf = FPDF()
    pdf.add_page()
    
    # --- 1. ส่วนของลายน้ำ (Watermark) ---
    if os.path.exists(LOGO_FILE):
        try:
            img_w = 160  # กำหนดขนาดรูปขนาดใหญ่
            # คำนวณกึ่งกลางหน้า A4 (กว้าง 210 มม. สูง 297 มม.)
            x_pos = (210 - img_w) / 2
            y_pos = (297 - img_w) / 2 
            
            pdf.set_alpha(0.4) # ตั้งค่าลายน้ำจาง 40%
            pdf.image(LOGO_FILE, x=x_pos, y=y_pos, w=img_w)
            pdf.set_alpha(1.0) # คืนค่าความชัดปกติให้ตัวหนังสือ
        except Exception as e:
            print(f"Watermark Error: {e}")

    # --- 2. การตั้งค่าฟอนต์ ---
    try:
        pdf.add_font('THSarabun', '', FONT_FILE, uni=True)
        pdf.set_font('THSarabun', '', 14)
    except:
        pdf.set_font("Arial", size=12)

    # --- 3. การสร้างข้อมูลในกรอบ (หน้า data) ---
    if not df.empty and sheet_name == "data":
        # คำนวณความสูงกรอบตามจำนวนคอลัมน์
        frame_height = (len(df.columns) * 10) + 10
        pdf.rect(10, 10, 190, frame_height) # วาดกรอบสี่เหลี่ยมอันเดียวคลุมทั้งหมด
        
        pdf.set_y(15)
        for _, row in df.iterrows():
            for col in df.columns:
                pdf.set_x(15)
                pdf.cell(60, 10, f"{col} : ", border=0)
                pdf.cell(115, 10, str(row[col]), border=0, align='L')
                pdf.ln(10)
    
    # ส่งค่ากลับเป็น bytes เพื่อรองรับ download_button
    return bytes(pdf.output())

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

# --- ระบบแสดงผลหลัก ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 ระบบกองทุนพนักงาน")
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
                    st.error("ข้อมูลไม่ถูกต้อง")
else:
    st.sidebar.success(f"สวัสดี: {st.session_state.user_id}")
    menu = st.sidebar.radio("เลือกรายการ", ["ข้อมูลสรุป", "เงินออม", "เงินกู้ยืม", "หลักทรัพย์ค้ำประกัน"])
    
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
            
            if sheet_name == "data":
                c1, c2 = st.columns(2)
                with c1:
                    try:
                        pdf_data = create_pdf(filtered, sheet_name)
                        st.download_button("📥 Download PDF", pdf_data, f"report_{st.session_state.user_id}.pdf", "application/pdf")
                    except Exception as e:
                        st.error(f"Error PDF: {e}")
                with c2:
                    try:
                        excel_data = to_excel(filtered)
                        st.download_button("📥 Download Excel", excel_data, f"report_{st.session_state.user_id}.xlsx")
                    except Exception as e:
                        st.error(f"Error Excel: {e}")
            else:
                try:
                    excel_data = to_excel(filtered)
                    st.download_button("📥 Download Excel", excel_data, f"data_{sheet_name}.xlsx", use_container_width=True)
                except Exception as e:
                    st.error(f"Error Excel: {e}")
        else:
            st.info("ไม่มีข้อมูลของคุณในระบบ")
