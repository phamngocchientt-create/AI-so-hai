import streamlit as st
import os
import tempfile
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google import genai
from google.genai import types

# ------------------- CẤU HÌNH -------------------
MODEL_NAME = "gemini-2.0-flash"
SCOPES = ['https://www.googleapis.com/auth/drive.file']
CREDENTIALS_FILE = "credentials.json"
DRIVE_FOLDER_NAME = "ChatbotDocs"
PASSWORD = "giaovu123"  # Mật khẩu giáo viên

# ------------------- Google Drive -------------------
@st.cache_resource
def get_drive_service():
    creds = None
    token_path = "token.json"
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token:
            token.write(creds.to_json())
    service = build('drive', 'v3', credentials=creds)
    return service

def upload_files_to_drive(service, uploaded_files):
    folder_id = None
    results = service.files().list(q=f"name='{DRIVE_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder'",
                                   spaces='drive', fields="files(id, name)").execute()
    folders = results.get('files', [])
    if folders:
        folder_id = folders[0]['id']
    else:
        folder_metadata = {'name': DRIVE_FOLDER_NAME, 'mimeType': 'application/vnd.google-apps.folder'}
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        folder_id = folder.get('id')

    file_ids = []
    for file in uploaded_files:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.name)[1]) as tmp:
            tmp.write(file.read())
            tmp.flush()
            media = MediaFileUpload(tmp.name, resumable=True)
            file_metadata = {'name': file.name, 'parents': [folder_id]}
            uploaded = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            file_ids.append(uploaded['id'])
            st.success(f"✅ Upload {file.name} thành công, fileId: {uploaded['id']}")
    return file_ids

# ------------------- Gemini Client -------------------
@st.cache_resource
def setup_gemini_client():
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        return genai.Client(api_key=api_key)
    except Exception as e:
        st.error(f"❌ Lỗi khởi tạo Gemini: {e}")
        return None

def get_or_create_chat_session(client, file_ids):
    if 'chat_session' not in st.session_state or st.session_state.chat_session is None:
        list_parts = []
        for fid in file_ids:
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
            st.success("Đăng nhập thành công. Bạn có thể upload tài liệu.")
        else:
            st.error("Sai mật khẩu!")

# --- Upload file (giáo viên) ---
uploaded_files = []
if st.session_state.authenticated:
    uploaded_files = st.file_uploader("Upload PDF/TXT", accept_multiple_files=True)

drive_service = get_drive_service()
file_ids = []
if uploaded_files and drive_service:
    file_ids = upload_files_to_drive(drive_service, uploaded_files)
    st.session_state.LIST_FILES = file_ids
elif 'LIST_FILES' in st.session_state:
    file_ids = st.session_state.LIST_FILES

# --- Gemini client & chat session ---
gemini_client = setup_gemini_client()
chat_session = None
if gemini_client and file_ids:
    chat_session = get_or_create_chat_session(gemini_client, file_ids)

# --- Chat interface ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Chào em! Thầy đã sẵn sàng."}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Nhập câu hỏi..."):
    if not chat_session:
        st.error("Chatbot chưa được khởi tạo.")
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
                except Exception as
