const userId = localStorage.getItem('sc_id') || 'user_' + Math.random().toString(36).substr(2, 9);
localStorage.setItem('sc_id', userId);

const v = document.getElementById('v');
const resultBox = document.getElementById('resultBox');

// 1. [수정] 뇌(백엔드)의 주소를 인터넷 주소로 설정합니다.
const API_URL = 'https://smartcal-ai.onrender.com'; 

// 카메라 켜기
navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } }).then(s => v.srcObject = s);

async function capture() {
    const c = document.createElement('canvas');
    c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext('2d').drawImage(v, 0, 0);
    c.toBlob(upload, 'image/jpeg', 0.8);
}

async function upload(blob) {
    if(!blob) return;
    const fd = new FormData(); fd.append('file', blob);
    
    try {
        // 2. [수정] 아래 fetch 주소를 API_URL 변수를 사용하도록 바꿨습니다.
        const res = await fetch(`${API_URL}/analyze`, {
            method: 'POST', body: fd, headers: { 'user-id': userId }
        });
        const d = await res.json();
        if(d.error) return alert("무료 기간이 종료되었습니다.");

        // UI 결과 표시
        document.getElementById('name').innerText = d.food_name;
        document.getElementById('kcal').innerText = d.calories + " kcal";
        document.getElementById('carb').innerText = d.carbs + "g";
        document.getElementById('prot').innerText = d.protein + "g";
        document.getElementById('fat').innerText = d.fat + "g";
        document.getElementById('info').classList.remove('hidden');

        // 분석된 이미지 덮어쓰기
        resultBox.innerHTML = `<img src="${d.result_image}" class="w-full h-full object-cover">`;
        resultBox.classList.remove('hidden');
        v.classList.add('hidden');
    } catch(e) { 
        console.error(e);
        alert("인공지능 서버 연결에 실패했습니다. (주소를 확인해주세요!)"); 
    }
}