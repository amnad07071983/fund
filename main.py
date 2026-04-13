import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from fpdf import FPDF
from io import BytesIO

# ================= CONFIGURATION =================
SHEET_ID = "1Geh6DEbnkdDAgTQx_G4wu4cEjchO5EPwLcNCheSICNY"
FONT_FILE = "THSARABUN BOLD.ttf" 
# =================================================

# ใช้ st.cache_resource เพื่อเชื่อมต่อครั้งเดียว
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

# ใช้ st.cache_data เพื่อจำค่าข้อมูล ลดการเรียก Google Sheets
@st.cache_data(ttl=600) # จำข้อมูลไว้ 10 นาที (600 วินาที)
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
    pdf = FPDF()
    pdf.add_page()
    try:
        pdf.add_font('THSarabun', '', FONT_FILE, uni=True)
        pdf.set_font('THSarabun', '', 14)
    except:
        pdf.set_font("Arial", size=12)

    if not df.empty and sheet_name == "data":
        total_rows = len(df.columns)
        frame_height = (total_rows * 10) + 10
        # วาดกรอบสี่เหลี่ยมคลุมข้อมูล
        pdf.rect(10, 10, 190, frame_height)
        
        pdf.set_y(15)
        for _, row in df.iterrows():
            for col in df.columns:
                pdf.set_x(15)
                pdf.cell(60, 10, f"{col} : ", border=0)
                pdf.cell(115, 10, str(row[col]), border=0, align='L')
                pdf.ln(10)
    
    return pdf.output(dest='S').encode('latin-1')

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
            auth = users_df[(users_df['username'].astype(str) == str(u)) & 
                            (users_df['password'].astype(str) == str(p))]
            if not auth.empty:
                st.session_state.logged_in = True
                st.session_state.user_id = str(u)
                st.rerun()
            else:
                st.error("ข้อมูลไม่ถูกต้อง")
else:
    st.sidebar.write(f"สวัสดีคุณ: **{st.session_state.user_id}**")
    menu = st.sidebar.radio("เมนู", ["ข้อมูลสรุป", "เงินออม", "เงินกู้ยืม", "หลักทรัพย์ค้ำประกัน"])
    
    if st.sidebar.button("ออกจากระบบ"):
        st.session_state.logged_in = False
        st.cache_data.clear() # เคลียร์แคชเมื่อออก
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
                col1, col2 = st.columns(2)
                with col1:
                    pdf_bytes = create_pdf(filtered, sheet_name)
                    st.download_button("📥 PDF Report", pdf_bytes, f"report_{st.session_state.user_id}.pdf", "application/pdf")
                with col2:
                    excel_bytes = to_excel(filtered)
                    st.download_button("📥 Excel Report", excel_bytes, f"report_{st.session_state.user_id}.xlsx")
            else:
                excel_bytes = to_excel(filtered)
                st.download_button("📥 Download Excel", excel_bytes, f"data_{sheet_name}.xlsx", use_container_width=True)
        else:
            st.info("ไม่พบข้อมูลของคุณ")
