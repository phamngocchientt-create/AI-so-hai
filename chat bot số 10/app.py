import streamlit as st
from google import genai
from google.genai import types
import os

# ----------------------------------------------------
# ⚠️ BƯỚC 1: DÁN DANH SÁCH MÃ FILE TẠM THỜI VÀO ĐÂY ⚠️
# DÁN LIST_FILES TỪ SCRIPT TẢI LÊN MÁY TÍNH VÀO ĐÂY
LIST_FILES = ['1I0lmDgGJdHfnzIjdLtH4ayXmb83G5dgR', '1pwCceN2dAucZEWytejVCPi6jX5xYItfY', '1XqETTjqIRJ_rUhI_DP--HaR0w3LODTgq'] 
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
    if 'chat_session' not in st.session_state or st.session_state.chat_session is None:
        try:
            list_parts = []
            for file_name in LIST_FILES:
                # Dùng mã ID HỢP LỆ của Gemini
                uri = f"https://generativelanguage.googleapis.com/v1beta/files/{file_name}"
                # Giả định file là PDF (hoặc TXT/PDF)
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
                st.error("Lỗi File: Mã file trong LIST_FILES không hợp lệ hoặc đã hết hạn (48h). Vui lòng chạy lại script tải lên.")
            return None
    return st.session_state.chat_session

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
    st.sidebar.warning("⚠️ Mã file sẽ hết hạn sau 48 giờ. Vui lòng chạy lại script trên máy tính để làm mới dữ liệu.")
else:
    st.sidebar.error("Lỗi: Không thể khởi tạo Chatbot. Kiểm tra cấu hình.")

# Giao diện Chat
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "
