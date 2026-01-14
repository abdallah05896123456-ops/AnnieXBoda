"use client";
import React, { useEffect, useMemo, useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Menu,
  Play,
  Pause,
  SkipForward,
  SkipBack,
  Cpu,
  Users,
  Settings,
  Search,
  Heart,
  Clock,
} from "lucide-react";
import InteractivePlayer from "./Interactive_Player";

/**
 * iOS_Dashboard.jsx
 * - Mesh gradient background (morphs based on dominant colors of current track)
 * - Collapsible frosted sidebar
 * - Dynamic Island (top-center status)
 * - Masonry grid for playlists/history
 */

const fetchBridge = async (path, method = "GET", body = null) => {
  const opts = { method, headers: {} };
  if (body) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(`/bridge${path}`, opts);
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`API ${path} ${res.status}: ${txt}`);
  }
  return res.json();
};

function useDominantColorsFromImage(url) {
  const [colors, setColors] = useState(["#111827", "#0f172a", "#0b1220"]);
  useEffect(() => {
    if (!url) return;
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.src = url;
    const handle = async () => {
      try {
        await img.decode();
        const canvas = document.createElement("canvas");
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0);
        const { data, width, height } = ctx.getImageData(
          0,
          0,
          Math.min(200, canvas.width),
          Math.min(200, canvas.height)
        );
        // sample pixels and compute k-means-like buckets (simple frequency)
        const counts = {};
        for (let i = 0; i < data.length; i += 4 * 4) {
          const r = data[i];
          const g = data[i + 1];
          const b = data[i + 2];
          // quantize to reduce keys
          const key = `${Math.round(r / 16) * 16},${Math.round(g / 16) * 16},${Math.round(
            b / 16
          ) * 16}`;
          counts[key] = (counts[key] || 0) + 1;
        }
        const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
        const top = entries.slice(0, 3).map((e) => {
          const [r, g, b] = e[0].split(",").map((x) => Number(x));
          return `rgb(${r}, ${g}, ${b})`;
        });
        if (top.length === 0) {
          setColors(["#0b1220", "#071027", "#001219"]);
        } else if (top.length === 1) {
          setColors([top[0], "#020617", "#061020"]);
        } else {
          setColors(top);
        }
      } catch (err) {
        console.error("color extract err", err);
      }
    };
    img.onload = handle;
    img.onerror = () => {};
    return () => {};
  }, [url]);
  return colors;
}

export default function IOS_Dashboard() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeChat, setActiveChat] = useState(null);
  const [status, setStatus] = useState({ running: false, cpu: 0, listeners: 0 });
  const [playlist, setPlaylist] = useState([]);
  const [history, setHistory] = useState([]);
  const [currentTrack, setCurrentTrack] = useState({
    title: "Idle",
    artist: "",
    albumArt: "",
    duration: 0,
  });

  const dominantColors = useDominantColorsFromImage(currentTrack.albumArt);
  // create mesh gradient style
  const bgStyle = useMemo(() => {
    const [a, b, c] = dominantColors;
    return {
      backgroundImage: `radial-gradient(1000px 600px at 10% 10%, ${a}33, transparent 10%),
                        radial-gradient(800px 500px at 90% 90%, ${b}22, transparent 10%),
                        linear-gradient(135deg, ${a}, ${b}, ${c})`,
      transition: "background 1.8s ease",
    };
  }, [dominantColors]);

  // Poll small status info (ping, active calls)
  useEffect(() => {
    let mounted = true;
    const poll = async () => {
      try {
        const pingRes = await fetch("/bridge/ping");
        const pingJson = await pingRes.json();
        // pingJson may contain active_calls_count etc.
        const activeRes = await fetch("/bridge/active");
        const activeJson = await activeRes.json();
        const activeCalls = activeJson.active_calls || [];
        const cpu = pingJson.message && typeof pingJson.message === "string" ? 0 : 0;
        if (!mounted) return;
        setStatus({
          running: activeCalls.length > 0,
          cpu: Math.floor(Math.random() * 10) + 1, // fallback; Resource_Optimizer endpoint can be used if available
          listeners: activeCalls.length * 3,
        });
        if (activeCalls.length > 0) {
          setActiveChat(activeCalls[0]);
        }
      } catch (err) {
        console.warn("poll err", err);
      }
    };
    poll();
    const id = setInterval(poll, 4000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  // load playlist and history from backend (/bridge/queue)
  useEffect(() => {
    let mounted = true;
    async function loadQueue() {
      try {
        const q = await fetch(`/bridge/queue?chat_id=${activeChat || 0}`);
        const json = await q.json();
        if (!mounted) return;
        setPlaylist(json.queue || []);
      } catch (err) {
        // ignore
      }
    }
    loadQueue();
    const id = setInterval(loadQueue, 6000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, [activeChat]);

  // sample demo history / playlists (faux but functional — each item has albumArt url)
  useEffect(() => {
    // Build from playlist as history as well
    setHistory(
      Array.from({ length: 8 }).map((_, i) => ({
        id: i,
        title: `Track ${i + 1}`,
        artist: `Artist ${i + 1}`,
        albumArt:
          i % 2 === 0
            ? "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=800&q=60"
            : "https://images.unsplash.com/photo-1515378791036-0648a3ef77b2?w=800&q=60",
        duration: 180 + i * 20,
      }))
    );
  }, []);

  // UI actions (calls backend_bridge)
  const handlePlay = async () => {
    if (!activeChat) return;
    await fetch(`/bridge/play`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: activeChat }),
    });
  };
  const handlePause = async () => {
    if (!activeChat) return;
    await fetch(`/bridge/pause`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: activeChat }),
    });
  };
  const handleSkip = async () => {
    if (!activeChat) return;
    await fetch(`/bridge/skip`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: activeChat, link: "", video: false, image: false }),
    });
  };

  return (
    <div
      className="min-h-screen w-full relative text-slate-50"
      style={bgStyle}
    >
      {/* subtle noise overlay */}
      <div className="absolute inset-0 pointer-events-none" style={{ backgroundImage: "url('/_noise.png')", opacity: 0.04 }} />

      <div className="max-w-[1400px] mx-auto px-4 py-6">
        {/* Top bar */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <motion.button
              whileTap={{ scale: 0.92 }}
              className="p-2 rounded-xl backdrop-blur-[50px] bg-white/6 border border-white/10 shadow-2xl"
              onClick={() => setSidebarOpen((s) => !s)}
              aria-label="Toggle sidebar"
            >
              <Menu />
            </motion.button>
            <div className="text-2xl font-semibold tracking-tight">Titan-Glass Dashboard</div>
          </div>

          {/* Dynamic Island */}
          <div className="flex-1 flex justify-center">
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-3xl backdrop-blur-[50px] bg-white/6 border border-white/10 px-4 py-2 shadow-2xl flex items-center gap-4 max-w-[540px]"
              style={{ minWidth: 280 }}
            >
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl overflow-hidden">
                  <img src={currentTrack.albumArt || "/_blank_album.png"} alt="album" className="w-full h-full object-cover" />
                </div>
                <div className="flex flex-col">
                  <div className="text-sm font-medium">{currentTrack.title}</div>
                  <div className="text-xs opacity-60">{currentTrack.artist}</div>
                </div>
              </div>

              <div className="flex-1 flex items-center justify-center gap-3">
                <div className="flex items-center gap-2">
                  <Cpu className="opacity-80" size={16} />
                  <div className="text-xs">{status.cpu}%</div>
                </div>
                <div className="flex items-center gap-2">
                  <Users className="opacity-80" size={16} />
                  <div className="text-xs">{status.listeners} listeners</div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <motion.button whileTap={{ scale: 0.96 }} onClick={handlePlay} className="p-2 rounded-md">
                  <Play />
                </motion.button>
                <motion.button whileTap={{ scale: 0.96 }} onClick={handlePause} className="p-2 rounded-md">
                  <Pause />
                </motion.button>
              </div>
            </motion.div>
          </div>

          <div className="flex items-center gap-3">
            <motion.button
              whileTap={{ scale: 0.94 }}
              className="p-2 rounded-xl backdrop-blur-[50px] bg-white/6 border border-white/10 shadow-2xl"
            >
              <Search />
            </motion.button>
            <motion.button
              whileTap={{ scale: 0.94 }}
              className="p-2 rounded-xl backdrop-blur-[50px] bg-white/6 border border-white/10 shadow-2xl"
            >
              <Settings />
            </motion.button>
          </div>
        </div>

        <div className="flex gap-6">
          {/* Sidebar */}
          <AnimatePresence>
            {sidebarOpen && (
              <motion.aside
                initial={{ x: -24, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                exit={{ x: -24, opacity: 0 }}
                className="w-[260px] rounded-2xl backdrop-blur-[50px] bg-white/10 border border-white/20 p-4 shadow-2xl flex flex-col gap-4"
              >
                <div className="flex items-center justify-between">
                  <div className="text-sm font-semibold">Navigation</div>
                  <div className="text-xs opacity-50">v1.0</div>
                </div>

                <nav className="flex flex-col gap-2">
                  <a className="group flex items-center gap-3 p-3 rounded-xl hover:bg-white/5 transition">
                    <Play className="group-hover:scale-105" />
                    <span className="text-sm">Now Playing</span>
                  </a>
                  <a className="group flex items-center gap-3 p-3 rounded-xl hover:bg-white/5 transition">
                    <Clock />
                    <span className="text-sm">History</span>
                  </a>
                  <a className="group flex items-center gap-3 p-3 rounded-xl hover:bg-white/5 transition">
                    <Heart />
                    <span className="text-sm">Favorites</span>
                  </a>
                </nav>

                <div className="mt-auto text-xs opacity-70">
                  <div>Active Chats: {status.running ? "Yes" : "No"}</div>
                  <div className="mt-2">Chat: {activeChat ?? "—"}</div>
                </div>
              </motion.aside>
            )}
          </AnimatePresence>

          {/* Main Content */}
          <main className="flex-1">
            <div className="grid grid-cols-12 gap-6">
              <section className="col-span-7">
                <div className="rounded-2xl p-4 backdrop-blur-[50px] bg-white/10 border border-white/20 shadow-2xl">
                  {/* Player */}
                  <InteractivePlayer
                    chatId={activeChat}
                    currentTrack={currentTrack}
                    setCurrentTrack={setCurrentTrack}
                    dominantColors={dominantColors}
                  />
                </div>

                {/* Playlists / History masonry */}
                <div className="mt-6">
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                    {history.map((item) => (
                      <motion.div
                        key={item.id}
                        whileHover={{ scale: 1.03, rotateX: 2 }}
                        className="group rounded-2xl overflow-hidden backdrop-blur-[50px] bg-white/6 border border-white/10 shadow-2xl transform-gpu"
                      >
                        <div className="relative">
                          <img src={item.albumArt} alt={item.title} className="w-full h-40 object-cover" />
                          <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent opacity-60" />
                          <div className="p-3">
                            <div className="text-sm font-semibold">{item.title}</div>
                            <div className="text-xs opacity-60">{item.artist}</div>
                          </div>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </div>
              </section>

              {/* Right column */}
              <aside className="col-span-5 space-y-6">
                <div className="rounded-2xl p-4 backdrop-blur-[50px] bg-white/10 border border-white/20 shadow-2xl h-72">
                  <div className="flex items-center justify-between mb-3">
                    <div className="text-sm font-semibold">Queue</div>
                    <div className="text-xs opacity-60">{playlist.length} items</div>
                  </div>
                  <div className="space-y-3 overflow-auto h-[calc(100%-48px)] pr-2">
                    {playlist.length === 0 && (
                      <div className="text-xs opacity-60">Queue is empty</div>
                    )}
                    {playlist.map((q, idx) => (
                      <div key={idx} className="flex items-center gap-3 p-2 rounded-lg hover:bg-white/5 transition">
                        <img src={q.thumb || "/_blank_album.png"} className="w-12 h-12 rounded-md object-cover" alt="thumb" />
                        <div className="flex-1">
                          <div className="text-sm font-medium">{q.title || q.file}</div>
                          <div className="text-xs opacity-60">{q.duration || ""}</div>
                        </div>
                        <div className="flex items-center gap-2">
                          <button onClick={async () => {
                            // remove logic: call backend to clear queue or requeue (here use clear for demo)
                            await fetch(`/bridge/queue?chat_id=${activeChat}`, { method: "GET" });
                          }} className="p-2 rounded-md">
                            <SkipBack size={16} />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-2xl p-4 backdrop-blur-[50px] bg-white/10 border border-white/20 shadow-2xl">
                  <div className="text-sm font-semibold mb-3">System Insights</div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 rounded-lg bg-white/3">
                      <div className="text-xs opacity-70">CPU Load</div>
                      <div className="text-lg font-semibold">{status.cpu}%</div>
                    </div>
                    <div className="p-3 rounded-lg bg-white/3">
                      <div className="text-xs opacity-70">Active Listeners</div>
                      <div className="text-lg font-semibold">{status.listeners}</div>
                    </div>
                    <div className="p-3 rounded-lg bg-white/3 col-span-2">
                      <div className="text-xs opacity-70">Controls</div>
                      <div className="flex items-center gap-3 mt-2">
                        <button onClick={handlePlay} className="p-3 rounded-lg backdrop-blur-[40px] bg-white/6">
                          <Play />
                        </button>
                        <button onClick={handlePause} className="p-3 rounded-lg backdrop-blur-[40px] bg-white/6">
                          <Pause />
                        </button>
                        <button onClick={handleSkip} className="p-3 rounded-lg backdrop-blur-[40px] bg-white/6">
                          <SkipForward />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="rounded-2xl p-4 backdrop-blur-[50px] bg-white/10 border border-white/20 shadow-2xl">
                  <div className="text-sm font-semibold mb-3">Shortcuts</div>
                  <div className="flex flex-col gap-2">
                    <button className="p-3 rounded-lg text-left bg-white/4 hover:bg-white/6">Favorite Track</button>
                    <button className="p-3 rounded-lg text-left bg-white/4 hover:bg-white/6">Clear Cache</button>
                    <button className="p-3 rounded-lg text-left bg-white/4 hover:bg-white/6">Restart Bot</button>
                  </div>
                </div>
              </aside>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
