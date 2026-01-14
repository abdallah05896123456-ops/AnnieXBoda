/**
 * TITAN OS - ULTIMATE CORE ENGINE
 * Version: 3.0.0 Pro
 * Author: The Developer
 * Description: The brain behind the glass interface.
 * --------------------------------------------------
 * TABLE OF CONTENTS:
 * 1. Global Config & Utils
 * 2. API Handler (The Bridge)
 * 3. UI Controller (Animations & Toasts)
 * 4. Router (Navigation System)
 * 5. Dashboard Manager (Widgets & Charts)
 * 6. Player Engine (Audio Control)
 * 7. Vault Manager (File System)
 * 8. Terminal Emulator (Root Shell)
 * 9. Boot Sequence (Initialization)
 */

'use strict';

/* ==========================================================================
   1. GLOBAL CONFIG & UTILITIES
   ========================================================================== */
const Config = {
    apiBase: '/api',
    pollInterval: 3000, // تحديث كل 3 ثواني
    chartLimit: 20,     // عدد نقاط الرسم البياني
    isMobile: /iPhone|iPad|iPod|Android/i.test(navigator.userAgent),
    debug: true
};

const Utils = {
    // تنسيق الوقت (MM:SS)
    formatTime: (seconds) => {
        if (!seconds || isNaN(seconds)) return "0:00";
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${m}:${s < 10 ? '0' : ''}${s}`;
    },

    // تنسيق الحجم (Bytes -> MB)
    formatSize: (bytes) => {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    // اهتزاز خفيف (Haptic Feedback)
    vibrate: (pattern = 10) => {
        if (navigator.vibrate) navigator.vibrate(pattern);
    },

    // توليد لون عشوائي متناسق للخلفية
    generateColor: () => {
        const hue = Math.floor(Math.random() * 360);
        return `hsl(${hue}, 70%, 60%)`;
    },

    // تأخير زمني (Sleep)
    sleep: (ms) => new Promise(resolve => setTimeout(resolve, ms))
};

/* ==========================================================================
   2. API HANDLER (THE BRIDGE)
   ========================================================================== */
class ApiService {
    static async get(endpoint) {
        try {
            const res = await fetch(`${Config.apiBase}${endpoint}`);
            if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error(`API GET Error [${endpoint}]:`, err);
            return null;
        }
    }

    static async post(endpoint, body) {
        try {
            const res = await fetch(`${Config.apiBase}${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            return await res.json();
        } catch (err) {
            console.error(`API POST Error [${endpoint}]:`, err);
            return { success: false, error: err.message };
        }
    }

    static async upload(endpoint, formData, onProgress) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open('POST', `${Config.apiBase}${endpoint}`, true);

            // تتبع التقدم
            if (onProgress) {
                xhr.upload.onprogress = (e) => {
                    if (e.lengthComputable) {
                        const percent = (e.loaded / e.total) * 100;
                        onProgress(percent);
                    }
                };
            }

            xhr.onload = () => {
                if (xhr.status === 200) {
                    try {
                        resolve(JSON.parse(xhr.responseText));
                    } catch (e) { resolve({ success: true }); }
                } else {
                    reject(xhr.statusText);
                }
            };

            xhr.onerror = () => reject("Network Error");
            xhr.send(formData);
        });
    }
}

/* ==========================================================================
   3. UI CONTROLLER (ANIMATIONS & TOASTS)
   ========================================================================== */
class UI {
    // نظام الإشعارات العائمة
    static showToast(message, type = 'info', icon = 'info-circle') {
        const container = document.getElementById('toast-area');
        const toast = document.createElement('div');
        
        // تحديد اللون حسب النوع
        let color = 'var(--color-primary)';
        if (type === 'success') color = 'var(--color-success)';
        if (type === 'error') color = 'var(--color-danger)';

        toast.className = 'glass-toast';
        toast.style.cssText = `
            background: rgba(20, 20, 20, 0.9);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.1);
            color: #fff;
            padding: 12px 20px;
            border-radius: 50px;
            margin-bottom: 10px;
            display: flex; align-items: center; gap: 10px;
            font-size: 14px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
            animation: slideUpFade 0.4s ease forwards;
            min-width: 200px;
            justify-content: center;
        `;

        toast.innerHTML = `<i class="fas fa-${icon}" style="color: ${color}"></i> <span>${message}</span>`;
        
        container.appendChild(toast);
        Utils.vibrate([10, 30, 10]); // Haptic feedback

        // إخفاء تلقائي
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(20px)';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // تحديث الساعة في الشريط العلوي
    static initClock() {
        const el = document.getElementById('clock-display');
        setInterval(() => {
            const now = new Date();
            el.innerText = now.toLocaleTimeString('en-US', {
                hour: '2-digit', minute: '2-digit', hour12: false
            });
        }, 1000);
    }
}

/* ==========================================================================
   4. ROUTER (NAVIGATION SYSTEM)
   ========================================================================== */
class Router {
    constructor() {
        this.views = document.querySelectorAll('.view-screen');
        this.navItems = document.querySelectorAll('.dock-item');
        this.currentView = 'home';
    }

    nav(target) {
        if (this.currentView === target) return;

        // 1. تبديل الأزرار النشطة في الدوك
        this.navItems.forEach(item => {
            if (item.dataset.target === `view-${target}`) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });

        // 2. تبديل الشاشات مع أنيميشن
        this.views.forEach(view => {
            if (view.id === `view-${target}`) {
                view.classList.add('active');
            } else {
                view.classList.remove('active');
            }
        });

        this.currentView = target;
        Utils.vibrate(15); // اهتزاز عند التغيير

        // تحميل البيانات الخاصة بالشاشة
        if (target === 'vault') Vault.loadFiles();
        if (target === 'home') Dashboard.update();
    }
}

/* ==========================================================================
   5. DASHBOARD MANAGER (WIDGETS & CHARTS)
   ========================================================================== */
class DashboardController {
    constructor() {
        this.ramEl = document.getElementById('ram-usage');
        this.cpuEl = document.getElementById('cpu-usage');
        this.activeCountEl = document.getElementById('active-count');
        this.streamsListEl = document.getElementById('active-streams-container');
        this.isUpdating = false;
    }

    async update() {
        if (this.isUpdating) return;
        this.isUpdating = true;

        // 1. تحديث إحصائيات النظام
        const stats = await ApiService.get('/system/stats');
        if (stats) {
            this.ramEl.innerText = `${stats.memory.percent}%`;
            this.cpuEl.innerText = `${stats.cpu.total}%`;
            
            // تغيير اللون لو الاستهلاك عالي
            this.cpuEl.style.color = stats.cpu.total > 80 ? 'var(--color-danger)' : 'var(--text-primary)';
        }

        // 2. تحديث قائمة المشغل
        const dashData = await ApiService.get('/player/dashboard');
        if (dashData) {
            this.renderStreams(dashData.chats || []);
        }

        this.isUpdating = false;
    }

    renderStreams(chats) {
        this.activeCountEl.innerText = chats.length;

        if (chats.length === 0) {
            this.streamsListEl.innerHTML = `
                <div class="empty-placeholder">
                    <i class="fas fa-music"></i>
                    <p>النظام في وضع السكون</p>
                    <small>لا يوجد بث نشط حالياً</small>
                </div>`;
            return;
        }

        // بناء HTML للكروت (Virtual DOM Lite)
        const html = chats.map(chat => `
            <div class="glass-row-card" onclick='Player.openModal(${JSON.stringify(chat)})'>
                <div class="card-art">
                    <img src="${chat.cover}" class="art-img" onerror="this.src='https://via.placeholder.com/60'">
                    <img src="${chat.user_img}" class="user-bubble">
                </div>
                <div class="card-info">
                    <h4>${chat.track}</h4>
                    <p>${chat.title}</p>
                </div>
                <div class="card-eq">
                    <span></span><span></span><span></span>
                </div>
            </div>
        `).join('');

        // تحديث الـ DOM فقط لو المحتوى اتغير
        if (this.streamsListEl.innerHTML !== html) {
            this.streamsListEl.innerHTML = html;
        }
    }
}

/* ==========================================================================
   6. PLAYER ENGINE (AUDIO CONTROL)
   ========================================================================== */
class PlayerEngine {
    constructor() {
        this.modal = document.getElementById('player-modal');
        this.elements = {
            cover: document.getElementById('p-cover'),
            userImg: document.getElementById('p-user-img'),
            trackTitle: document.getElementById('p-track-title'),
            groupName: document.getElementById('p-group-name'),
            progress: document.getElementById('p-progress-fill'),
            currTime: document.getElementById('p-current-time'),
            totalTime: document.getElementById('p-total-time'),
            playBtn: document.getElementById('play-btn')
        };
        this.currentChat = null;
        this.isPlaying = false;
        this.progressInterval = null;
    }

    openModal(chat) {
        this.currentChat = chat;
        
        // تعبئة البيانات
        this.elements.cover.src = chat.cover;
        this.elements.userImg.src = chat.user_img;
        this.elements.trackTitle.innerText = chat.track;
        this.elements.groupName.innerText = chat.title;
        
        // تغيير لون الخلفية (Glow) بناءً على عشوائية (Simulated)
        document.querySelector('.art-glow').style.background = Utils.generateColor();

        this.updateState('playing');
        this.startProgressSim(chat.position, chat.duration);

        // فتح المودال
        this.modal.classList.add('open');
        Utils.vibrate(20);
    }

    close() {
        this.modal.classList.remove('open');
        this.stopProgressSim();
    }

    updateState(state) {
        this.isPlaying = state === 'playing';
        const icon = this.elements.playBtn.querySelector('i');
        
        if (this.isPlaying) {
            icon.className = 'fas fa-pause';
        } else {
            icon.className = 'fas fa-play';
            // تحريك النص قليلاً للإشارة
            icon.style.paddingLeft = '5px'; 
        }
    }

    toggle() {
        if (this.isPlaying) this.action('pause');
        else this.action('resume');
        
        // تغيير الحالة فورياً للـ UX (Optimistic UI)
        this.updateState(this.isPlaying ? 'paused' : 'playing');
    }

    async action(cmd) {
        if (!this.currentChat) return;

        Utils.vibrate(15); // Haptic

        // 1. إظهار إشعار فوري
        const msgs = {
            'pause': 'تم الإيقاف المؤقت',
            'resume': 'تم استئناف التشغيل',
            'skip': 'تم تخطي الأغنية',
            'stop': 'تم إنهاء التشغيل',
            'ban': 'تم حظر المجموعة',
            'focus': 'تم تفعيل وضع التركيز'
        };
        
        if (msgs[cmd]) UI.showToast(msgs[cmd], 'info', 'check');

        // 2. إرسال الطلب للسيرفر
        const res = await ApiService.post('/player/group_action', {
            action: cmd,
            chat_id: this.currentChat.chat_id
        });

        if (res.success) {
            if (cmd === 'stop' || cmd === 'ban') this.close();
            Dashboard.update(); // تحديث القائمة
        } else {
            UI.showToast(`خطأ: ${res.msg}`, 'error', 'exclamation-triangle');
        }
    }

    startProgressSim(startSec, totalSec) {
        this.stopProgressSim();
        let current = startSec;
        
        this.elements.totalTime.innerText = Utils.formatTime(totalSec);
        
        this.progressInterval = setInterval(() => {
            if (!this.isPlaying) return;
            
            current++;
            if (current > totalSec) current = 0; // Loop simulation
            
            const pct = (current / totalSec) * 100;
            this.elements.progress.style.width = `${pct}%`;
            this.elements.currTime.innerText = Utils.formatTime(current);
            
        }, 1000);
    }

    stopProgressSim() {
        if (this.progressInterval) clearInterval(this.progressInterval);
    }
}

/* ==========================================================================
   7. VAULT MANAGER (FILE SYSTEM)
   ========================================================================== */
class VaultManager {
    constructor() {
        this.container = document.getElementById('vault-files-list');
        this.statsEls = {
            disk: document.getElementById('disk-space'),
            count: document.getElementById('files-total')
        };
        this.uploadInput = document.getElementById('file-upload');
        
        // تفعيل الرفع
        this.uploadInput.addEventListener('change', (e) => this.handleUpload(e));
    }

    async loadFiles() {
        this.container.innerHTML = '<div class="loader-spinner" style="margin: 20px auto;"></div>';
        
        const [filesData, statsData] = await Promise.all([
            ApiService.get('/vault/list?sort=date'),
            ApiService.get('/vault/stats')
        ]);

        if (statsData) {
            this.statsEls.disk.innerText = statsData.used_vault;
            this.statsEls.count.innerText = `${statsData.files_count.audio + statsData.files_count.video} ملف`;
        }

        this.renderFiles(filesData ? filesData.files : []);
    }

    renderFiles(files) {
        if (!files || files.length === 0) {
            this.container.innerHTML = `
                <div class="empty-placeholder" style="grid-column: 1/-1;">
                    <i class="fas fa-folder-open"></i>
                    <p>الخزنة فارغة</p>
                </div>`;
            return;
        }

        this.container.innerHTML = files.map(f => {
            const icon = f.type === 'video' ? 'video' : 'music';
            const color = f.type === 'video' ? 'var(--color-purple)' : 'var(--color-primary)';
            return `
            <div class="file-card" onclick="Vault.fileAction('${f.name}')">
                <i class="fas fa-file-${icon} file-icon" style="color: ${color}"></i>
                <div class="file-name">${f.name}</div>
                <div style="font-size:10px; color:#666; margin-top:5px;">${f.size}</div>
            </div>`;
        }).join('');
    }

    async handleUpload(e) {
        const file = e.target.files[0];
        if (!file) return;

        UI.showToast(`جاري رفع: ${file.name}`, 'info', 'cloud-upload-alt');
        Utils.vibrate(20);

        const formData = new FormData();
        formData.append('file', file);

        try {
            // محاكاة زرار لودينج أو إظهار حالة
            const res = await ApiService.upload('/vault/upload', formData, (pct) => {
                // ممكن هنا نحدث UI بـ Progress
                console.log(`Upload: ${pct}%`);
            });

            if (res.success) {
                UI.showToast('تم الرفع بنجاح ✅', 'success');
                this.loadFiles();
            } else {
                UI.showToast('فشل الرفع ❌', 'error');
            }
        } catch (err) {
            UI.showToast(`خطأ في السيرفر`, 'error');
        }
    }

    fileAction(filename) {
        // قائمة خيارات سريعة (محاكاة Prompt)
        const action = confirm(`Manage File: ${filename}\nOK to Play, Cancel to Delete?`);
        
        if (action) {
            // Play
            ApiService.post('/vault/action', { action: 'play', filename: filename });
            UI.showToast('جاري التشغيل...', 'success', 'play');
        } else {
            // Delete (Confirm again in real app, simplified here)
            const sure = confirm("Are you sure you want to delete this file?");
            if (sure) {
                ApiService.post('/vault/action', { action: 'delete', filename: filename })
                    .then(() => {
                        UI.showToast('تم الحذف', 'warning', 'trash');
                        this.loadFiles();
                    });
            }
        }
    }
}

/* ==========================================================================
   8. TERMINAL EMULATOR (ROOT SHELL)
   ========================================================================== */
class TerminalEmulator {
    constructor() {
        this.output = document.getElementById('term-output-area');
        this.input = document.getElementById('term-cmd-input');
        this.sendBtn = document.getElementById('send-cmd-btn');
        this.history = [];
        this.histIndex = -1;

        this.input.addEventListener('keydown', (e) => this.handleKey(e));
        this.sendBtn.addEventListener('click', () => this.execute());
    }

    handleKey(e) {
        if (e.key === 'Enter') {
            this.execute();
        } else if (e.key === 'ArrowUp') {
            if (this.history.length > 0) {
                this.histIndex = Math.max(0, this.histIndex - 1);
                this.input.value = this.history[this.history.length - 1 - this.histIndex] || '';
            }
        }
    }

    async execute() {
        const cmd = this.input.value.trim();
        if (!cmd) return;

        this.history.push(cmd);
        this.histIndex = -1;
        this.log(`root@titan:~# ${cmd}`, 'sys');
        this.input.value = '';

        // Local Commands
        if (cmd === 'clear') {
            this.output.innerHTML = '';
            return;
        }
        if (cmd === 'help') {
            this.log('Available Commands:', 'success');
            this.log('- system: Show stats', 'normal');
            this.log('- play <url>: Stream URL', 'normal');
            this.log('- reboot: Restart Bot', 'error');
            return;
        }

        // Server Commands
        this.log('Processing...', 'normal');
        const res = await ApiService.post('/system/terminal', { command: cmd });
        
        // Remove "Processing..." logic could be added here
        
        if (res && res.output) {
            // تحويل الـ Newlines لـ <br> ومعالجة الألوان ببساطة
            const lines = res.output.split('\n');
            lines.forEach(line => this.log(line));
        } else {
            this.log('No output or error.', 'error');
        }

        // Scroll to bottom
        this.output.scrollTop = this.output.scrollHeight;
    }

    log(text, type = 'normal') {
        const div = document.createElement('div');
        div.className = `term-line ${type}`;
        div.innerText = text;
        this.output.appendChild(div);
        this.output.scrollTop = this.output.scrollHeight;
    }
}

/* ==========================================================================
   9. BOOT SEQUENCE (INITIALIZATION)
   ========================================================================== */

// تعريف المتغيرات العامة للوصول إليها من HTML
const App = new Router();
const Dashboard = new DashboardController();
const Player = new PlayerEngine();
const Vault = new VaultManager();
const Term = new TerminalEmulator();

window.addEventListener('DOMContentLoaded', () => {
    
    // 1. شاشة التحميل (Fake Boot)
    setTimeout(() => {
        const preloader = document.getElementById('preloader');
        preloader.classList.add('fade-out');
        setTimeout(() => preloader.remove(), 500);
        
        // تشغيل صوت بدء تشغيل خفيف (اختياري)
        // new Audio('/static/startup.mp3').play().catch(()=>{});
        
    }, 1500); // 1.5 ثانية تحميل وهمي

    // 2. تفعيل الساعة
    UI.initClock();

    // 3. بدء التحديث الدوري
    Dashboard.update(); // أول مرة فوراً
    setInterval(() => Dashboard.update(), Config.pollInterval);

    // 4. إعدادات الموبايل (منع السحب للتحديث)
    document.body.addEventListener('touchmove', function(e) {
        if (!e.target.closest('.scroll-content')) {
            e.preventDefault();
        }
    }, { passive: false });

    console.log("%c TITAN OS 3.0 LOADED ", "background: #0a84ff; color: #fff; padding: 5px; border-radius: 5px; font-weight: bold;");
});

// تعريض الكلاسات للـ Global Scope عشان `onclick` في HTML يشوفهم
window.App = App;
window.Player = Player;
window.Vault = Vault;
window.UI = UI;

/* END OF FILE */
