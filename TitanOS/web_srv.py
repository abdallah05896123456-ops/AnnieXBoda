<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Titan OS | Ultimate Command Center</title>
    
    <!-- =========================================
         1. المكتبات الخارجية (Dependencies)
         ========================================= -->
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;800&family=Rajdhani:wght@500;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://vjs.zencdn.net/7.20.3/video-js.css" rel="stylesheet" />

    <style>
        /* =========================================
           2. المتغيرات والأساسيات (Core Styling)
           ========================================= */
        :root {
            --bg-deep: #050505;
            --glass-bg: rgba(20, 25, 30, 0.75);
            --glass-border: rgba(255, 255, 255, 0.08);
            --neon-blue: #0A84FF;
            --neon-purple: #BF5AF2;
            --danger: #FF453A;
            --success: #32D74B;
            --warning: #FFD60A;
            --text-main: #ffffff;
            --text-muted: #86868b;
            --card-radius: 24px;
            --shadow-glow: 0 0 30px rgba(10, 132, 255, 0.15);
        }

        * { box-sizing: border-box; margin: 0; padding: 0; outline: none; -webkit-tap-highlight-color: transparent; font-family: 'Cairo', sans-serif; }
        
        body {
            background-color: var(--bg-deep);
            color: var(--text-main);
            height: 100vh; overflow: hidden;
            background-image: radial-gradient(circle at 90% 10%, #1a1b2e 0%, #000 60%);
            display: flex; flex-direction: column;
            user-select: none;
        }

        /* --- خلفية النجوم --- */
        #starfield { position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: -1; pointer-events: none; }
        .star { position: absolute; background: #fff; border-radius: 50%; opacity: 0; animation: twinkle var(--dur) infinite ease-in-out; }
        @keyframes twinkle { 0%,100% { opacity:0; transform:scale(0.5); } 50% { opacity:0.7; transform:scale(1); } }

        /* =========================================
           3. الهيكل والتقسيم (Layout & Grid)
           ========================================= */
        .layout-wrapper {
            display: flex; height: 100%; width: 100%; padding: 15px; gap: 15px;
            transition: all 0.4s cubic-bezier(0.25, 1, 0.5, 1);
        }

        /* القائمة الجانبية */
        .sidebar {
            width: 280px; background: var(--glass-bg); backdrop-filter: blur(40px);
            border: 1px solid var(--glass-border); border-radius: var(--card-radius);
            padding: 25px; display: flex; flex-direction: column; gap: 20px;
            transform: translateX(0); transition: 0.3s; z-index: 100;
        }

        /* المحتوى الرئيسي */
        .main-stage {
            flex: 1; overflow-y: auto; padding-bottom: 110px; /* مساحة للدوك */
            display: flex; flex-direction: column; gap: 20px;
        }

        /* الكروت */
        .card {
            background: rgba(30, 30, 35, 0.6); backdrop-filter: blur(20px);
            border: 1px solid var(--glass-border); border-radius: var(--card-radius);
            padding: 20px; position: relative; overflow: hidden;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            transition: transform 0.2s, border-color 0.2s;
        }
        .card:hover { border-color: rgba(255,255,255,0.2); }

        /* =========================================
           4. مشغل الميديا المتقدم (The Super Player)
           ========================================= */
        .player-wrapper {
            height: 420px; padding: 0; display: flex; flex-direction: column;
            border: 1px solid rgba(255,255,255,0.05);
        }

        /* منطقة العرض (فيديو/صورة) */
        .viewport {
            flex: 1; position: relative; overflow: hidden; border-radius: var(--card-radius) var(--card-radius) 0 0;
            background: #000; cursor: pointer;
        }
        
        .viewport img#album-art {
            width: 100%; height: 100%; object-fit: cover; opacity: 0.8;
            transition: 0.5s;
        }
        
        /* طبقة التحكم المخفية (Overlay) */
        .overlay-controls {
            position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.7); backdrop-filter: blur(8px);
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            opacity: 0; transition: 0.3s;
        }
        .viewport:hover .overlay-controls { opacity: 1; }
        .viewport:hover img#album-art { transform: scale(1.1); opacity: 0.4; }

        /* أزرار الأوفرلاي */
        .overlay-btn {
            background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2);
            color: #fff; padding: 10px 20px; border-radius: 30px; margin: 5px;
            cursor: pointer; font-size: 0.9rem; display: flex; align-items: center; gap: 8px;
            transition: 0.2s;
        }
        .overlay-btn:hover { background: var(--neon-blue); border-color: var(--neon-blue); }

        /* شريط التحكم السفلي */
        .control-bar {
            height: 100px; background: rgba(15, 15, 20, 0.95);
            padding: 0 25px; display: flex; align-items: center; justify-content: space-between;
            border-top: 1px solid rgba(255,255,255,0.1);
        }

        /* معلومات الأغنية */
        .track-info {
            display: flex; flex-direction: column; max-width: 40%;
        }
        .track-title { font-weight: 700; font-size: 1.1rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .track-artist { font-size: 0.85rem; color: var(--text-muted); }

        /* أزرار التشغيل */
        .playback-ctrls { display: flex; align-items: center; gap: 20px; }
        .btn-round {
            width: 45px; height: 45px; border-radius: 50%; border: none;
            background: rgba(255,255,255,0.1); color: #fff; font-size: 1.1rem;
            cursor: pointer; display: flex; align-items: center; justify-content: center;
            transition: 0.2s;
        }
        .btn-round:hover { background: rgba(255,255,255,0.2); }
        .btn-play {
            width: 60px; height: 60px; background: var(--neon-blue); font-size: 1.6rem;
            box-shadow: 0 0 20px rgba(10, 132, 255, 0.4);
        }
        .btn-play:hover { transform: scale(1.05); background: #0070e0; }

        /* =========================================
           5. الدوك السفلي (Dock Navigation)
           ========================================= */
        .dock-container {
            position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
            background: rgba(10, 10, 15, 0.85); backdrop-filter: blur(35px);
            border: 1px solid rgba(255,255,255,0.1); padding: 12px 30px;
            border-radius: 40px; display: flex; gap: 30px; z-index: 999;
            box-shadow: 0 20px 50px rgba(0,0,0,0.6); width: auto;
        }

        .dock-app {
            display: flex; flex-direction: column; align-items: center; gap: 6px;
            color: var(--text-muted); cursor: pointer; transition: 0.3s; position: relative;
        }
        .dock-app i { font-size: 1.6rem; transition: 0.3s; padding: 10px; border-radius: 12px; }
        .dock-app:hover i { background: rgba(255,255,255,0.1); color: #fff; transform: translateY(-10px); }
        .dock-app.active i { color: var(--neon-blue); }
        .dock-app.active::after {
            content: ''; position: absolute; bottom: -5px; width: 5px; height: 5px;
            background: var(--neon-blue); border-radius: 50%;
        }

        /* =========================================
           6. زرار تحويل النظام (Desktop Toggle)
           ========================================= */
        .system-switch {
            position: absolute; top: 15px; left: 15px; z-index: 1000;
            background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.2);
            padding: 8px 16px; border-radius: 20px; color: #fff; font-size: 0.85rem;
            cursor: pointer; display: flex; align-items: center; gap: 8px; backdrop-filter: blur(10px);
        }
        .system-switch:hover { background: var(--neon-blue); border-color: var(--neon-blue); }

        /* =========================================
           7. المودال والنوافذ (Modals)
           ========================================= */
        .modal-wrap {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.85); z-index: 2000; display: none;
            align-items: center; justify-content: center; backdrop-filter: blur(15px);
            opacity: 0; transition: opacity 0.3s;
        }
        .modal-wrap.active { opacity: 1; }
        
        .modal-body {
            background: #121214; width: 90%; max-width: 400px; padding: 30px;
            border-radius: 30px; border: 1px solid rgba(255,255,255,0.1);
            text-align: center; transform: scale(0.9); transition: 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }
        .modal-wrap.active .modal-body { transform: scale(1); }

        .glow-input {
            width: 100%; padding: 15px; background: #000; border: 1px solid #333;
            color: #fff; border-radius: 15px; text-align: center; margin-bottom: 20px; font-size: 1.1rem;
        }
        .glow-input:focus { border-color: var(--neon-blue); box-shadow: 0 0 15px rgba(10,132,255,0.3); }

        @media (max-width: 768px) {
            .sidebar { position: fixed; left: -300px; height: 100%; box-shadow: 10px 0 30px #000; }
            .sidebar.show { left: 0; }
            .layout-wrapper { display: block; padding: 10px; }
            .player-wrapper { height: 380px; }
            .main-stage { overflow: visible; padding-bottom: 100px; }
            body { overflow-y: auto; }
        }

        body.desktop-view .sidebar { position: relative; left: 0; display: flex; }
        body.desktop-view .layout-wrapper { display: flex; }
        body.desktop-view .dock-container { padding: 15px 50px; }
        
        .visualizer-bars {
            display: flex; gap: 3px; align-items: flex-end; height: 20px; opacity: 0.7;
        }
        .v-bar { width: 3px; background: var(--neon-blue); animation: jump 0.5s infinite alternate; }
        @keyframes jump { 0% { height: 5px; } 100% { height: 20px; } }
    </style>
</head>
<body>

    <div id="starfield"></div>

    <div class="system-switch" onclick="toggleDesktopMode()">
        <i class="fa-solid fa-display"></i> <span id="view-label">Desktop View</span>
    </div>

    <div class="layout-wrapper">
        
        <aside class="sidebar">
            <div style="text-align:center; padding-bottom:20px; border-bottom:1px solid rgba(255,255,255,0.1);">
                <h2 style="font-family:'Rajdhani'; letter-spacing:2px; font-weight:700; color:var(--text-main);">TITAN <span style="color:var(--neon-blue)">OS</span></h2>
                <small style="color:var(--text-muted);">Ultimate Control Center v9.5</small>
            </div>

            <div class="card" style="display:flex; align-items:center; gap:15px; padding:15px;">
                <img src="https://ui-avatars.com/api/?name=Admin&background=0A84FF&color=fff&size=128" style="width:50px; height:50px; border-radius:15px;">
                <div>
                    <h5 style="margin:0;">System Admin</h5>
                    <div style="font-size:0.75rem; color:var(--success); display:flex; align-items:center; gap:5px;">
                        <div style="width:6px; height:6px; background:var(--success); border-radius:50%;"></div> Online
                    </div>
                </div>
            </div>

            <div style="margin-top:auto;">
                <h6 style="color:var(--text-muted); margin-bottom:10px;">CONNECTED TARGET</h6>
                <div class="card" style="border:1px solid var(--neon-blue); background:rgba(10,132,255,0.05); text-align:center;">
                    <i class="fa-solid fa-satellite-dish" style="color:var(--neon-blue); font-size:1.5rem; margin-bottom:5px;"></i>
                    <h5 id="sidebar-chat-name" style="margin:0; font-family:'Rajdhani';">No Signal</h5>
                    <small id="sidebar-chat-id" style="font-family:monospace; color:var(--text-muted);">---</small>
                </div>
            </div>
        </aside>

        <main class="main-stage">
            
            <div class="card player-wrapper">
                
                <div class="viewport" id="media-viewport">
                    <!-- مشغل الفيديو -->
                    <video id="titan-video-player" class="video-js vjs-theme-city" style="display:none; width:100%; height:100%;" controls preload="auto">
                        <source src="" type="video/mp4" />
                    </video>

                    <!-- صورة الألبوم -->
                    <img id="album-art" src="https://images.unsplash.com/photo-1614613535308-eb5fbd3d2c17?q=80&w=1000" alt="Cover Art">
                    
                    <div class="overlay-controls">
                        <h3 id="overlay-title" style="margin-bottom:20px; text-shadow:0 2px 10px #000;">Waiting for Stream...</h3>
                        
                        <div style="display:flex; flex-wrap:wrap; justify-content:center;">
                            <button class="overlay-btn" onclick="openModal('quality-modal')">
                                <i class="fa-solid fa-sliders"></i> الجودة
                            </button>
                            <button class="overlay-btn" onclick="toggleVideoDisplay()">
                                <i class="fa-solid fa-video"></i> فيديو/صوت
                            </button>
                            <button class="overlay-btn" style="border-color:var(--danger); color:var(--danger);" onclick="sendCommand('stop')">
                                <i class="fa-solid fa-power-off"></i> إيقاف
                            </button>
                        </div>
                    </div>
                </div>

                <div class="control-bar">
                    <div class="track-info">
                        <div class="track-title" id="bar-title">System Idle</div>
                        <div class="track-artist" id="bar-artist">Select a group to start</div>
                        
                        <div class="visualizer-bars" id="visualizer" style="display:none; margin-top:5px;">
                            <div class="v-bar" style="animation-duration:0.4s"></div>
                            <div class="v-bar" style="animation-duration:0.6s"></div>
                            <div class="v-bar" style="animation-duration:0.3s"></div>
                            <div class="v-bar" style="animation-duration:0.5s"></div>
                        </div>
                    </div>

                    <div class="playback-ctrls">
                        <button class="btn-round" onclick="sendCommand('seek_back')"><i class="fa-solid fa-rotate-left"></i></button>
                        <button class="btn-round btn-play" id="play-pause-btn" onclick="togglePlayback()">
                            <i class="fa-solid fa-play"></i>
                        </button>
                        <button class="btn-round" onclick="sendCommand('skip')"><i class="fa-solid fa-forward-step"></i></button>
                    </div>
                </div>
            </div>

            <!-- ب) أدوات النظام (تم إضافة زر الجروبات هنا) -->
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap:15px;">
                <!-- حالة السيرفر -->
                <div class="card" style="text-align:center;">
                    <i class="fa-solid fa-server" style="font-size:1.8rem; color:var(--neon-purple); margin-bottom:10px;"></i>
                    <h4>Server</h4>
                    <small style="color:var(--success);">Stable 99%</small>
                </div>
                <!-- زر الجروبات الجديد -->
                <div class="card" style="text-align:center; cursor:pointer;" onclick="openModal('connection-modal'); scanForCalls();">
                    <i class="fa-solid fa-users" style="font-size:1.8rem; color:var(--text-main); margin-bottom:10px;"></i>
                    <h4>Groups</h4>
                    <small>Active List</small>
                </div>
                <!-- وضع التيربو -->
                <div class="card" style="text-align:center; cursor:pointer;" onclick="activateTurbo()">
                    <i class="fa-solid fa-bolt" style="font-size:1.8rem; color:var(--warning); margin-bottom:10px;"></i>
                    <h4>Turbo</h4>
                    <small id="turbo-text">Deactivated</small>
                </div>
                <!-- تنظيف الكاش -->
                <div class="card" style="text-align:center; cursor:pointer;" onclick="cleanCache()">
                    <i class="fa-solid fa-broom" style="font-size:1.8rem; color:var(--neon-blue); margin-bottom:10px;"></i>
                    <h4>Cleaner</h4>
                    <small id="clean-text">Free RAM</small>
                </div>
            </div>

        </main>
    </div>

    <!-- 5. الدوك السفلي -->
    <div class="dock-container">
        <div class="dock-app active" onclick="openModal('connection-modal')">
            <i class="fa-solid fa-tower-broadcast"></i>
            <span>اتصال</span>
        </div>
        <div class="dock-app" onclick="toggleVideoDisplay()">
            <i class="fa-solid fa-tv"></i>
            <span>شاشة</span>
        </div>
        <div class="dock-app" onclick="window.open('/logs', '_blank')">
            <i class="fa-solid fa-file-code"></i>
            <span>سجلات</span>
        </div>
        <div class="dock-app danger" onclick="confirmLogout()">
            <i class="fa-solid fa-right-from-bracket" style="color:var(--danger);"></i>
            <span>خروج</span>
        </div>
    </div>

    <!-- 6. النوافذ المنبثقة -->
    <div class="modal-wrap" id="connection-modal">
        <div class="modal-body">
            <i class="fa-solid fa-link" style="font-size:3rem; color:var(--neon-blue); margin-bottom:20px;"></i>
            <h3>Active Groups</h3>
            <p style="color:var(--text-muted); margin-bottom:20px;">Select a group to control</p>
            
            <input type="text" id="manual-id-input" class="glow-input" placeholder="-100xxxxxxx (Chat ID)">
            
            <button onclick="scanForCalls()" style="width:100%; padding:15px; background:var(--neon-blue); border:none; border-radius:15px; color:#fff; font-weight:bold; margin-bottom:10px; cursor:pointer;">
                <i class="fa-solid fa-radar"></i> Refresh List
            </button>
            <button onclick="manualConnect()" style="width:100%; padding:15px; background:rgba(255,255,255,0.1); border:none; border-radius:15px; color:#fff; cursor:pointer;">
                Manual Connect
            </button>

            <div id="scan-results-list" style="margin-top:20px; text-align:right; max-height:150px; overflow-y:auto; border-top:1px solid rgba(255,255,255,0.1); padding-top:10px;"></div>
            
            <div style="margin-top:20px; cursor:pointer; color:#666;" onclick="closeModal('connection-modal')">Close</div>
        </div>
    </div>

    <div class="modal-wrap" id="quality-modal">
        <div class="modal-body">
            <h3><i class="fa-solid fa-sliders"></i> دقة العرض</h3>
            <div style="display:flex; flex-direction:column; gap:10px; margin-top:20px;">
                <button onclick="alert('تم التغيير لـ Low Data')" style="padding:15px; background:#222; border:1px solid #333; color:#fff; border-radius:10px;">Audio Only (Low)</button>
                <button onclick="alert('تم التغيير لـ HD Ready')" style="padding:15px; background:rgba(10,132,255,0.2); border:1px solid var(--neon-blue); color:#fff; border-radius:10px;">HD Video (Standard)</button>
                <button onclick="alert('جاري محاولة 4K...')" style="padding:15px; background:#222; border:1px solid #333; color:#fff; border-radius:10px;">Ultra 4K (High)</button>
            </div>
            <div style="margin-top:20px; cursor:pointer; color:#666;" onclick="closeModal('quality-modal')">إغلاق</div>
        </div>
    </div>

    <!-- 7. الكود البرمجي (The Brain) -->
    <script src="https://vjs.zencdn.net/7.20.3/video.min.js"></script>
    <script>
        let activeChatId = localStorage.getItem('titan_active_id') || null;
        let isPlaying = false;
        let syncInterval = null;

        // الخلفية
        const starContainer = document.getElementById('starfield');
        for (let i = 0; i < 100; i++) {
            const s = document.createElement('div');
            s.className = 'star';
            s.style.left = Math.random() * 100 + '%';
            s.style.top = Math.random() * 100 + '%';
            const size = Math.random() * 3 + 1;
            s.style.width = size + 'px'; s.style.height = size + 'px';
            s.style.setProperty('--dur', (Math.random()*2+1) + 's');
            starContainer.appendChild(s);
        }

        // وضع الديسكتوب
        function toggleDesktopMode() {
            document.body.classList.toggle('desktop-view');
            const label = document.getElementById('view-label');
            const meta = document.querySelector('meta[name="viewport"]');
            
            if (document.body.classList.contains('desktop-view')) {
                label.innerText = "Mobile View";
                meta.setAttribute('content', 'width=1200');
            } else {
                label.innerText = "Desktop View";
                meta.setAttribute('content', 'width=device-width, initial-scale=1.0');
            }
        }

        // المودال
        function openModal(id) { 
            const m = document.getElementById(id);
            m.style.display = 'flex';
            setTimeout(() => m.classList.add('active'), 10);
        }
        function closeModal(id) {
            const m = document.getElementById(id);
            m.classList.remove('active');
            setTimeout(() => m.style.display = 'none', 300);
        }

        // الاتصال
        function setConnectedTarget(id, name) {
            activeChatId = id;
            localStorage.setItem('titan_active_id', id);
            localStorage.setItem('titan_active_name', name);
            document.getElementById('sidebar-chat-name').innerText = name;
            document.getElementById('sidebar-chat-name').style.color = "var(--success)";
            document.getElementById('sidebar-chat-id').innerText = id;
            document.getElementById('bar-title').innerText = name;
            document.getElementById('overlay-title').innerText = name;
            closeModal('connection-modal');
            startSync();
        }

        async function scanForCalls() {
            const list = document.getElementById('scan-results-list');
            list.innerHTML = "<div style='color:var(--neon-blue)'>Scanning Frequencies... <i class='fa-solid fa-satellite-dish fa-spin'></i></div>";
            try {
                const res = await fetch('/api/active_calls');
                const data = await res.json();
                list.innerHTML = "";
                if (data.chats && data.chats.length > 0) {
                    data.chats.forEach(chat => {
                        list.innerHTML += `
                        <div onclick="setConnectedTarget('${chat.id}', '${chat.name}')" 
                             style="padding:10px; border-bottom:1px solid #333; cursor:pointer; display:flex; justify-content:space-between;">
                             <span><i class="fa-solid fa-music"></i> ${chat.name}</span>
                             <small style="color:#666">${chat.id}</small>
                        </div>`;
                    });
                } else {
                    list.innerHTML = "<small>No Active Calls Found.</small>";
                }
            } catch (e) {
                list.innerHTML = "<small style='color:var(--danger)'>Connection Error.</small>";
            }
        }

        function manualConnect() {
            const val = document.getElementById('manual-id-input').value;
            if(val) setConnectedTarget(val, "Manual Target");
        }

        // المزامنة ومعلومات التراك
        function startSync() {
            if (syncInterval) clearInterval(syncInterval);
            document.getElementById('visualizer').style.display = 'flex';

            syncInterval = setInterval(async () => {
                if(!activeChatId) return;
                try {
                    const res = await fetch(`/api/track_info/${activeChatId}`);
                    if(res.ok) {
                        const info = await res.json();
                        if(info.cover) document.getElementById('album-art').src = info.cover;
                        if(info.title) {
                            document.getElementById('bar-title').innerText = info.title;
                            document.getElementById('overlay-title').innerText = info.title;
                        }
                        if(info.artist) document.getElementById('bar-artist').innerText = info.artist;
                    }
                } catch(e) { }
            }, 3000);
        }

        // التحكم
        async function sendCommand(cmd) {
            if(!activeChatId) return openModal('connection-modal');
            try {
                await fetch(`/api/${cmd}/${activeChatId}`, {method: 'POST'});
                const card = document.querySelector('.player-wrapper');
                card.style.borderColor = "var(--neon-blue)";
                setTimeout(() => card.style.borderColor = "rgba(255,255,255,0.05)", 300);
            } catch(e) { console.error(e); }
        }

        function togglePlayback() {
            const btn = document.getElementById('play-pause-btn');
            if(isPlaying) {
                sendCommand('pause');
                btn.innerHTML = '<i class="fa-solid fa-play"></i>';
                document.getElementById('visualizer').style.opacity = '0.2';
                isPlaying = false;
            } else {
                sendCommand('resume');
                btn.innerHTML = '<i class="fa-solid fa-pause"></i>';
                document.getElementById('visualizer').style.opacity = '1';
                isPlaying = true;
            }
        }

        // تبديل الفيديو
        function toggleVideoDisplay() {
            const vid = document.getElementById('titan-video-player');
            const img = document.getElementById('album-art');
            if (vid.style.display === 'none') {
                vid.style.display = 'block';
                img.style.display = 'none';
                // محاولة تشغيل الفيديو
                vid.play().catch(e => console.log("Waiting for user interaction or stream"));
            } else {
                vid.style.display = 'none';
                img.style.display = 'block';
                vid.pause();
            }
        }

        // تيربو (فعلي)
        async function activateTurbo() {
            const txt = document.getElementById('turbo-text');
            txt.innerText = "Processing...";
            try {
                const res = await fetch('/api/system/turbo', {method: 'POST'});
                const data = await res.json();
                if(data.ok) {
                    txt.innerText = "RAM CLEANED!";
                    txt.style.color = "var(--success)";
                } else {
                    txt.innerText = "Error";
                    txt.style.color = "var(--danger)";
                }
            } catch(e) {
                txt.innerText = "Offline";
            }
            setTimeout(() => {
                txt.innerText = "Deactivated";
                txt.style.color = "var(--text-muted)";
            }, 3000);
        }

        // تنظيف الكاش (فعلي)
        async function cleanCache() {
            const txt = document.getElementById('clean-text');
            txt.innerText = "Cleaning...";
            try {
                const res = await fetch('/api/system/cleancache', {method: 'POST'});
                const data = await res.json();
                if(data.ok) {
                    txt.innerText = "CACHE CLEARED!";
                    txt.style.color = "var(--success)";
                }
            } catch(e) {}
            setTimeout(() => {
                txt.innerText = "Free RAM";
                txt.style.color = "var(--text-muted)";
            }, 3000);
        }

        function confirmLogout() {
            if(confirm("Disconnect System & Logout?")) window.location.href = "/logout";
        }

        if(localStorage.getItem('titan_active_id')) {
            setConnectedTarget(localStorage.getItem('titan_active_id'), localStorage.getItem('titan_active_name'));
        }

    </script>
</body>
</html>
