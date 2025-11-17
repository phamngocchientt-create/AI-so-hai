import streamlit as st
import os
import tempfile
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google import genai
from google.genai import types

# ------------------- CẤU HÌNH BẮT BUỘC -------------------
MODEL_NAME = "gemini-2.0-flash"
PASSWORD = "giaovu123" 
DRIVE_FOLDER_NAME = "ChatbotDocs"

# ⚠️ LƯU Ý: Code này yêu cầu bạn đã dán toàn bộ thông tin Service Account 
# (JSON key) và GEMINI_API_KEY vào Streamlit Secrets!

# ------------------- Google Drive & File Handling -------------------
@st.cache_resource
def get_drive_service_creds():
    """Sử dụng Service Account để xác thực (thay cho OAuth Flow)."""
    try:
        creds_dict = {
            "type": st.secrets["type"],
            "project_id": st.secrets["project_id"],
            "private_key_id": st.secrets["private_key_id"],
            "private_key": st.secrets["private_key"], 
            "client_email": st.secrets["client_email"],
            "client_id": st.secrets["client_id"],
            "auth_uri": st.secrets["auth_uri"],
            "token_uri": st.secrets["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["client_x509_cert_url"],
            "universe_domain": st.secrets["universe_domain"]
        }
        
        scopes = ['https://www.googleapis.com/auth/drive.file']
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        service = build('drive', 'v3', credentials=creds)
        st.sidebar.success("✅ Kết nối Google Drive thành công (qua Service Account)")
        return service
    except KeyError as e:
        st.error(f"❌ Lỗi Secrets: Thiếu key '{e.args[0]}'. Kiểm tra Secrets.")
        return None
    except Exception as e:
        st.error(f"❌ Lỗi xác thực Drive: {e}")
        return None

def upload_files_to_drive_and_gemini(drive_service, gemini_client, uploaded_files):
    """Upload lên Drive, sau đó tải lên Gemini để lấy mã ID hợp lệ."""
    folder_id = None
    # 1. TÌM/TẠO FOLDER TRÊN DRIVE
    results = drive_service.files().list(q=f"name='{DRIVE_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder'",
                                         spaces='drive', fields="files(id, name)").execute()
    folders = results.get('files', [])
    if folders:
        folder_id = folders[0]['id']
    else:
        folder_metadata = {'name': DRIVE_FOLDER_NAME, 'mimeType': 'application/vnd.google-apps.folder'}
        folder = drive_service.files().create(body=folder_metadata, fields='id').execute()
        folder_id = folder.get('id')

    # 2. XỬ LÝ UPLOAD
    gemini_file_ids = []
    for file in uploaded_files:
        mime_type = file.type or 'application/pdf'
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.name)[1]) as tmp:
            tmp.write(file.read())
            tmp.flush()
            tmp_path = tmp.name
        
        # A. UPLOAD LÊN GOOGLE DRIVE (Lưu trữ vĩnh viễn)
        media = MediaFileUpload(tmp_path, mimetype=mime_type, resumable=True)
        file_metadata = {'name': file.name, 'parents': [folder_id]}
        uploaded_drive = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        st.success(f"✅ Upload Drive {file.name} thành công.")

        # B. UPLOAD LÊN GEMINI API (Lấy mã ID tạm thời)
        with open(tmp_path, 'rb') as f_content:
            uploaded_gemini = gemini_client.files.upload(file=f_content, mime_type=mime_type)

        gemini_file_ids.append(uploaded_gemini.name)
        st.success(f"✅ Upload Gemini {file.name} thành công. ID: {uploaded_gemini.name}")

        os.unlink(tmp_path) # Xóa file tạm thời
        
    return gemini_file_ids

# ------------------- Gemini Client & Chat Session -------------------
@st.cache_resource
def setup_gemini_client():
    """Khởi tạo Client duy nhất (đã cache)"""
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        return genai.Client(api_key=api_key)
    except Exception as e:
        st.error(f"❌ Lỗi: Không thể khởi tạo Client API. Kiểm tra GEMINI_API_KEY. {e}")
        return None

def get_or_create_chat_session(client, gemini_file_ids):
    """Tạo hoặc sử dụng lại phiên trò chuyện."""
    if 'chat_session' not in st.session_state or st.session_state.chat_session is None:
        try:
            list_parts = []
            for fid in gemini_file_ids:
                # Dùng mã ID HỢP LỆ của Gemini
                uri = f"https://generativelanguage.googleapis.com/v1beta/files/{fid}"
                list_parts.append(types.Part.from_uri(file_uri=uri, mime_type="application/pdf")) 
            
            list_parts.append(types.Part.from_text(text="Hãy tuân thủ 2 quy trình sư phạm trên."))

            sys_instruct = (
                "Bạn là Gia sư Hóa học THCS thông minh. "
                "Trả lời theo 2 quy trình: Lý thuyết (Cơ bản/Nâng cao) và Bài tập (Hướng dẫn/Giải chi tiết)."
            )

            chat = client.chats.create(
                model=MODEL_NAME,
                config=types.GenerateContentConfig(
                    system_instruction=sys_instruct,
                    temperature=0.3
                ),
                history=[
                    types.Content(role="user", parts=list_parts),
                    types.Content(role="model", parts=[types.Part.from_text(text="Đã hiểu 2 quy trình. Tôi đã đọc tài liệu.")])
                ]
            )
            st.session_state.chat_session = chat
            return chat
        except Exception as e:
            st.error(f"❌ Lỗi thiết lập Chat Session: {e}")
            return None
    return st.session_state.chat_session

# ------------------- STREAMLIT UI -------------------
st.set_page_config(page_title="Gia sư Hóa học", layout="wide")
st.title("👨‍🔬 Gia sư Hóa học THCS (Upload & Chat)")

# --- Mật khẩu giáo viên ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    pwd_input = st.text_input("Nhập mật khẩu giáo viên để upload tài liệu", type="password")
    if st.button("Đăng nhập"):
        if pwd_input == PASSWORD:
            st.session_state.authenticated = True
            st.session_state.LIST_FILES = [] # Reset list khi đăng nhập
            st.rerun() 
        else:
            st.error("Sai mật khẩu!")
    st.stop() # Dừng nếu chưa đăng nhập

# --- Upload file (giáo viên) ---
drive_service = get_drive_service_creds()
gemini_client = setup_gemini_client()
uploaded_files = []
gemini_file_ids = []

if drive_service and gemini_client:
    st.sidebar.markdown("#### 🔄 Quản lý File")
    uploaded_files = st.file_uploader("Upload PDF/TXT (Chỉ PDF/TXT)", accept_multiple_files=True, type=['pdf', 'txt'])
    
    if uploaded_files:
        st.session_state.uploaded_file_names = [f.name for f in uploaded_files]
        if st.button("Bắt đầu Upload & Xử lý"):
            st.session_state.LIST_FILES = upload_files_to_drive_and_gemini(drive_service, gemini_client, uploaded_files)
            st.session_state.messages = [{"role": "assistant", "content": "Tải tài liệu hoàn tất. Thầy đã sẵn sàng."}]
            st.rerun()

    if 'LIST_FILES' in st.session_state and st.session_state.LIST_FILES:
        gemini_file_ids = st.session_state.LIST_FILES
        st.sidebar.info(f"Đã xử lý {len(gemini_file_ids)} tài liệu.")

# --- Gemini client & chat session ---
chat_session = None
if gemini_client and gemini_file_ids:
    chat_session = get_or_create_chat_session(gemini_client, gemini_file_ids)

# --- Chat interface ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Chào em! Thầy đã sẵn sàng."}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Nhập câu hỏi..."):
    if not chat_session:
        st.error("Chatbot chưa được khởi tạo. Vui lòng upload tài liệu.")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Thầy đang tra cứu..."):
                try:
                    response = chat_session.send_message(prompt)
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                
                except Exception as e:
                    if "Cannot send a request, as the client has been closed." in str(e):
                        st.warning("Kết nối bị ngắt. Đang tự động tạo lại phiên trò chuyện...")
                        del st.session_state.chat_session # Xóa session cũ để tạo lại
                        st.rerun() 
                    else:
                        st.error(f"Lỗi: {e}")
