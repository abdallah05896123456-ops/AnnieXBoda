/* ============================================================
   DASHX ULTIMATE - CONTROLLER (app.js)
   Version: 5.0 Titan
   ============================================================ */

const API_BASE = '/api';
let updateTimer = null;
let isDraggingSlider = false; // عشان الشريط ميرجعش لورا واحنا بنسحبه
let currentChatId = -100123456789; // ايدي الجروب الافتراضي (هيتم تحديثه تلقائياً)

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
    // تحديث البيانات كل ثانية
    updateTimer = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/status`);
            if (!response.ok) throw new Error("Network response was not ok");
            
            const data = await response.json();
            updateInterface(data);
            
            // تحديث حالة الاتصال
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
    // أ. تحديث النصوص
    document.getElementById('track-title').innerText = data.track || "لا يوجد تشغيل";
    document.getElementById('track-artist').innerText = data.artist || "Bot Idle";

    // ب. تحديث الغلاف (فقط لو اتغير عشان ميرمش)
    const coverImg = document.getElementById('track-art');
    if (coverImg.src !== data.cover && data.cover) {
        coverImg.src = data.cover;
    }

    // ج. تحديث شريط التقدم (لو المستخدم مش بيسحبه حالياً)
    if (!isDraggingSlider) {
        const slider = document.querySelector('.seek-slider');
        const timeCurr = document.querySelector('.time-current');
        const timeTotal = document.querySelector('.time-total');

        if (data.duration > 0) {
            slider.max = data.duration;
            slider.value = data.position;
            
            // نسبة مئوية للخلفية الملونة للشريط
            const percent = (data.position / data.duration) * 100;
            slider.style.background = `linear-gradient(to right, var(--accent) ${percent}%, #3a3a3c ${percent}%)`;

            timeCurr.innerText = formatTime(data.position);
            timeTotal.innerText = formatTime(data.duration);
        }
    }

    // د. تحديث الإحصائيات السريعة
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
    // زر التشغيل/الإيقاف
    const playBtn = document.querySelector('.play-glow');
    playBtn.addEventListener('click', () => {
        const icon = playBtn.querySelector('i');
        // تبديل الأيقونة مؤقتاً لحد ما السيرفر يرد
        if (icon.classList.contains('fa-play')) {
            sendCommand('resume');
            icon.classList.replace('fa-play', 'fa-pause');
        } else {
            sendCommand('pause');
            icon.classList.replace('fa-pause', 'fa-play');
        }
    });

    // زر التخطي (Forward)
    document.querySelector('.fa-forward').closest('button').addEventListener('click', () => {
        sendCommand('skip');
    });

    // شريط التقدم (Seek Bar)
    const slider = document.querySelector('.seek-slider');
    slider.addEventListener('input', (e) => {
        isDraggingSlider = true;
        // تحديث الوقت شكلياً أثناء السحب
        document.querySelector('.time-current').innerText = formatTime(e.target.value);
        // تحديث لون الشريط
        const percent = (e.target.value / e.target.max) * 100;
        e.target.style.background = `linear-gradient(to right, var(--accent) ${percent}%, #3a3a3c ${percent}%)`;
    });

    slider.addEventListener('change', (e) => {
        isDraggingSlider = false;
        sendCommand('seek', e.target.value); // ميزة لسه هنضيفها في البايثون
    });
}

async function sendCommand(action, value = null) {
    // اهتزاز خفيف للموبايل (Haptic Feedback)
    if (navigator.vibrate) navigator.vibrate(40);

    try {
        await fetch(`${API_BASE}/control`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: action,
                value: value,
                chat_id: currentChatId
            })
        });
        console.log(`Command Sent: ${action}`);
    } catch (err) {
        console.error("Command Failed:", err);
    }
}

/* ============================================================
   3. التنقل بين الصفحات (Navigation)
   ============================================================ */
function setupNavigation() {
    // دالة متاحة للـ HTML (window scope)
    window.switchTab = function(tabName) {
        // 1. إخفاء كل الشاشات
        document.querySelectorAll('.view').forEach(el => {
            el.classList.remove('active');
            el.style.display = 'none'; // تأكيد الإخفاء
        });

        // 2. إظهار الشاشة المطلوبة
        const targetView = document.getElementById(`tab-${tabName}`);
        if (targetView) {
            targetView.style.display = 'block';
            // تأخير بسيط عشان الانيميشن يشتغل
            setTimeout(() => targetView.classList.add('active'), 10);
        }

        // 3. تحديث أزرار القائمة السفلية
        document.querySelectorAll('.dock-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        // تلوين الزر النشط (بناءً على الترتيب أو الاسم)
        // (هنا بنعتمد على الـ onclick في الـ HTML اللي بيحدد الزر)
        const clickedBtn = event.currentTarget;
        if(clickedBtn && clickedBtn.classList.contains('dock-btn')) {
            clickedBtn.classList.add('active');
        }
    };
}

/* ============================================================
   4. تخصيص المظهر (Theming)
   ============================================================ */
function setupThemeSwitcher() {
    window.setTheme = function(colorName) {
        // إزالة أي كلاس ثيم قديم
        document.body.className = document.body.className.replace(/theme-\w+/g, "");
        
        // إضافة الثيم الجديد
        document.body.classList.add(`theme-${colorName}`);
        
        // تحديث الـ Selected Dot
        document.querySelectorAll('.color-dot').forEach(dot => dot.classList.remove('selected'));
        // (الـ event.target هو الدائرة اللي داس عليها المستخدم)
        if(event && event.target) {
            event.target.classList.add('selected');
        }

        // حفظ الاختيار (Local Storage) عشان لما يعمل ريفريش يفضل موجود
        localStorage.setItem('dashx_theme', colorName);
    };

    // استرجاع الثيم المحفوظ عند الفتح
    const savedTheme = localStorage.getItem('dashx_theme');
    if(savedTheme) {
        document.body.classList.add(`theme-${savedTheme}`);
    } else {
        document.body.classList.add('theme-red'); // الافتراضي
    }
}

/* ============================================================
   5. أدوات مساعدة (Utilities)
   ============================================================ */
function formatTime(seconds) {
    if (!seconds || isNaN(seconds)) return "0:00";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
}
