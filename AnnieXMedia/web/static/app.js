/* ============================================================
   DASHX ULTIMATE - CONTROLLER (app.js)
   Version: 6.0 Titan (Full Features)
   ============================================================ */

const API_BASE = '/api';
let updateTimer = null;
let isDraggingSlider = false; 
let currentChatId = -100123456789; // ايدي الجروب الافتراضي

document.addEventListener('DOMContentLoaded', () => {
    console.log("🚀 DashX System Initialized...");

    // 1. تشغيل التحديث اللحظي
    startPolling();

    // 2. تفعيل أزرار التحكم
    setupPlayerControls();

    // 3. تفعيل التنقل بين الصفحات
    setupNavigation();

    // 4. تفعيل تغيير الثيمات
    setupThemeSwitcher();
});

/* ============================================================
   1. نظام التحديث اللحظي (Polling System)
   ============================================================ */
function startPolling() {
    updateTimer = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/status`);
            if (!response.ok) throw new Error("Network response was not ok");
            
            const data = await response.json();
            updateInterface(data);
            
            document.getElementById('system-status').innerText = "متصل";
            document.querySelector('.dot').classList.add('live');
            document.querySelector('.dot').style.backgroundColor = "#30d158";

        } catch (error) {
            console.warn("Lost connection to Bot:", error);
            document.getElementById('system-status').innerText = "جاري الاتصال...";
            document.querySelector('.dot').classList.remove('live');
            document.querySelector('.dot').style.backgroundColor = "orange";
        }
    }, 1000);
}

function updateInterface(data) {
    document.getElementById('track-title').innerText = data.track || "لا يوجد تشغيل";
    document.getElementById('track-artist').innerText = data.artist || "Bot Idle";

    const coverImg = document.getElementById('track-art');
    if (coverImg.src !== data.cover && data.cover) {
        coverImg.src = data.cover;
    }

    if (!isDraggingSlider) {
        const slider = document.querySelector('.seek-slider');
        const timeCurr = document.querySelector('.time-current');
        const timeTotal = document.querySelector('.time-total');

        if (data.duration > 0) {
            slider.max = data.duration;
            slider.value = data.position;
            const percent = (data.position / data.duration) * 100;
            slider.style.background = `linear-gradient(to right, var(--accent) ${percent}%, #3a3a3c ${percent}%)`;
            timeCurr.innerText = formatTime(data.position);
            timeTotal.innerText = formatTime(data.duration);
        }
    }

    const stats = document.querySelectorAll('.glass-box .num');
    if(stats.length >= 3) {
        if(data.listeners) stats[0].innerText = data.listeners;
        if(data.ping) stats[1].innerText = data.ping;
    }
}

/* ============================================================
   2. التحكم في المشغل (Player Controls)
   ============================================================ */
function setupPlayerControls() {
    const playBtn = document.querySelector('.play-glow');
    playBtn.addEventListener('click', () => {
        const icon = playBtn.querySelector('i');
        if (icon.classList.contains('fa-play')) {
            sendCommand('resume');
            icon.classList.replace('fa-play', 'fa-pause');
        } else {
            sendCommand('pause');
            icon.classList.replace('fa-pause', 'fa-play');
        }
    });

    document.querySelector('.fa-forward').closest('button').addEventListener('click', () => sendCommand('skip'));

    const slider = document.querySelector('.seek-slider');
    slider.addEventListener('input', (e) => {
        isDraggingSlider = true;
        document.querySelector('.time-current').innerText = formatTime(e.target.value);
        const percent = (e.target.value / e.target.max) * 100;
        e.target.style.background = `linear-gradient(to right, var(--accent) ${percent}%, #3a3a3c ${percent}%)`;
    });

    slider.addEventListener('change', (e) => {
        isDraggingSlider = false;
        sendCommand('seek', e.target.value);
    });
}

async function sendCommand(action, value = null) {
    if (navigator.vibrate) navigator.vibrate(40);
    try {
        await fetch(`${API_BASE}/control`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: action, value: value, chat_id: currentChatId })
        });
    } catch (err) { console.error(err); }
}

/* ============================================================
   3. التنقل بين الصفحات (Navigation)
   ============================================================ */
function setupNavigation() {
    window.switchTab = function(tabName) {
        // إخفاء الكل
        document.querySelectorAll('.view').forEach(el => {
            el.classList.remove('active');
            el.style.display = 'none';
        });

        // إظهار المطلوب
        const targetView = document.getElementById(`tab-${tabName}`);
        if (targetView) {
            targetView.style.display = 'block';
            setTimeout(() => targetView.classList.add('active'), 10);
        }

        // تحديث الأزرار
        document.querySelectorAll('.dock-btn').forEach(btn => btn.classList.remove('active'));
        if(event && event.currentTarget && event.currentTarget.classList.contains('dock-btn')) {
            event.currentTarget.classList.add('active');
        }

        // 🔥 تشغيل الخزنة لو التبويب هو vault
        if (tabName === 'vault') {
            loadVaultFiles();
        }
    };
}

/* ============================================================
   4. تخصيص المظهر (Theming)
   ============================================================ */
function setupThemeSwitcher() {
    window.setTheme = function(colorName) {
        document.body.className = document.body.className.replace(/theme-\w+/g, "");
        document.body.classList.add(`theme-${colorName}`);
        document.querySelectorAll('.color-dot').forEach(dot => dot.classList.remove('selected'));
        if(event && event.target) event.target.classList.add('selected');
        localStorage.setItem('dashx_theme', colorName);
    };

    const savedTheme = localStorage.getItem('dashx_theme');
    if(savedTheme) document.body.classList.add(`theme-${savedTheme}`);
    else document.body.classList.add('theme-red');
}

/* ============================================================
   5. منطق الخزنة (VAULT SYSTEM) 🔥
   ============================================================ */
async function loadVaultFiles() {
    const container = document.querySelector('.vault-grid');
    container.innerHTML = `<div class="empty-state"><i class="fas fa-spinner fa-spin"></i><p>جاري تحميل الملفات...</p></div>`;

    try {
        const res = await fetch(`${API_BASE}/vault/list`);
        const data = await res.json();
        
        if(!data.files || data.files.length === 0) {
            container.innerHTML = `<div class="empty-state"><i class="fas fa-box-open"></i><p>الخزنة فارغة</p></div>`;
            return;
        }

        let html = '';
        data.files.forEach(file => {
            const icon = file.type === 'video' ? 'fa-video' : 'fa-music';
            const colorClass = file.type === 'video' ? 'video' : 'mp3';
            
            html += `
            <div class="vault-item glass-panel">
                <div class="file-icon ${colorClass}"><i class="fas ${icon}"></i></div>
                <div class="file-info">
                    <h4>${file.name}</h4>
                    <span>${file.size} • ${file.date}</span>
                </div>
                <div class="file-actions">
                    <button onclick="playFile('${file.name}')" class="glass-btn-icon"><i class="fas fa-play"></i></button>
                    <button onclick="deleteFile('${file.name}')" class="glass-btn-icon danger"><i class="fas fa-trash"></i></button>
                </div>
            </div>`;
        });
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = `<p style="text-align:center;color:red">فشل الاتصال بالخزنة</p>`;
    }
}

async function playFile(filename) {
    if(confirm(`تشغيل ${filename}؟`)) {
        await fetch(`${API_BASE}/vault/action`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ action: 'play', filename: filename, chat_id: currentChatId })
        });
        window.switchTab('home'); // ارجع للمشغل
    }
}

async function deleteFile(filename) {
    if(confirm(`هل أنت متأكد من حذف ${filename}؟`)) {
        const res = await fetch(`${API_BASE}/vault/action`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ action: 'delete', filename: filename })
        });
        const data = await res.json();
        if(data.success) loadVaultFiles(); // تحديث القائمة
    }
}

/* ============================================================
   6. أدوات مساعدة
   ============================================================ */
function formatTime(seconds) {
    if (!seconds || isNaN(seconds)) return "0:00";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
}
