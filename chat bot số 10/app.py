import streamlit as st
from google import genai
from google.genai import types
import os

# ----------------------------------------------------
# ⚠️ BƯỚC 1: DÁN DANH SÁCH MÃ FILE TẠM THỜI VÀO ĐÂY ⚠️
# CHUỖI NÀY BẮT ĐẦU BẰNG ['files/abc-123', 'files/xyz-456']
LIST_FILES = ['DÁN_MÃ_FILE_TẠM_THỜI_VÀO_ĐÂY'] 
# ----------------------------------------------------

# --- CẤU HÌNH KHÁC ---
MODEL_NAME = "gemini-2.0-flash"
# --- KẾT THÚC CẤU HÌNH ---


@st.cache_resource
def setup_chat_client():
    """Khởi tạo Client duy nhất (đã cache)"""
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        return genai.Client(api_key=api_key)
    except Exception as e:
        st.error(f"❌ Lỗi: Không thể khởi tạo Client API. Kiểm tra GEMINI_API_KEY. {e}")
        return None

def get_or_create_chat_session(client):
    """Tạo hoặc sử dụng lại phiên trò chuyện (Sử dụng state để ổn định)."""
    # Không tạo lại session nếu đã có
    if 'chat_session' in st.session_state and st.session_state.chat_session is not None:
        return st.session_state.chat_session
    
    # Tạo session mới
    try:
        list_parts = []
        for file_name in LIST_FILES:
            # Dùng mã ID HỢP LỆ của Gemini
            uri = f"https://generativelanguage.googleapis.com/v1beta/files/{file_name}"
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
        if "Invalid or unsupported file uri" in str(e) or "files/" in str(e):
            st.error("Lỗi File: Mã file trong LIST_FILES không hợp lệ hoặc đã hết hạn (48h).")
        return None
    
# ------------------- STREAMLIT UI -------------------
st.set_page_config(page_title="Gia sư Hóa học", layout="wide")
st.title("👨‍🔬 Gia sư Hóa học THCS (Nguồn: Tải lên Trực tiếp)")

# Khởi tạo Client và Session
client = setup_chat_client()
chat_session = None

if client:
    chat_session = get_or_create_chat_session(client)
    
if chat_session:
    st.sidebar.success("✅ Đã kết nối Gemini (Dữ liệu ổn định).")
    st.sidebar.info(f"🤖 Model: {MODEL_NAME}")
    
    if len(LIST_FILES) > 0 and LIST_FILES[0] != 'DÁN_MÃ_FILE_TẠM_THỜI_VÀO_ĐÂY':
        st.sidebar.info(f"Thấy {len(LIST_FILES)} tài liệu.")
    st.sidebar.warning("⚠️ Mã file sẽ hết hạn sau 48 giờ. Vui lòng chạy lại script để làm mới dữ liệu.")
else:
    st.sidebar.error("Lỗi: Không thể khởi tạo Chatbot. Kiểm tra cấu hình.")

# Giao diện Chat
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Chào em! Thầy đã sẵn sàng."}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Nhập câu hỏi..."):
    if not chat_session:
        st.error("Chatbot chưa được khởi tạo. Kiểm tra cấu hình.")
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
                        # Tự động khắc phục lỗi "client closed"
                        st.warning("Kết nối bị ngắt. Đang tự động tạo lại phiên trò chuyện...")
                        del st.session_state.chat_session # Xóa session cũ
                        st.rerun() 
                    else:
                        st.error(f"Lỗi: {e}")
