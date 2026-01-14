"use client";
import React, { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Play, Pause, SkipForward, SkipBack, Volume2, Sliders } from "lucide-react";

/**
 * Interactive_Player.jsx
 * - Web Audio API visualizer (3 modes)
 * - Vinyl rotation and pulse with bass
 * - Neumorphic volume knob (0-200)
 * - Timeline scrubber with glow progress
 * - Floating DSP FABs
 * - Live lyrics container
 *
 * Props:
 *  - chatId (int) used to call backend_bridge endpoints
 *  - currentTrack, setCurrentTrack: data pipe
 *  - dominantColors: array used for glow and CSS
 */

const fetchBridgePost = async (path, body) => {
  const res = await fetch(`/bridge${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const txt = await res.text();
    console.error("bridge error", txt);
    throw new Error(txt);
  }
  return res.json();
};

const formatTime = (s) => {
  if (!s && s !== 0) return "0:00";
  const mm = Math.floor(s / 60);
  const ss = Math.floor(s % 60).toString().padStart(2, "0");
  return `${mm}:${ss}`;
};

export default function InteractivePlayer({ chatId, currentTrack, setCurrentTrack, dominantColors }) {
  const canvasRef = useRef(null);
  const vinylRef = useRef(null);
  const audioRef = useRef(null); // optional audio element for local preview
  const analyserRef = useRef(null);
  const rafRef = useRef(null);
  const [visMode, setVisMode] = useState("circular"); // circular, bars, neon
  const [playing, setPlaying] = useState(false);
  const [volume, setVolume] = useState(100);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(currentTrack.duration || 0);
  const [lyrics, setLyrics] = useState([
    { t: 0, text: "This is the first line of the lyrics." },
    { t: 5, text: "Here comes the chorus, louder and strong." },
    { t: 12, text: "Now the verse continues, softer." },
    { t: 22, text: "Bridge section, emotion rises." },
    { t: 32, text: "Final chorus repeating the hook." },
  ]);
  const [activeLine, setActiveLine] = useState(0);

  // Setup WebAudio
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 2048;
    const gain = ctx.createGain();
    gain.gain.value = volume / 100;
    analyserRef.current = { ctx, analyser, gain };
    // connect microphone or create oscillator for demo if no stream
    // We'll use an <audio> element for safety - but the backend actually streams audio via voice calls
    const audio = new Audio();
    audio.crossOrigin = "anonymous";
    audioRef.current = audio;
    const source = ctx.createMediaElementSource(audio);
    source.connect(gain);
    gain.connect(analyser);
    analyser.connect(ctx.destination);

    // example silent audio buffer to kickstart
    audio.loop = true;
    audio.src =
      "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAAA=";
    audio.play().catch(() => {});

    const draw = () => {
      const c = canvas;
      const dpr = window.devicePixelRatio || 1;
      const w = c.clientWidth * dpr;
      const h = c.clientHeight * dpr;
      if (c.width !== w || c.height !== h) {
        c.width = w;
        c.height = h;
      }
      const g = c.getContext("2d");
      g.clearRect(0, 0, c.width, c.height);

      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      analyser.getByteFrequencyData(dataArray);

      if (visMode === "circular") {
        // circular wave
        const cx = c.width / 2;
        const cy = c.height / 2;
        const radius = Math.min(cx, cy) * 0.28;
        const bars = 120;
        g.lineWidth = 2 * dpr;
        for (let i = 0; i < bars; i++) {
          const phi = (i / bars) * Math.PI * 2;
          const idx = Math.floor((i / bars) * bufferLength);
          const v = dataArray[idx] / 255;
          const len = radius + v * radius * 1.8;
          const x1 = cx + Math.cos(phi) * radius;
          const y1 = cy + Math.sin(phi) * radius;
          const x2 = cx + Math.cos(phi) * len;
          const y2 = cy + Math.sin(phi) * len;
          g.strokeStyle = `rgba(255,255,255,${0.08 + v * 0.9})`;
          g.beginPath();
          g.moveTo(x1, y1);
          g.lineTo(x2, y2);
          g.stroke();
        }
      } else if (visMode === "bars") {
        // frequency bars
        const barWidth = (c.width / bufferLength) * 2.2;
        let x = 0;
        for (let i = 0; i < bufferLength; i += 4) {
          const v = dataArray[i] / 255;
          const hBar = v * c.height * 0.9;
          const grad = g.createLinearGradient(x, 0, x + barWidth, c.height);
          grad.addColorStop(0, "rgba(255,255,255,0.9)");
          grad.addColorStop(1, "rgba(255,255,255,0.06)");
          g.fillStyle = grad;
          g.fillRect(x, c.height - hBar, barWidth, hBar);
          x += barWidth + 1 * dpr;
        }
      } else {
        // neon line
        g.lineWidth = 3 * dpr;
        g.beginPath();
        const step = Math.floor(bufferLength / 120);
        let first = true;
        for (let i = 0; i < bufferLength; i += step) {
          const v = dataArray[i] / 255;
          const x = (i / bufferLength) * c.width;
          const y = c.height / 2 - v * c.height * 0.45;
          if (first) {
            g.moveTo(x, y);
            first = false;
          } else {
            g.lineTo(x, y);
          }
        }
        const grad = g.createLinearGradient(0, 0, c.width, 0);
        grad.addColorStop(0, dominantColors[0] || "#7c3aed");
        grad.addColorStop(1, dominantColors[1] || "#06b6d4");
        g.strokeStyle = grad;
        g.shadowBlur = 20 * dpr;
        g.shadowColor = "rgba(255,255,255,0.12)";
        g.stroke();
        g.shadowBlur = 0;
      }

      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(rafRef.current);
      try {
        audio.pause();
        const { ctx } = analyserRef.current;
        if (ctx && typeof ctx.close === "function") ctx.close();
      } catch (e) {}
    };
  }, [visMode, dominantColors, volume]);

  // Vinyl rotation + bass pulse
  useEffect(() => {
    let raf = null;
    const el = vinylRef.current;
    let angle = 0;
    const tick = () => {
      if (!el) return;
      angle = (angle + (playing ? 0.6 : 0.12)) % 360;
      el.style.transform = `rotate(${angle}deg)`;
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing]);

  // Play / Pause actions
  const togglePlay = async () => {
    if (!chatId) return;
    if (!playing) {
      await fetchBridgePost("/play", { chat_id: chatId });
      setPlaying(true);
    } else {
      await fetchBridgePost("/pause", { chat_id: chatId });
      setPlaying(false);
    }
  };

  const handleSkip = async () => {
    if (!chatId) return;
    await fetchBridgePost("/skip", { chat_id: chatId, link: "", video: false, image: false });
  };

  // Volume knob interaction (simple slider here with neumorphic look)
  const handleVolumeChange = async (v) => {
    setVolume(v);
    if (!chatId) return;
    await fetchBridgePost("/volume", { chat_id: chatId, volume: Math.min(200, Math.max(0, Math.round(v))) });
  };

  // Seek via scrubber: sends absolute seconds as to_seek and file_path empty (depends on backend)
  const handleSeek = async (posSeconds) => {
    setProgress(posSeconds);
    if (!chatId) return;
    // Backend seek signature: chat_id, file_path, to_seek, duration, mode
    await fetchBridgePost("/seek", { chat_id: chatId, file_path: "", to_seek: `${Math.floor(posSeconds)}`, duration: `${Math.floor(duration)}`, mode: "absolute" });
  };

  // DSP toggles
  const handleDSP = async (type) => {
    // For demo: call speed endpoint for some effects or toggle by sending to backend (requires backend support)
    if (!chatId) return;
    if (type === "eq") {
      // pretend call
      await fetchBridgePost("/speed", { chat_id: chatId, file_path: "", speed: 1.0, playing: [] });
    } else if (type === "bass") {
      await fetchBridgePost("/speed", { chat_id: chatId, file_path: "", speed: 1.0, playing: [] });
    } else {
      await fetchBridgePost("/speed", { chat_id: chatId, file_path: "", speed: 1.0, playing: [] });
    }
  };

  // Timeline progress simulation (in real infra you'd poll backend for position)
  useEffect(() => {
    let id = null;
    if (playing) {
      id = setInterval(() => {
        setProgress((p) => {
          const next = p + 1;
          if (next >= duration) {
            setPlaying(false);
            clearInterval(id);
            return duration;
          }
          // update active line of lyrics
          const idx = lyrics.slice().reverse().findIndex((l) => l.t <= next);
          setActiveLine(Math.max(0, lyrics.length - 1 - idx));
          return next;
        });
      }, 1000);
    } else {
      // small idle
    }
    return () => clearInterval(id);
  }, [playing, duration, lyrics]);

  // handle clicks on timeline
  const timelineRef = useRef(null);
  const onTimelineClick = (e) => {
    const rect = timelineRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const ratio = x / rect.width;
    const sec = ratio * duration;
    handleSeek(sec);
  };

  return (
    <div className="w-full flex flex-col gap-4">
      <div className="flex items-center gap-4">
        {/* Album art + vinyl */}
        <div className="w-44 h-44 rounded-2xl relative overflow-hidden backdrop-blur-[50px] bg-white/6 border border-white/10 shadow-2xl flex items-center justify-center">
          <div ref={vinylRef} className="w-36 h-36 rounded-full overflow-hidden shadow-xl" style={{ transition: "transform 0.2s linear" }}>
            <img src={currentTrack.albumArt || "/_blank_album.png"} alt="art" className="w-full h-full object-cover" />
          </div>
        </div>

        {/* Controls & info */}
        <div className="flex-1">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-lg font-semibold">{currentTrack.title || "No Track"}</div>
              <div className="text-xs opacity-60">{currentTrack.artist}</div>
            </div>

            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <Volume2 />
                <div className="text-xs opacity-60">{volume}%</div>
              </div>
              <div className="text-xs opacity-60">{formatTime(progress)} / {formatTime(duration)}</div>
            </div>
          </div>

          {/* Timeline */}
          <div className="mt-4">
            <div
              ref={timelineRef}
              onClick={onTimelineClick}
              className="w-full h-4 rounded-full relative cursor-pointer"
              style={{ backdropFilter: "blur(18px)" }}
            >
              <div
                className="absolute left-0 top-0 bottom-0 rounded-full"
                style={{
                  width: `${Math.min(100, (progress / Math.max(1, duration)) * 100)}%`,
                  background: `linear-gradient(90deg, ${dominantColors[0] || "#7c3aed"}, ${dominantColors[1] || "#06b6d4"})`,
                  boxShadow: `0 4px 18px ${dominantColors[0] || "#7c3aed"}33`,
                  height: "100%",
                }}
              />
              {/* scrubber knob */}
              <div
                style={{
                  left: `${Math.min(100, (progress / Math.max(1, duration)) * 100)}%`,
                }}
                className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-4 h-4 rounded-full bg-white/90 shadow-lg"
              />
            </div>
          </div>

          {/* Buttons */}
          <div className="mt-4 flex items-center gap-3">
            <motion.button whileTap={{ scale: 0.94 }} onClick={async () => { await fetchBridgePost("/skip", { chat_id: chatId, link: "", video: false, image: false }); }} className="p-3 rounded-full backdrop-blur-[40px] bg-white/6">
              <SkipBack />
            </motion.button>

            <motion.button whileTap={{ scale: 0.94 }} onClick={togglePlay} className="p-4 rounded-full bg-gradient-to-r from-white/20 to-white/12 shadow-xl">
              {playing ? <Pause /> : <Play />}
            </motion.button>

            <motion.button whileTap={{ scale: 0.94 }} onClick={handleSkip} className="p-3 rounded-full backdrop-blur-[40px] bg-white/6">
              <SkipForward />
            </motion.button>

            {/* Volume knob (simple slider + neumorphic) */}
            <div className="ml-4 flex items-center gap-2">
              <div className="p-3 rounded-full bg-white/5 shadow-inner">
                <input
                  type="range"
                  min="0"
                  max="200"
                  value={volume}
                  onChange={(e) => handleVolumeChange(Number(e.target.value))}
                  className="w-36"
                />
              </div>
            </div>

            {/* DSP FAB */}
            <div className="ml-auto flex items-center gap-2">
              <motion.button whileTap={{ scale: 0.92 }} onClick={() => handleDSP("eq")} className="p-3 rounded-full backdrop-blur-[40px] bg-white/6">
                <Sliders />
              </motion.button>
            </div>
          </div>
        </div>
      </div>

      {/* Visualizer canvas */}
      <div className="w-full h-56 rounded-2xl overflow-hidden">
        <canvas ref={canvasRef} className="w-full h-full block" />
        {/* Mode buttons */}
        <div className="mt-3 flex items-center gap-2">
          <button onClick={() => setVisMode("circular")} className={`py-1 px-3 rounded-lg ${visMode === "circular" ? "bg-white/10" : "bg-white/6"}`}>Circular</button>
          <button onClick={() => setVisMode("bars")} className={`py-1 px-3 rounded-lg ${visMode === "bars" ? "bg-white/10" : "bg-white/6"}`}>Bars</button>
          <button onClick={() => setVisMode("neon")} className={`py-1 px-3 rounded-lg ${visMode === "neon" ? "bg-white/10" : "bg-white/6"}`}>Neon</button>
        </div>

      </div>

      {/* Live lyrics */}
      <div className="rounded-2xl p-3 backdrop-blur-[50px] bg-white/4 border border-white/10 shadow-2xl h-44 overflow-auto">
        <div className="text-xs opacity-70 mb-2">Live Lyrics</div>
        <div className="space-y-2">
          {lyrics.map((line, idx) => (
            <div key={idx} className={`text-sm transition-all ${idx === activeLine ? "text-white scale-102 font-semibold" : "text-white/60"}`}>
              {line.text}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
