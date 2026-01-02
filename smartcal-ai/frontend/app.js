const userId = localStorage.getItem('sc_id') || 'user_' + Math.random().toString(36).substr(2, 9);
localStorage.setItem('sc_id', userId);

const v = document.getElementById('v');
const resultBox = document.getElementById('resultBox');

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
        const res = await fetch('http://localhost:8000/analyze', {
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
    } catch(e) { alert("서버 연결 확인!"); }
}