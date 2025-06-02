# Streamlit app.py placeholder
import streamlit as st
import requests
from google_auth_oauthlib.flow import Flow
from PIL import Image
import io

st.set_page_config(page_title="🌴 油棕樹辨識系統")
st.title("🌴 油棕樹辨識系統")

#BACKEND_URL = "http://localhost:8000"
BACKEND_URL = "https://palm-oil-detector.onrender.com"
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/drive.readonly"
]

# 使用 secrets 安全載入 OAuth 設定
client_config = {
    "web": {
        "client_id": st.secrets["google_oauth"]["client_id"],
        "client_secret": st.secrets["google_oauth"]["client_secret"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [st.secrets["google_oauth"]["redirect_uri"]]
    }
}

#flow = Flow.from_client_config(client_config, scopes=SCOPES)
flow = Flow.from_client_config(..., redirect_uri=st.secrets["google_oauth"]["redirect_uri"])
flow.redirect_uri = st.secrets["google_oauth"]["redirect_uri"]

# Google OAuth 登入流程
if "token" not in st.session_state:
    query_params = st.query_params
    if "code" in query_params:
        try:
            flow.fetch_token(code=query_params["code"][0])
            creds = flow.credentials
            st.session_state["token"] = creds.token

            headers = {"Authorization": f"Bearer {creds.token}"}
            userinfo_resp = requests.get("https://www.googleapis.com/oauth2/v3/userinfo", headers=headers)
            st.session_state["user"] = userinfo_resp.json()

            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.error(f"⚠️ 登入失敗：{e}")
            st.query_params.clear()
    else:
        auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
        st.markdown(f"[👉 使用 Google 登入]({auth_url})")

# 登入後操作
elif "user" in st.session_state:
    st.success(f"✅ 已登入：{st.session_state['user']['email']}")
    if st.button("🚪 登出"):
        st.session_state.clear()
        st.rerun()

    token = st.session_state["token"]
    user_email = st.session_state["user"]["email"]

    headers = {"Authorization": f"Bearer {token}"}

    # 驗證 token 狀態
    test_resp = requests.get("https://www.googleapis.com/oauth2/v3/userinfo", headers=headers)
    if test_resp.status_code == 401:
        st.warning("⚠️ 權限失效，請重新登入")
        st.session_state.clear()
        st.rerun()

    st.header("☁️ 雲端圖片選擇")
    params = {"q": "mimeType contains 'image/'", "fields": "files(id, name, mimeType, thumbnailLink)", "pageSize": 10}
    drive_resp = requests.get("https://www.googleapis.com/drive/v3/files", headers=headers, params=params)

    if drive_resp.status_code == 200:
        files = drive_resp.json().get("files", [])
        for file in files:
            with st.expander(file["name"]):
                st.image(file.get("thumbnailLink", ""))
                if st.button(f"🔍 辨識 {file['name']}", key=file['id']):
                    download_url = f"https://www.googleapis.com/drive/v3/files/{file['id']}?alt=media"
                    image_resp = requests.get(download_url, headers=headers)
                    if image_resp.status_code == 200:
                        mime_type = file['mimeType']
                        files_data = {"file": (file['name'], image_resp.content, mime_type)}
                        detect = requests.post(f"{BACKEND_URL}/detect", files=files_data, headers={"Authorization": f"Bearer {token}"})
                        if detect.status_code == 200:
                            data = detect.json()
                            user_id = user_email.replace("@", "_").replace(".", "_")
                            result_img_url = f"{BACKEND_URL}/results/{user_id}/{data['result_image'].split('/')[-1]}"
                            label_url = f"{BACKEND_URL}/labels/{user_id}/{data['label_file'].split('/')[-1]}"
                            st.image(Image.open(io.BytesIO(requests.get(result_img_url).content)), caption="辨識結果", use_container_width=True)
                            st.download_button("📄 下載標籤", data=requests.get(label_url).content, file_name="labels.txt")
                        else:
                            st.error("辨識失敗")
                    else:
                        st.error("無法下載圖片")

    st.header("📤 上傳圖片辨識")
    uploaded_file = st.file_uploader("請上傳圖片", type=["jpg", "jpeg", "png"])
    if uploaded_file:
        st.image(uploaded_file)
        if st.button("開始辨識"):
            files_data = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            detect = requests.post(f"{BACKEND_URL}/detect", files=files_data, headers={"Authorization": f"Bearer {token}"})
            if detect.status_code == 200:
                data = detect.json()
                user_id = user_email.replace("@", "_").replace(".", "_")
                result_img_url = f"{BACKEND_URL}/results/{user_id}/{data['result_image'].split('/')[-1]}"
                label_url = f"{BACKEND_URL}/labels/{user_id}/{data['label_file'].split('/')[-1]}"
                st.image(Image.open(io.BytesIO(requests.get(result_img_url).content)), caption="辨識結果", use_container_width=True)
                st.download_button("📄 下載標籤", data=requests.get(label_url).content, file_name="labels.txt")
            else:
                st.error("辨識失敗或未授權")
