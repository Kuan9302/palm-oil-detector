# FastAPI main.py placeholder
from fastapi import FastAPI, File, UploadFile, Header, HTTPException
from fastapi.responses import FileResponse
from ultralytics import YOLO
from PIL import Image, UnidentifiedImageError
import shutil, uuid, os
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

app = FastAPI()
model = YOLO("best.pt")

BASE_UPLOAD_DIR = "uploaded_files"
BASE_RESULT_DIR = "results"

os.makedirs(BASE_UPLOAD_DIR, exist_ok=True)
os.makedirs(BASE_RESULT_DIR, exist_ok=True)

GOOGLE_CLIENT_ID = "814767699432-5mg8u4q7hnjlsgp2r500e8ani3cqqcqe.apps.googleusercontent.com"

def verify_google_token(token: str):
    if not token:
        raise HTTPException(status_code=401, detail="❗未提供授權 Token")
    try:
        idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
        return idinfo
    except Exception:
        raise HTTPException(status_code=401, detail="Google 登入驗證失敗，請重新登入。")

@app.post("/detect")
async def detect_objects(file: UploadFile = File(...), authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="❗未提供授權 Token")
    token = authorization.split(" ")[1]
    user_info = verify_google_token(token)
    user_email = user_info["email"].replace("@", "_").replace(".", "_")

    user_upload_dir = os.path.join(BASE_UPLOAD_DIR, user_email)
    user_result_dir = os.path.join(BASE_RESULT_DIR, user_email)
    os.makedirs(user_upload_dir, exist_ok=True)
    os.makedirs(user_result_dir, exist_ok=True)

    img_filename = f"{uuid.uuid4()}_{file.filename}"
    img_path = os.path.join(user_upload_dir, img_filename)

    try:
        Image.open(file.file).verify()
        file.file.seek(0)
    except UnidentifiedImageError:
        return {"error": "⛔ 無效的圖片檔案"}

    with open(img_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    results = model(img_path)
    result_img_path = os.path.join(user_result_dir, f"result_{img_filename}")
    results[0].save(filename=result_img_path)

    label_filename = os.path.splitext(img_filename)[0] + ".txt"
    label_path = os.path.join(user_result_dir, label_filename)
    with open(label_path, "w") as f:
        for r in results:
            for box in r.boxes:
                cls = int(box.cls.item())
                conf = box.conf.item()
                xywh = box.xywhn[0].tolist()
                line = f"{cls} {xywh[0]:.6f} {xywh[1]:.6f} {xywh[2]:.6f} {xywh[3]:.6f} {conf:.4f}\n"
                f.write(line)

    print(f"✅ [辨識完成] 用戶：{user_email}")

    return {
        "result_image": result_img_path,
        "label_file": label_path,
        "user": user_info["email"]
    }

@app.get("/results/{user}/{filename}")
async def get_result_image(user: str, filename: str, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="❗未提供授權 Token")
    token = authorization.split(" ")[1]
    verify_google_token(token)
    return FileResponse(os.path.join(BASE_RESULT_DIR, user, filename))

@app.get("/labels/{user}/{filename}")
async def get_label_file(user: str, filename: str, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="❗未提供授權 Token")
    token = authorization.split(" ")[1]
    verify_google_token(token)
    return FileResponse(os.path.join(BASE_RESULT_DIR, user, filename))