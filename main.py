import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from io import BytesIO

# ===== เพิ่ม reportlab =====
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
# ==========================

# ================= CONFIGURATION =================
SHEET_ID = "1Geh6DEbnkdDAgTQx_G4wu4cEjchO5EPwLcNCheSICNY"
FONT_FILE = "THSARABUN BOLD.ttf" 
WATERMARK_FILE = "p1.png"
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


# ====== สร้าง PDF (เปลี่ยนเป็น ReportLab + ลายน้ำโปร่งใส) ======
def create_pdf(df, sheet_name):
    buffer = BytesIO()

    # โหลดฟอนต์ไทย
    try:
        pdfmetrics.registerFont(TTFont('THSarabun', FONT_FILE))
        font_name = 'THSarabun'
    except:
        font_name = 'Helvetica'

    # ฟังก์ชันลายน้ำ
    def add_watermark(c: canvas.Canvas, doc):
        try:
            c.saveState()
            c.setFillAlpha(0.05)  # 👈 ปรับความจางตรงนี้
            width, height = A4

            img_width = 120 * mm
            img_height = 120 * mm
            x = (width - img_width) / 2
            y = (height - img_height) / 2

            c.drawImage(WATERMARK_FILE, x, y,
                        width=img_width,
                        height=img_height,
                        mask='auto')
            c.restoreState()
        except:
            pass

    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    if not df.empty:
        for _, row in df.iterrows():
            for col in df.columns:
                text = f"{col} : {row[col]}"
                story.append(Paragraph(text, styles["Normal"]))
                story.append(Spacer(1, 8))

    doc.build(story, onFirstPage=add_watermark, onLaterPages=add_watermark)

    return buffer.getvalue()
# ===============================================================


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
                    st.error("ข้อมูล Login ไม่ถูกต้อง")
            else:
                st.error("ไม่สามารถเชื่อมต่อฐานข้อมูลผู้ใช้ได้")
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
            
            if sheet_name == "data":
                col1, col2 = st.columns(2)
                with col1:
                    try:
                        pdf_data = create_pdf(filtered, sheet_name)
                        st.download_button(
                            label="📥 PDF Report",
                            data=pdf_data,
                            file_name=f"report_{st.session_state.user_id}.pdf",
                            mime="application/pdf"
                        )
                    except Exception as e:
                        st.error(f"ไม่สามารถสร้าง PDF ได้: {e}")
                with col2:
                    excel_data = to_excel(filtered)
                    st.download_button(
                        label="📥 Excel Report",
                        data=excel_data,
                        file_name=f"report_{st.session_state.user_id}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            else:
                excel_data = to_excel(filtered)
                st.download_button(
                    label="📥 Download Excel",
                    data=excel_data,
                    file_name=f"data_{sheet_name}.xlsx",
                    use_container_width=True
                )
        else:
            st.info("ไม่พบข้อมูลของคุณในส่วนนี้")
