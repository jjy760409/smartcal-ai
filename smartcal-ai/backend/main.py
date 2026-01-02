from fastapi import FastAPI, File, UploadFile, Header
from fastapi.middleware.cors import CORSMiddleware
from ultralytics import YOLO
import cv2
import numpy as np
import base64
import uvicorn
import sqlite3
import httpx
import os
from datetime import datetime, timedelta
from typing import Optional

app = FastAPI()

# --- [1. CORS 보안 설정: 에러 해결 핵심] ---
# 브라우저가 다른 도메인(Vercel)에서 오는 요청을 거부하지 않도록 모든 문을 엽니다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 모든 웹사이트에서의 접속을 허용합니다.
    allow_credentials=True,
    allow_methods=["*"],      # GET, POST 등 모든 통신 방식을 허용합니다.
    allow_headers=["*"],      # 모든 데이터 헤더를 허용합니다.
)

# --- [2. 식약처 API 설정] ---
async def fetch_mfds_nutrition(food_name_en: str):
    # 발급받으신 식약처 API 키를 여기에 입력하세요.
    API_KEY = ad6b7fb869c545d10be67ecde89d3bc3b496d6f229d5e4ac2b5ebe56c5be2879 
    
    translation = {
        "apple": "사과", "banana": "바나나", "pizza": "피자", 
        "sandwich": "샌드위치", "hot dog": "핫도그", "broccoli": "브로콜리",
        "donut": "도넛", "orange": "오렌지", "cake": "케이크"
    }
    ko_name = translation.get(food_name_en, None)
    if not ko_name: return None

    # 식약처 식품영양성분 DB 호출 (I2790 서비스)
    url = f"http://openapi.foodsafetykorea.go.kr/api/{API_KEY}/I2790/json/1/1/DESC_KOR={ko_name}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=5.0)
            data = response.json()
            if "I2790" in data and int(data["I2790"]["total_count"]) > 0:
                item = data["I2790"]["row"][0]
                return {
                    "name": item.get("DESC_KOR", ko_name),
                    "kcal": float(item.get("NUTR_CONT1", 0) or 0),
                    "carbs": float(item.get("NUTR_CONT2", 0) or 0),
                    "protein": float(item.get("NUTR_CONT3", 0) or 0),
                    "fat": float(item.get("NUTR_CONT4", 0) or 0)
                }
        except Exception as e:
            print(f"API 호출 오류: {e}")
    return None

# --- [3. 데이터베이스 설정] ---
def init_db():
    conn = sqlite3.connect("smartcal_pro.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, first_access TEXT)")
    conn.commit()
    conn.close()

init_db()
model = YOLO('yolov8n.pt') # AI 모델 로드

# --- [4. 결제 성공 처리 API] ---
@app.post("/pay-success")
async def pay_success(user_id: str):
    conn = sqlite3.connect("smartcal_pro.db")
    c = conn.cursor()
    # 결제한 사용자는 만료 시간을 100년 뒤로 설정하여 무제한 사용 가능하게 합니다.
    unlimited_date = (datetime.now() + timedelta(days=36500)).isoformat()
    c.execute("INSERT OR REPLACE INTO users (user_id, first_access) VALUES (?, ?)", (user_id, unlimited_date))
    conn.commit()
    conn.close()
    return {"status": "premium_activated"}

# --- [5. 음식 분석 API] ---
@app.post("/analyze")
async def analyze_food(file: UploadFile = File(...), user_id: Optional[str] = Header(None)):
    conn = sqlite3.connect("smartcal_pro.db")
    c = conn.cursor()
    c.execute("SELECT first_access FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    
    now = datetime.now()
    if not row:
        c.execute("INSERT INTO users VALUES (?, ?)", (user_id, now.isoformat()))
        conn.commit()
    elif now > datetime.fromisoformat(row[0]) + timedelta(hours=24):
        conn.close()
        return {"error": "expired"}

    # 이미지 분석
    contents = await file.read()
    img = cv2.imdecode(np.frombuffer(contents, np.uint8), cv2.IMREAD_COLOR)
    results = model(img)
    
    response = {"food_name": "인식 실패", "calories": 0, "carbs": 0, "protein": 0, "fat": 0}
    
    for r in results:
        for box in r.boxes:
            label = model.names[int(box.cls[0])]
            real_data = await fetch_mfds_nutrition(label)
            if real_data:
                response.update(real_data)
                # 이미지에 결과 박스 그리기
                b = box.xyxy[0].cpu().numpy().astype(int)
                cv2.rectangle(img, (b[0], b[1]), (b[2], b[3]), (0, 255, 0), 4)
                break

    conn.close()
    _, encoded_img = cv2.imencode('.jpg', img)
    response["result_image"] = f"data:image/jpeg;base64,{base64.b64encode(encoded_img).decode('utf-8')}"
    return response

# --- [6. 서버 실행 설정: Render 전용] ---
if __name__ == "__main__":
    # Render 환경에서 지정해주는 포트를 자동으로 사용합니다.
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
