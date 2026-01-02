from fastapi import FastAPI, File, UploadFile, Header
from fastapi.middleware.cors import CORSMiddleware
from ultralytics import YOLO
import cv2
import numpy as np
import base64
import uvicorn
import sqlite3
import httpx
from datetime import datetime, timedelta
from typing import Optional

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- [식약처 API 실시간 연동 로직] ---
async def fetch_mfds_nutrition(food_name_en: str):
    # 1. 여기에 발급받은 공공데이터 API 인증키(Service Key)를 넣으세요
    API_KEY = ad6b7fb869c545d10be67ecde89d3bc3b496d6f229d5e4ac2b5ebe56c5be2879 
    
    # 2. YOLO 인식 결과(영어)를 식약처 검색어(한국어)로 매칭
    translation = {
        "apple": "사과", "banana": "바나나", "pizza": "피자", 
        "sandwich": "샌드위치", "hot dog": "핫도그", "broccoli": "브로콜리",
        "donut": "도넛", "orange": "오렌지", "cake": "케이크"
    }
    ko_name = translation.get(food_name_en, None)
    if not ko_name: return None

    # 3. 식약처 식품영양성분 DB 호출 (서비스코드: I2790 기준)
    # 15127578 데이터도 I2790 규격을 따르는 경우가 많습니다.
    url = f"http://openapi.foodsafetykorea.go.kr/api/{API_KEY}/I2790/json/1/1/DESC_KOR={ko_name}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=5.0)
            data = response.json()
            
            if "I2790" in data and int(data["I2790"]["total_count"]) > 0:
                item = data["I2790"]["row"][0]
                return {
                    "name": item.get("DESC_KOR", ko_name),
                    "kcal": float(item.get("NUTR_CONT1", 0) or 0), # 에너지
                    "carbs": float(item.get("NUTR_CONT2", 0) or 0), # 탄수화물
                    "protein": float(item.get("NUTR_CONT3", 0) or 0), # 단백질
                    "fat": float(item.get("NUTR_CONT4", 0) or 0) # 지방
                }
        except Exception as e:
            print(f"식약처 API 연동 실패: {e}")
    return None

# --- [DB 및 모델 설정] ---
def init_db():
    conn = sqlite3.connect("smartcal_pro.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, first_access TEXT)")
    conn.commit()
    conn.close()

init_db()
model = YOLO('yolov8n.pt')

@app.post("/analyze")
async def analyze_food(file: UploadFile = File(...), user_id: Optional[str] = Header(None)):
    # 24시간 체험 제한 로직 (기존과 동일)
    conn = sqlite3.connect("smartcal_pro.db")
    c = conn.cursor()
    c.execute("SELECT first_access FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO users VALUES (?, ?)", (user_id, datetime.now().isoformat())); conn.commit()
    elif datetime.now() > datetime.fromisoformat(row[0]) + timedelta(hours=24):
        conn.close(); return {"error": "expired"}

    # AI 분석
    contents = await file.read()
    img = cv2.imdecode(np.frombuffer(contents, np.uint8), cv2.IMREAD_COLOR)
    results = model(img)
    
    response = {"food_name": "알 수 없음", "calories": 0, "carbs": 0, "protein": 0, "fat": 0}
    
    for r in results:
        for box in r.boxes:
            label = model.names[int(box.cls[0])]
            real_data = await fetch_mfds_nutrition(label) # 실시간 데이터 호출
            if real_data:
                response.update(real_data)
                b = box.xyxy[0].cpu().numpy().astype(int)
                cv2.rectangle(img, (b[0], b[1]), (b[2], b[3]), (0, 255, 0), 4)
                break

    conn.close()
    _, encoded_img = cv2.imencode('.jpg', img)
    response["result_image"] = f"data:image/jpeg;base64,{base64.b64encode(encoded_img).decode('utf-8')}"
    return response

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)