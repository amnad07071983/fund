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
            df = pd.DataFrame(worksheet.get_all_records())
            
            # --- ฟอร์แมตตัวเลขที่มีคอมม่าคั่น ---
            target_cols = [
                "เงินออม-เพิ่มขึ้น", "เงินออม-ลดลง", "เงินออม-คงเหลือ",
                "หนี้-เพิ่มขึ้น", "หนี้-ลดลง", "หนี้คงเหลือ", "ดอกเบี้ย"
            ]
            for col in target_cols:
                if col in df.columns:
                    # แปลงเป็น numeric ก่อนเพื่อความถูกต้อง แล้วฟอร์แมต string
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                    df[col] = df[col].apply(lambda x: "{:,.2f}".format(x))
            return df
        except Exception as e:
            st.error(f"Error แผ่นงาน {sheet_name}: {e}")
    return pd.DataFrame()

def create_pdf(df, user_id, sheet_name):
    pdf = FPDF()
    pdf.add_page()
    
    try:
        pdf.add_font('THSarabun', '', FONT_FILE, uni=True)
    except:
        pass

    # --- ส่วนหัวรายงาน (บังคับพิมพ์ที่ตำแหน่งบนสุด) ---
    pdf.set_y(15)
    pdf.set_font('THSarabun', '', 20)
    pdf.cell(0, 10, "บริษัท น้ำตาลกกกก จำกัด", ln=True, align='C')
    pdf.set_font('THSarabun', '', 16)
    pdf.cell(0, 10, "รายงานสรุปกองทุน", ln=True, align='C')
    pdf.line(10, 35, 200, 35) # เส้นคั่นหัวกระดาษ
    pdf.ln(10)

    if not df.empty:
        # รูปแบบสำหรับแผ่นงาน "data" (รายตั้ง)
        if sheet_name == "data":
            pdf.set_font('THSarabun', '', 14)
            for _, row in df.iterrows():
                for col in df.columns:
                    pdf.set_font('THSarabun', '', 14)
                    pdf.cell(60, 10, f"{col} :", border='B')
                    pdf.cell(130, 10, str(row[col]), border='B', align='R') # ชิดขวาเพื่อความสวยงาม
                    pdf.ln(12)
                pdf.ln(10)
    
    # แก้ไขปัญหา a bytes-like object is required โดยการคืนค่า output โดยตรง
    return pdf.output(dest='S').encode('latin-1')

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

# --- ระบบ UI & Logic ---
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
                auth = users_df[(users_df['username'].astype(str) == str(u)) & 
                                (users_df['password'].astype(str) == str(p))]
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
            filtered = df[df['user'].astype(str) == str(st.session_state.user_id)]
            if not filtered.empty:
                st.dataframe(filtered)
                st.write("---")
                
                # แสดงปุ่มตามเงื่อนไข
                if name == "data":
                    c1, c2 = st.columns(2)
                    with c1:
                        try:
                            pdf_bytes = create_pdf(filtered, st.session_state.user_id, name)
                            st.download_button("📥 Download PDF", pdf_bytes, f"report_{name}.pdf", "application/pdf")
                        except Exception as e: st.error(f"Error PDF: {e}")
                    with c2:
                        try:
                            excel_data = to_excel(filtered)
                            st.download_button("📥 Download Excel", excel_data, f"report_{name}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                        except Exception as e: st.error(f"Error Excel: {e}")
                else:
                    try:
                        excel_data = to_excel(filtered)
                        st.download_button("📥 Download Excel", excel_data, f"report_{name}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                    except Exception as e: st.error(f"Error Excel: {e}")
            else:
                st.info("ไม่มีข้อมูลของคุณ")

    mapping = {"ข้อมูลสรุป": "data", "เงินออม": "data1", "เงินกู้ยืม": "data2", "หลักทรัพย์ค้ำประกัน": "data3"}
    show_page(mapping[menu])
