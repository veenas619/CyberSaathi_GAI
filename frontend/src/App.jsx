import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity, AlertCircle, AlertTriangle, ArrowDownRight, ArrowRight, ArrowUpRight,
  AudioLines, Bell, BookOpen, Check, CheckCircle2, ChevronDown, ChevronRight,
  CircleHelp, Clock3, FileClock, FileText, Headphones, Home, LayoutDashboard,
  LifeBuoy, LoaderCircle, LogOut, Menu, MessageCircle, Mic, Plus, Search,
  Settings, Shield, ShieldAlert, ShieldCheck, Sparkles, Upload, UserRound,
  Volume2, X
} from "lucide-react";
import { apiFetch, LIVE_WS } from "./lib/api";

const EXAMPLES = [
  ["Suspicious bank call", "Someone called claiming ₹20,000 was transferred to my account by mistake and asked me to return it."],
  ["Money deducted", "I shared an OTP with someone claiming to be from my bank. Now ₹20,000 has been deducted."],
  ["Suspicious APK", "I received an APK file on WhatsApp saying it is a courier tracking app. They asked me to install it."]
];

const navItems = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "analyze", label: "New analysis", icon: Sparkles },
  { id: "incidents", label: "My incidents", icon: FileClock },
  { id: "safety", label: "Safety centre", icon: ShieldCheck }
];

function cn(...parts) { return parts.filter(Boolean).join(" "); }
function initials(user) {
  const name = user?.user_metadata?.full_name || user?.user_metadata?.name || user?.email || "User";
  return name.split(/[\s@.]+/).filter(Boolean).slice(0, 2).map(x => x[0].toUpperCase()).join("");
}
function displayName(user) {
  return user?.user_metadata?.full_name || user?.user_metadata?.name || user?.email?.split("@")[0] || "there";
}
function timeAgo(value) {
  if (!value) return "Just now";
  const mins = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 60000));
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} hr ago`;
  return `${Math.floor(hours / 24)} days ago`;
}

function Brand({ compact = false }) {
  return <div className="flex items-center gap-3">
    <div className="grid h-10 w-10 place-items-center rounded-2xl bg-teal-600 text-white shadow-lg shadow-teal-200"><ShieldCheck size={21}/></div>
    {!compact && <div><div className="text-[17px] font-extrabold tracking-tight text-slate-900">CyberSaathi</div><div className="text-[10px] font-semibold uppercase tracking-[.16em] text-slate-400">Digital safety companion</div></div>}
  </div>;
}

function StatCard({ label, value, hint, icon: Icon, tone = "blue" }) {
  const tones = { blue: "bg-teal-50 text-teal-700", green: "bg-emerald-50 text-emerald-700", amber: "bg-amber-50 text-amber-700", violet: "bg-violet-50 text-violet-700" };
  return <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    <div className="flex items-start justify-between"><span className="text-sm font-medium text-slate-500">{label}</span><span className={cn("grid h-10 w-10 place-items-center rounded-xl", tones[tone])}><Icon size={19}/></span></div>
    <div className="mt-4 text-3xl font-extrabold tracking-tight text-slate-900">{value}</div>
    <div className="mt-1 text-xs text-slate-400">{hint}</div>
  </div>;
}

function SeverityPill({ status }) {
  const urgent = status === "urgent_response" || status === "urgent_protective_action";
  return <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold", urgent ? "bg-rose-50 text-rose-700" : "bg-amber-50 text-amber-700")}>
    <span className={cn("h-1.5 w-1.5 rounded-full", urgent ? "bg-rose-500" : "bg-amber-500")}/>{urgent ? "Urgent action" : "Review"}
  </span>;
}

function EmptyState({ onNew }) {
  return <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
    <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-teal-50 text-teal-600"><FileClock size={22}/></div>
    <h3 className="mt-4 font-bold text-slate-800">Your incident history starts here</h3>
    <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-slate-500">When you analyse a suspicious call, message or transaction, your report will appear here.</p>
    <button onClick={onNew} className="mt-5 inline-flex items-center gap-2 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-teal-700"><Plus size={16}/> Start an analysis</button>
  </div>;
}

function intensityTone(value) {
  const level = String(value || "").toLowerCase();
  if (["critical", "urgent", "urgent_response", "urgent_protective_action"].includes(level)) return "critical";
  if (["high", "elevated"].includes(level)) return "high";
  if (["medium", "important", "moderate", "review"].includes(level)) return "medium";
  return "low";
}

const intensityStyles = {
  critical: { card: "border-rose-300 bg-rose-100/90", icon: "text-rose-700", marker: "bg-rose-700", label: "text-rose-800", iconComponent: AlertTriangle },
  high: { card: "border-orange-300 bg-orange-100/90", icon: "text-orange-700", marker: "bg-orange-600", label: "text-orange-800", iconComponent: AlertTriangle },
  medium: { card: "border-amber-300 bg-amber-100/80", icon: "text-amber-700", marker: "bg-amber-600", label: "text-amber-800", iconComponent: AlertCircle },
  low: { card: "border-teal-200 bg-teal-50/90", icon: "text-teal-700", marker: "bg-teal-700", label: "text-teal-800", iconComponent: CheckCircle2 }
};

function ActionCard({ action }) {
  const tone = intensityTone(action.urgency || action.priority || action.risk_level);
  const style = intensityStyles[tone];
  const Icon = style.iconComponent;
  return <div className={cn("rounded-xl border p-4", style.card)}>
    <div className="flex items-start gap-3"><span className={cn("mt-0.5", style.icon)}><Icon size={17}/></span><div className="min-w-0 flex-1"><h4 className="text-sm font-bold text-slate-900">{action.title}</h4><p className="mt-1 text-sm leading-6 text-slate-700">{action.detail}</p>{action.destination && <p className="mt-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">{action.destination}</p>}</div></div>
  </div>;
}

function getGuidanceParts(analysis) {
  const raw = String(analysis?.localized_summary || analysis?.summary || analysis?.english_summary || "The incident details are being assessed.").trim();
  const actions = Array.isArray(analysis?.actions) ? analysis.actions : [];
  // The model's spoken summary often repeats the same steps that are also
  // returned as structured actions. Keep only the scenario introduction here.
  let cutAt = -1;
  const stepMarker = /\b(?:step\s*1\s*[:.)-]?|1\s*[.)]\s+)/i.exec(raw);
  if (stepMarker) cutAt = stepMarker.index;
  if (actions.length) {
    for (const action of actions) {
      for (const candidate of [action?.title, action?.detail]) {
        if (!candidate || candidate.trim().length < 18) continue;
        const idx = raw.toLowerCase().indexOf(candidate.trim().slice(0, 70).toLowerCase());
        if (idx >= 0 && (cutAt < 0 || idx < cutAt)) cutAt = idx;
      }
    }
  }
  let scenario = (cutAt >= 0 ? raw.slice(0, cutAt) : raw).trim();
  // Remove a trailing model-generated follow-up question; this interface is
  // a one-way guidance flow and does not present question prompts.
  scenario = scenario.replace(/\s*[^.!?]*\?\s*$/, "").trim();
  scenario = scenario.replace(/(?:Here are some safe habits[^.]*\.)\s*$/i, "").trim() || "Here is what the situation means and what to do next.";

  const resources = [];
  const addResource = (label, url) => {
    if (typeof url !== "string" || !/^https?:\/\//i.test(url.trim())) return;
    if (!resources.some(x => x.url === url.trim())) resources.push({ label: label || "Open official resource", url: url.trim() });
  };
  actions.forEach(a => addResource(a.destination || a.title || "Open official resource", a.url));
  (Array.isArray(analysis?.retrieved_sources) ? analysis.retrieved_sources : []).forEach(x => addResource(x.source || x.topic || "Reference source", x.url));

  // Make the instruction to open the resources explicit and place the links
  // immediately after that instruction in the ordered flow.
  const linkInstruction = /\b(click|open|visit|use)\b.{0,70}\b(links?|resources?)\b|\b(links?|resources?)\b.{0,70}\b(below|given|following)\b/i;
  let resourcesAfterStep = -1;
  if (resources.length) {
    resourcesAfterStep = actions.findIndex(a => linkInstruction.test(`${a?.title || ""} ${a?.detail || ""}`));
    if (resourcesAfterStep < 0) {
      actions.push({
        title: "Open the official links below",
        detail: "Click the relevant link below to open the official reporting or support resource. Use the link that matches your situation.",
        urgency: "low"
      });
      resourcesAfterStep = actions.length - 1;
    }
  }
  return { scenario, actions, resources, resourcesAfterStep };
}

function OrderedGuidance({ analysis, animate = true }) {
  const { scenario, actions, resources, resourcesAfterStep } = useMemo(() => getGuidanceParts(analysis), [analysis]);
  const [block, setBlock] = useState(animate ? 0 : actions.length + 1);
  const [chars, setChars] = useState(animate ? 0 : scenario.length);

  useEffect(() => {
    if (!animate) {
      setBlock(actions.length + 1);
      setChars(scenario.length);
      return;
    }
    let cancelled = false;
    let timer;
    let currentBlock = 0;
    let currentChars = 0;
    setBlock(0);
    setChars(0);
    const tick = () => {
      if (cancelled) return;
      const currentText = currentBlock === 0 ? scenario : String(actions[currentBlock - 1]?.detail || actions[currentBlock - 1]?.title || "");
      currentChars = Math.min(currentChars + 1, currentText.length);
      setBlock(currentBlock);
      setChars(currentChars);
      if (currentChars >= currentText.length) {
        currentBlock += 1;
        currentChars = 0;
        if (currentBlock <= actions.length) timer = setTimeout(tick, 900);
        else setBlock(actions.length + 1);
      } else timer = setTimeout(tick, 35);
    };
    timer = setTimeout(tick, 250);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [scenario, actions, animate]);

  const scenarioText = !animate || block > 0 ? scenario : scenario.slice(0, chars);
  const scenarioTyping = animate && block === 0 && chars < scenario.length;
  const scenarioTone = intensityStyles[intensityTone(analysis?.risk_level || analysis?.status)];
  return <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-md" aria-live="polite">
    <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-5 py-3">
      <div className="flex items-center gap-2"><ShieldCheck size={17} className="text-teal-700"/><h3 className="text-xs font-extrabold uppercase tracking-[.16em] text-slate-700">Incident guidance</h3></div>
      <span className="rounded-full bg-white px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-500">{actions.length} ordered {actions.length === 1 ? "step" : "steps"}</span>
    </div>
    <div className="p-4 sm:p-5">
      <div className={cn("rounded-xl border p-4", scenarioTone.card)}>
        <div className="mb-3 flex items-center gap-3"><span className={cn("grid h-9 w-9 place-items-center rounded-xl bg-white/80", scenarioTone.icon)}><Sparkles size={17}/></span><div><div className="flex items-center gap-2"><span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500">00</span><h4 className="text-sm font-extrabold text-slate-900">Scenario</h4></div><p className={cn("text-[10px] font-semibold uppercase tracking-wider", scenarioTone.label)}>Situation overview · {String(analysis?.risk_level || "assessment").replaceAll("_", " ")}</p></div></div>
        <p className="whitespace-pre-wrap text-sm leading-7 text-slate-700">{scenarioText}{scenarioTyping && <span className="ml-0.5 inline-block h-4 w-1 animate-pulse bg-teal-500 align-middle"/>}</p>
      </div>
      {actions.length > 0 && <div className="my-4 flex items-center gap-3"><div className="h-px flex-1 bg-slate-200"/><span className="text-[10px] font-extrabold uppercase tracking-[.16em] text-slate-400">Recommended sequence</span><div className="h-px flex-1 bg-slate-200"/></div>}
      <div className="space-y-3">
        {actions.map((action, i) => {
          const actionBlock = i + 1;
          if (animate && block < actionBlock) return null;
          const detail = String(action.detail || "");
          const isTyping = animate && block === actionBlock && chars < detail.length;
          const shownDetail = !animate || block > actionBlock ? detail : detail.slice(0, chars);
          const stepTone = intensityStyles[intensityTone(action.urgency || action.priority || action.risk_level)];
          return <div key={`${i}-${action.title || "step"}`}>
            <div className={cn("rounded-xl border p-4", stepTone.card)}>
              <div className="flex items-start gap-3">
                <span className={cn("grid h-9 w-9 shrink-0 place-items-center rounded-full text-sm font-extrabold text-white shadow-sm", stepTone.marker)}>{String(i + 1).padStart(2, "0")}</span>
                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex flex-wrap items-center gap-2"><span className={cn("text-[10px] font-extrabold uppercase tracking-[.14em]", stepTone.label)}>Step {i + 1}</span><span className="text-[10px] text-slate-400">of {actions.length}</span></div>
                  <h4 className="text-sm font-extrabold text-slate-900">{action.title || `Action ${i + 1}`}</h4>
                  <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-700">{shownDetail}{isTyping && <span className="ml-0.5 inline-block h-4 w-1 animate-pulse bg-teal-600 align-middle"/>}</p>
                  {action.destination && <p className="mt-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">{action.destination}</p>}
                </div>
              </div>
            </div>
            {resources.length > 0 && i === resourcesAfterStep && (!animate || block > actionBlock) && <div className="mt-3 rounded-xl border border-emerald-300 bg-emerald-50 p-4"><div className="mb-2 flex items-center gap-2 text-sm font-extrabold text-emerald-900"><ShieldCheck size={17}/> Official links and resources</div><p className="mb-3 text-xs leading-5 text-emerald-800">Select the relevant official link to continue.</p><div className="space-y-2">{resources.map((resource, ri) => <a key={ri} href={resource.url} target="_blank" rel="noopener noreferrer" className="flex items-center justify-between gap-3 rounded-lg border border-emerald-300 bg-white px-3 py-3 text-sm font-bold text-emerald-800 transition hover:bg-emerald-100 focus:outline-none focus:ring-2 focus:ring-emerald-500"><span className="min-w-0 break-words">{resource.label}</span><ArrowUpRight size={16} className="shrink-0"/></a>)}</div></div>}
          </div>;
        })}
      </div>
      {actions.length === 0 && block > 0 && <p className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-800">No specific action steps were returned. Review the scenario carefully and verify through official channels before acting.</p>}
    </div>
  </section>;
}

function AnalysisPanel({ session, onSaved, onClose }) {
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [audioFile, setAudioFile] = useState(null);
  const [speaking, setSpeaking] = useState(false);
  const [outputLanguage, setOutputLanguage] = useState("en-IN");
  const [liveActive, setLiveActive] = useState(false);
  const [liveStatus, setLiveStatus] = useState("Ready to connect");
  const [liveTranscript, setLiveTranscript] = useState([]);
  const liveRef = useRef({ socket: null, stream: null, context: null, processor: null, source: null, pending: [], playAt: 0 });

  const saveIncident = useCallback(async (analysis, narration) => {
    const row = {
      id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`,
      user_id: "local-guest",
      narration,
      category: analysis.category,
      status: analysis.status,
      summary: analysis.localized_summary || analysis.summary,
      detailed_analysis: analysis.detailed_analysis || analysis.english_summary || "",
      localized_summary: analysis.localized_summary || analysis.summary,
      output_language: analysis.output_language || "en-IN",
      engine: analysis.engine,
      events: analysis.events || [],
      confirmed_facts: analysis.confirmed_facts || [],
      suspicious_indicators: analysis.suspicious_indicators || [],
      unknowns: analysis.unknowns || [],
      questions: analysis.questions || [],
      actions: analysis.actions || [],
      disclaimer: analysis.disclaimer || "",
      created_at: new Date().toISOString()
    };
    onSaved?.(row);
  }, [onSaved]);

  async function runAnalysis(narration = text) {
    if (narration.trim().length < 5) { setError("Please describe what happened in a little more detail."); return; }
    setBusy(true); setError(""); setResult(null);
    try {
      const response = await apiFetch("/api/incidents/analyze", session, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ narration, output_language: outputLanguage })
      });
      const analysis = await response.json();
      setResult(analysis);
      await saveIncident(analysis, narration);
      // Automatically start Timbre once the analysis and approved summary are ready.
      await speakSummary(analysis);
    } catch (e) { setError(e.message || "Could not analyse this incident."); }
    finally { setBusy(false); }
  }

  async function transcribeAndAnalyze() {
    if (!audioFile) return;
    setBusy(true); setError(""); setResult(null);
    try {
      const form = new FormData(); form.append("file", audioFile);
      const response = await apiFetch("/api/audio/transcribe", session, { method: "POST", body: form });
      const data = await response.json();
      setText(data.transcript || "");
      await runAnalysis(data.transcript || "");
    } catch (e) { setError(e.message || "Audio processing failed."); setBusy(false); }
  }

  async function startLiveSession() {
    setError(""); setLiveTranscript([]); setLiveStatus("Requesting microphone…");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      const context = new AudioContext();
      await context.resume();
      const socket = new WebSocket(`${LIVE_WS}?output_language=${encodeURIComponent(outputLanguage)}`);
      socket.binaryType = "arraybuffer";
      const state = liveRef.current;
      Object.assign(state, { socket, stream, context, pending: [], playAt: context.currentTime });
      socket.onopen = () => {
        setLiveActive(true); setLiveStatus("Connected · listening");
        const source = context.createMediaStreamSource(stream);
        const processor = context.createScriptProcessor(1024, 1, 1);
        state.source = source; state.processor = processor;
        processor.onaudioprocess = event => {
          if (socket.readyState !== WebSocket.OPEN) return;
          const input = event.inputBuffer.getChannelData(0);
          // Browser audio is commonly 48 kHz. Downsample to 16 kHz mono PCM16.
          const ratio = context.sampleRate / 16000;
          for (let i = 0; i < input.length; i += Math.max(1, Math.round(ratio))) {
            const sample = Math.max(-1, Math.min(1, input[i]));
            state.pending.push(sample < 0 ? sample * 32768 : sample * 32767);
          }
          while (state.pending.length >= 512) {
            const frame = new Int16Array(state.pending.splice(0, 512));
            if (socket.bufferedAmount < 256 * 1024) socket.send(frame.buffer);
          }
        };
        source.connect(processor); processor.connect(context.destination);
      };
      socket.onmessage = async event => {
        let msg; try { msg = JSON.parse(event.data); } catch { return; }
        if (msg.type === "ready") setLiveStatus(msg.message);
        if (msg.type === "speech_start") setLiveStatus("Speech detected…");
        if (msg.type === "transcript") {
          setLiveStatus("Understanding what you said…");
          setLiveTranscript(old => [...old, msg.text].slice(-8));
          setText(old => (old ? old + "\n" : "") + msg.text);
        }
        if (msg.type === "analysis") {
          setResult(msg.analysis); setLiveStatus("Analysis ready · keep speaking or stop");
          await saveIncident(msg.analysis, msg.transcript);
        }
        if (msg.type === "speech_started") { setSpeaking(true); setLiveStatus("Analysis ready · speaking your guidance…"); }
        if (msg.type === "audio" && msg.audio) {
          const binary = atob(msg.audio); const bytes = new Uint8Array(binary.length);
          for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
          const pcm = new Int16Array(bytes.buffer);
          const buffer = context.createBuffer(1, pcm.length, msg.sample_rate || 48000);
          const channel = buffer.getChannelData(0);
          for (let i = 0; i < pcm.length; i++) channel[i] = pcm[i] / 32768;
          const node = context.createBufferSource(); node.buffer = buffer; node.connect(context.destination);
          state.playAt = Math.max(state.playAt, context.currentTime + 0.04);
          node.start(state.playAt); state.playAt += buffer.duration;
        }
        if (msg.type === "audio_complete") { setSpeaking(false); setLiveStatus("Spoken response complete · listening"); }
        if (msg.type === "tts_error") { setSpeaking(false); setError(msg.message || "Timbre could not speak the response."); setLiveStatus("Speech unavailable"); }
        if (msg.type === "error") { setError(msg.message); setLiveStatus("Connection error"); }
      };
      socket.onerror = () => { setError("Live connection failed. Check the backend and GNANI_API_KEY."); setLiveStatus("Connection failed"); };
      socket.onclose = () => { setLiveActive(false); setLiveStatus("Disconnected"); };
    } catch (e) { setError(e.message || "Could not start microphone."); setLiveStatus("Microphone unavailable"); stopLiveSession(); }
  }

  function finishLiveTurn() {
    const socket = liveRef.current.socket;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({ type: "finish_turn" }));
    setLiveStatus("Analysing your complete narration…");
  }

  function stopLiveSession() {
    const state = liveRef.current;
    try { if (state.socket?.readyState === WebSocket.OPEN) state.socket.send(JSON.stringify({ type: "stop" })); state.socket?.close(); } catch {}
    state.processor?.disconnect(); state.source?.disconnect();
    state.stream?.getTracks().forEach(track => track.stop());
    state.context?.close();
    liveRef.current = { socket: null, stream: null, context: null, processor: null, source: null, pending: [], playAt: 0 };
    setLiveActive(false); setLiveStatus("Session stopped");
  }

  useEffect(() => () => {
    const state = liveRef.current;
    try { state.socket?.close(); } catch {}
    state.stream?.getTracks().forEach(track => track.stop());
    state.context?.close();
  }, []);

  async function speakSummary(analysisToSpeak = result) {
    if (!analysisToSpeak?.summary?.trim()) {
      setError("Analyse an incident before requesting spoken guidance.");
      return;
    }
    setSpeaking(true); setError("");
    try {
      const response = await apiFetch("/api/speech/synthesize", session, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: analysisToSpeak.localized_summary || analysisToSpeak.english_summary || analysisToSpeak.summary, language: analysisToSpeak.output_language || outputLanguage })
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "Timbre could not generate the response audio.");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => { URL.revokeObjectURL(url); setSpeaking(false); };
      audio.onerror = () => { URL.revokeObjectURL(url); setSpeaking(false); };
      await audio.play();
    } catch (e) { setError(e.message || "Timbre is unavailable."); setSpeaking(false); }
  }

  return <div className="space-y-6">
    <div className="flex flex-wrap items-end justify-between gap-4"><div><div className="text-xs font-bold uppercase tracking-[.12em] text-orange-700">Incident desk / New report</div><h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">Tell us what happened.</h2><p className="mt-2 max-w-xl text-sm leading-6 text-slate-600">Start wherever it makes sense. Describe the call, message, link or transaction in your own words.</p></div>{onClose && <button onClick={onClose} className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:bg-slate-50"><X size={17}/></button>}</div>
    <div className="flex flex-wrap items-center justify-between gap-3 border-y border-stone-200 py-3"><div><div className="text-sm font-semibold text-slate-800">Response language</div><p className="mt-0.5 text-xs text-slate-500">Choose the language for the written and spoken response.</p></div><select id="output-language" aria-label="Select response language" value={outputLanguage} onChange={e => setOutputLanguage(e.target.value)} className="min-w-48 rounded-lg border border-stone-300 bg-white px-3 py-2.5 text-sm text-slate-800"><option value="en-IN">English</option><option value="hi-IN">Hindi</option><option value="bn-IN">Bengali</option><option value="te-IN">Telugu</option><option value="ta-IN">Tamil</option><option value="mr-IN">Marathi</option><option value="gu-IN">Gujarati</option><option value="kn-IN">Kannada</option><option value="ml-IN">Malayalam</option><option value="pa-IN">Punjabi</option><option value="or-IN">Odia</option></select></div>
    <div className="grid grid-cols-1 gap-5 md:grid-cols-2 md:items-start">
      <div className="space-y-5">
    <div className="rounded-xl border border-stone-200 bg-white p-5">
      <div className="flex items-center justify-between gap-3"><label htmlFor="story" className="text-sm font-bold text-slate-800">Describe the situation</label><span className="text-[11px] text-slate-400">{text.length}/8000</span></div>
      <textarea id="story" value={text} onChange={e => setText(e.target.value)} rows={7} maxLength={8000} placeholder="For example: I received a call from someone claiming to be from my bank..." className="mt-3 w-full resize-y rounded-xl border border-slate-200 bg-slate-50/70 p-4 text-sm leading-7 text-slate-700 outline-none transition placeholder:text-slate-400 focus:border-teal-300 focus:bg-white focus:ring-4 focus:ring-teal-50"/>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3"><p className="text-xs text-slate-500">Please leave out OTPs, PINs, passwords and full account numbers.</p><button onClick={() => runAnalysis()} disabled={busy || text.trim().length < 5} className="inline-flex items-center gap-2 rounded-xl bg-teal-600 px-5 py-3 text-sm font-bold text-white shadow-lg shadow-teal-200 transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-50">{busy ? <LoaderCircle className="animate-spin" size={17}/> : <Sparkles size={16}/>} Analyse situation</button></div>
    </div>
    <div><div className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-400">Try an example</div><div className="flex flex-wrap gap-2">{EXAMPLES.map(([label, value]) => <button key={label} onClick={() => setText(value)} className="rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 transition hover:border-teal-200 hover:text-teal-700">{label}</button>)}</div></div>
      </div>
      <div className="h-full">
    <div className="rounded-2xl border border-teal-200 bg-gradient-to-br from-teal-50 to-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><div className="flex items-center gap-2 text-sm font-extrabold text-teal-950"><Mic size={18}/> Live voice conversation <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-wide text-emerald-700">Realtime</span></div><p className="mt-1 text-xs leading-5 text-slate-600">Talk naturally in any of Prisma v3.0’s supported languages. Prisma auto-detects the spoken language; choose the language you want CyberSaathi to speak in above.</p></div><button onClick={liveActive ? stopLiveSession : startLiveSession} className={cn("inline-flex items-center gap-2 rounded-xl px-4 py-3 text-xs font-extrabold text-white", liveActive ? "bg-rose-600 hover:bg-rose-700" : "bg-teal-700 hover:bg-teal-800")}>{liveActive ? <><X size={15}/> End live session</> : <><Mic size={15}/> Start live session</>}</button></div>
      <div className="mt-3 flex items-center gap-2 text-xs font-semibold text-slate-600"><span className={cn("h-2 w-2 rounded-full", liveActive ? "animate-pulse bg-emerald-500" : "bg-slate-300")}/>{liveStatus}</div>
      {liveTranscript.length > 0 && <div className="mt-4 max-h-36 space-y-2 overflow-y-auto rounded-xl border border-teal-100 bg-white/80 p-3">{liveTranscript.map((line, i) => <p key={i} className="text-xs leading-5 text-slate-700">{line}</p>)}</div>}
      {liveActive && <div className="mt-3 flex justify-end"><button onClick={finishLiveTurn} className="inline-flex items-center gap-2 rounded-xl bg-teal-700 px-4 py-2.5 text-xs font-extrabold text-white hover:bg-teal-800"><Sparkles size={14}/> Analyse & respond</button></div>}
      <p className="mt-3 text-[10px] leading-4 text-slate-500">Microphone audio is streamed to Gnani Prisma. Do not say OTPs, PINs, passwords or full account details. Keep this tab open during the session.</p>
    </div>
      </div>
    </div>
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex items-center gap-2 text-sm font-bold text-slate-800"><AudioLines size={18} className="text-teal-600"/> Voice input with Prisma</div>
      <p className="mt-1 text-xs leading-5 text-slate-500">Upload an audio recording to transcribe it. Audio is sent to the configured speech service for processing.</p>
      <div className="mt-4 flex flex-wrap items-center gap-3"><input type="file" accept="audio/*" onChange={e => setAudioFile(e.target.files?.[0] || null)} className="max-w-full text-xs text-slate-500 file:mr-3 file:rounded-lg file:border-0 file:bg-teal-50 file:px-3 file:py-2 file:text-xs file:font-bold file:text-teal-700"/><button onClick={transcribeAndAnalyze} disabled={!audioFile || busy} className="inline-flex items-center gap-2 rounded-lg border border-teal-200 px-4 py-2.5 text-xs font-bold text-teal-700 hover:bg-teal-50 disabled:opacity-50"><Upload size={14}/> Transcribe & analyse</button></div>
    </div>
    {error && <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</div>}
    {result && <div className="space-y-4" aria-live="polite">
      <div className={cn("rounded-xl border p-5", result.status === "urgent_response" ? "border-rose-200 bg-rose-50" : "border-stone-200 bg-white")}>
        <div className="flex flex-wrap items-center justify-between gap-2"><SeverityPill status={result.status}/><span className="text-[10px] font-semibold text-slate-500">{result.summary_provider === "local_qwen3" ? "AI analysis · Local Qwen3" : result.summary_provider ? `AI analysis · ${String(result.summary_provider).replaceAll("_", " ")}` : "Analysis ready"}</span></div>
        <h3 className="mt-3 text-xl font-extrabold capitalize text-slate-900">{(result.category || "Situation").replaceAll("_", " ")}</h3>
        <p className="mt-2 text-[10px] text-slate-400">The scenario and recommended steps appear in sequence. Spoken language: {result.output_language || outputLanguage}.</p>
        <button onClick={speakSummary} disabled={speaking} className="mt-4 inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-50">{speaking ? <LoaderCircle size={15} className="animate-spin"/> : <Volume2 size={15}/>} Replay full response</button>
      </div>
      <OrderedGuidance analysis={result}/>
      <p className="rounded-xl bg-slate-100 p-3 text-xs leading-5 text-slate-500">{result.disclaimer}</p>
    </div>}
  </div>;
}

function IncidentList({ incidents, onOpen, onNew }) {
  if (!incidents.length) return <EmptyState onNew={onNew}/>;
  return <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
    <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4"><div><h3 className="font-bold text-slate-900">All incident reports</h3><p className="mt-1 text-xs text-slate-400">Private to your account</p></div><span className="rounded-full bg-teal-50 px-3 py-1 text-xs font-bold text-teal-700">{incidents.length} reports</span></div>
    <div className="divide-y divide-slate-100">{incidents.map(item => <button key={item.id} onClick={() => onOpen(item)} className="flex w-full items-center gap-4 px-5 py-4 text-left transition hover:bg-slate-50"><div className={cn("grid h-10 w-10 shrink-0 place-items-center rounded-xl", item.status === "urgent_response" ? "bg-rose-50 text-rose-600" : "bg-teal-50 text-teal-600")}><FileText size={18}/></div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className="truncate text-sm font-bold capitalize text-slate-800">{(item.category || "Incident").replaceAll("_", " ")}</span><SeverityPill status={item.status}/></div><p className="mt-1 truncate text-xs text-slate-500">{item.summary || item.narration}</p><p className="mt-1 text-[10px] text-slate-400">{timeAgo(item.created_at)}</p></div><ChevronRight size={17} className="shrink-0 text-slate-300"/></button>)}</div>
  </div>;
}

function DetailModal({ incident, onClose }) {
  if (!incident) return null;
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/30 p-4 backdrop-blur-sm" onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}>
    <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl">
      <div className="flex items-start justify-between gap-3"><div><SeverityPill status={incident.status}/><h3 className="mt-3 text-xl font-extrabold capitalize text-slate-900">{(incident.category || "Incident").replaceAll("_", " ")}</h3><p className="mt-1 text-xs text-slate-400">{new Date(incident.created_at).toLocaleString()}</p></div><button onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"><X size={18}/></button></div>
      <div className="mt-5 rounded-xl bg-slate-50 p-4"><div className="text-xs font-bold uppercase tracking-wider text-slate-400">Your description</div><p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-slate-700">{incident.narration}</p></div>
      <div className="mt-5"><OrderedGuidance analysis={incident} animate={false}/></div>
      {incident.events?.length > 0 && <div className="mt-5"><div className="text-sm font-bold text-slate-800">Incident timeline</div><ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-slate-600">{incident.events.map((ev, i) => <li key={i}>{ev.description}</li>)}</ol></div>}
      <p className="mt-5 text-xs leading-5 text-slate-400">{incident.disclaimer}</p>
    </div>
  </div>;
}

function SafetyPage() {
  const items = [
    ["Never share secrets", "No legitimate bank employee needs your OTP, UPI PIN, card PIN or password."],
    ["Verify independently", "If someone claims to be from a bank or company, contact it using the official app or website—not a number they provide."],
    ["If money is lost", "Contact your bank immediately and call 1930 promptly. Also file a complaint on the National Cyber Crime Reporting Portal."],
    ["Report suspicious communications", "Use Chakshu on Sanchar Saathi for suspected fraudulent calls, SMS or WhatsApp messages. It is not a replacement for reporting an actual financial loss."]
  ];
  return <div className="space-y-5"><div><div className="text-xs font-bold uppercase tracking-[.16em] text-teal-600">Learn and protect</div><h2 className="mt-2 text-2xl font-extrabold text-slate-900">Safety centre</h2><p className="mt-1 text-sm text-slate-500">Simple habits that make common digital scams harder to pull off.</p></div><div className="grid gap-3 md:grid-cols-2">{items.map(([title, body], i) => <div key={title} className="rounded-2xl border border-slate-200 bg-white p-5"><div className="flex h-9 w-9 items-center justify-center rounded-xl bg-teal-50 text-teal-700"><ShieldCheck size={18}/></div><h3 className="mt-4 font-bold text-slate-900">{title}</h3><p className="mt-2 text-sm leading-6 text-slate-500">{body}</p></div>)}</div><div className="rounded-2xl border border-rose-200 bg-rose-50 p-5"><div className="flex items-center gap-2 font-bold text-rose-800"><LifeBuoy size={18}/> Need urgent help?</div><p className="mt-2 text-sm leading-6 text-rose-800">For suspected financial cyber fraud, contact your bank immediately and call <b>1930</b>. File a report through the official portal.</p><div className="mt-4 flex flex-wrap gap-3"><a className="rounded-lg bg-rose-700 px-4 py-2.5 text-xs font-bold text-white" href="https://cybercrime.gov.in/" target="_blank" rel="noreferrer">Cyber Crime Portal <ArrowUpRight size={13} className="inline"/></a><a className="rounded-lg border border-rose-200 bg-white px-4 py-2.5 text-xs font-bold text-rose-800" href="https://sancharsaathi.gov.in/" target="_blank" rel="noreferrer">Sanchar Saathi / Chakshu <ArrowUpRight size={13} className="inline"/></a></div></div></div>;
}

function Overview({ user, incidents, onNew, onIncidents, onOpen }) {
  const urgent = incidents.filter(x => x.status === "urgent_response").length;
  const reviewed = incidents.length - urgent;
  const recent = incidents.slice(0, 4);
  return <div className="space-y-7">
    <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-emerald-950 via-teal-800 to-cyan-800 p-7 text-white shadow-xl shadow-teal-200/70 sm:p-9">
      <div className="relative z-10 max-w-xl"><div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider"><Sparkles size={13}/> Your digital safety space</div><h2 className="mt-5 text-3xl font-extrabold tracking-tight sm:text-4xl">Hello, {displayName(user)}.</h2><p className="mt-3 max-w-lg text-sm leading-7 text-teal-50">Not sure about a call, message or transaction? Tell CyberSaathi what happened. We'll help you organise the details and identify safer next steps.</p><button onClick={onNew} className="mt-6 inline-flex items-center gap-2 rounded-xl bg-white px-4 py-3 text-sm font-extrabold text-teal-700 shadow-sm transition hover:bg-teal-50">Start a safety check <ArrowRight size={16}/></button></div>
      <div className="pointer-events-none absolute -right-10 -top-16 hidden h-80 w-80 rounded-full border-[36px] border-white/10 lg:block"/><div className="pointer-events-none absolute right-20 top-20 hidden h-40 w-40 rounded-full border-[24px] border-white/10 lg:block"/>
    </div>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard label="Reports saved" value={incidents.length} hint="In your personal history" icon={FileText} tone="blue"/>
      <StatCard label="Need urgent action" value={urgent} hint="Marked by prototype rules" icon={AlertTriangle} tone="amber"/>
      <StatCard label="Other reports" value={reviewed} hint="Review the recommended steps" icon={ShieldCheck} tone="green"/>
      <StatCard label="Your account" value="Active" hint="Signed in securely" icon={UserRound} tone="violet"/>
    </div>
    <div className="grid gap-5 xl:grid-cols-[1.35fr_.75fr]">
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="flex items-center justify-between border-b border-slate-100 px-5 py-4"><div><h3 className="font-bold text-slate-900">Recent activity</h3><p className="mt-1 text-xs text-slate-400">Your latest saved incident reports</p></div><button onClick={onIncidents} className="text-xs font-bold text-teal-700 hover:underline">View all</button></div>{recent.length ? <div className="divide-y divide-slate-100">{recent.map(item => <button key={item.id} onClick={() => onOpen(item)} className="flex w-full items-center gap-3 px-5 py-4 text-left hover:bg-slate-50"><div className="grid h-9 w-9 place-items-center rounded-xl bg-teal-50 text-teal-700"><FileText size={16}/></div><div className="min-w-0 flex-1"><div className="truncate text-sm font-bold capitalize text-slate-800">{(item.category || "Incident").replaceAll("_", " ")}</div><div className="mt-1 truncate text-xs text-slate-500">{item.summary || item.narration}</div></div><div className="hidden text-[10px] text-slate-400 sm:block">{timeAgo(item.created_at)}</div><ChevronRight size={15} className="text-slate-300"/></button>)}</div> : <div className="px-5 py-10 text-center"><div className="mx-auto grid h-10 w-10 place-items-center rounded-xl bg-teal-50 text-teal-600"><FileClock size={18}/></div><p className="mt-3 text-sm font-semibold text-slate-700">No reports yet</p><p className="mt-1 text-xs text-slate-400">Your saved analyses will appear here.</p></div>}</div>
      <div className="space-y-4"><div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-center gap-2 text-sm font-bold text-slate-900"><ShieldCheck size={18} className="text-emerald-600"/> A quick safety reminder</div><p className="mt-3 text-sm leading-6 text-slate-500">Never share OTPs, UPI PINs, passwords or remote-access permissions with someone who contacts you unexpectedly.</p></div><div className="rounded-2xl border border-teal-100 bg-teal-50/70 p-5"><div className="flex items-center gap-2 text-sm font-bold text-teal-900"><Headphones size={18}/> Speak naturally</div><p className="mt-2 text-sm leading-6 text-teal-800/80">You don't need technical words. Describe what the person said, what you clicked and what happened next.</p><button onClick={onNew} className="mt-3 text-xs font-extrabold text-teal-700 hover:underline">Try an analysis <ArrowRight size={13} className="inline"/></button></div></div>
    </div>
  </div>;
}


export default function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [fullName, setFullName] = useState("");
  const [loginId, setLoginId] = useState("");
  const [password, setPassword] = useState("");
  const guestUser = {
    id: "local-guest",
    email: loginId || "Local browser session",
    user_metadata: { full_name: fullName || "Guest" }
  };
  const session = { user: guestUser };
  const [page, setPage] = useState("overview");
  const [incidents, setIncidents] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [mobileNav, setMobileNav] = useState(false);
  const [toast, setToast] = useState("");

  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem("cybersaathi_incidents") || "[]");
      setIncidents(Array.isArray(stored) ? stored : []);
    } catch {
      setIncidents([]);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const saveIncident = useCallback((row) => {
    setIncidents(previous => {
      const next = [row, ...previous].slice(0, 100);
      try { localStorage.setItem("cybersaathi_incidents", JSON.stringify(next)); }
      catch { setToast("Report analysed, but browser storage is full. Export or clear older browser data."); }
      return next;
    });
    setToast("Incident report saved in this browser.");
    window.setTimeout(() => setToast(""), 3500);
  }, []);

  const clearHistory = () => {
    if (!window.confirm("Delete all incident reports saved in this browser? This cannot be undone.")) return;
    localStorage.removeItem("cybersaathi_incidents");
    setIncidents([]);
    setSelected(null);
    setToast("Local incident history cleared.");
    window.setTimeout(() => setToast(""), 3000);
  };

  const title = ({ overview: "Overview", analyze: "New analysis", incidents: "My incidents", safety: "Safety centre" })[page] || "Overview";

  if (!isLoggedIn) {
    return <div className="min-h-screen flex items-center justify-center bg-[#f6f4ef] px-5 py-10">
      <div className="grid w-full max-w-4xl overflow-hidden rounded-3xl border border-stone-200 bg-white shadow-xl md:grid-cols-2">
        <div className="flex flex-col justify-center bg-gradient-to-br from-emerald-950 via-teal-800 to-cyan-800 p-9 text-white sm:p-12">
          <Brand />
          <h1 className="mt-12 text-4xl font-extrabold tracking-tight">Your safety, our priority.</h1>
          <p className="mt-4 text-sm leading-7 text-teal-50">Your digital safety companion. Understand suspicious calls, messages and transactions, and find safer next steps.</p>
        </div>
        <form onSubmit={event => { event.preventDefault(); setIsLoggedIn(true); }} className="flex flex-col justify-center p-8 sm:p-12">
          <h2 className="text-2xl font-extrabold text-slate-900">Welcome to CyberSaathi</h2>
          <p className="mt-2 text-sm text-slate-500">Enter your details to continue.</p>
          <label htmlFor="full-name" className="mt-7 text-sm font-semibold text-slate-700">Your name</label>
          <input id="full-name" required value={fullName} onChange={event => setFullName(event.target.value)} placeholder="Enter your name" className="mt-2 rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none focus:border-teal-700 focus:ring-4 focus:ring-teal-50" />
          <label htmlFor="login-id" className="mt-4 text-sm font-semibold text-slate-700">Login ID</label>
          <input id="login-id" required value={loginId} onChange={event => setLoginId(event.target.value)} placeholder="Enter Login ID" className="mt-2 rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none focus:border-teal-700 focus:ring-4 focus:ring-teal-50" />
          <label htmlFor="login-password" className="mt-4 text-sm font-semibold text-slate-700">Password</label>
          <input id="login-password" type="password" required value={password} onChange={event => setPassword(event.target.value)} placeholder="Enter password" className="mt-2 rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none focus:border-teal-700 focus:ring-4 focus:ring-teal-50" />
          <button type="submit" className="mt-7 rounded-xl bg-teal-800 py-3 text-sm font-bold text-white transition hover:bg-teal-900">Sign in <span aria-hidden="true">→</span></button>
          <p className="mt-5 text-center text-xs leading-5 text-slate-400">Prototype sign-in · This screen does not provide real account authentication.</p>
        </form>
      </div>
    </div>;
  }

  return <div className="app-shell min-h-screen bg-[#f6f4ef]">
    {mobileNav && <button aria-label="Close menu" onClick={() => setMobileNav(false)} className="fixed inset-0 z-30 bg-slate-900/20 lg:hidden"/>}
    <aside className={cn("fixed inset-y-0 left-0 z-40 flex w-[258px] flex-col border-r border-slate-200 bg-white px-4 py-5 transition-transform lg:translate-x-0", mobileNav ? "translate-x-0" : "-translate-x-full")}>
      <div className="flex items-center justify-between px-2"><Brand/><button onClick={() => setMobileNav(false)} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 lg:hidden"><X size={17}/></button></div>
      <div className="mt-10 px-3 text-[10px] font-extrabold uppercase tracking-[.16em] text-slate-400">Workspace</div>
      <nav className="mt-3 space-y-1">{navItems.map(({ id, label, icon: Icon }) => <button key={id} onClick={() => { setPage(id); setMobileNav(false); }} className={cn("flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm font-semibold transition", page === id ? "bg-teal-50 text-teal-700" : "text-slate-500 hover:bg-slate-50 hover:text-slate-800")}><Icon size={18}/>{label}{id === "incidents" && incidents.length > 0 && <span className="ml-auto rounded-full bg-white px-2 py-0.5 text-[10px] font-bold text-slate-500">{incidents.length}</span>}</button>)}</nav>
      <div className="mt-auto rounded-2xl bg-gradient-to-br from-teal-50 to-cyan-50 p-4"><div className="grid h-9 w-9 place-items-center rounded-xl bg-white text-teal-700 shadow-sm"><LifeBuoy size={18}/></div><div className="mt-3 text-sm font-bold text-slate-800">Need urgent help?</div><p className="mt-1 text-xs leading-5 text-slate-500">If money was taken, contact your bank and call 1930 promptly.</p><a href="https://cybercrime.gov.in/" target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-xs font-extrabold text-teal-700">Official portal <ArrowUpRight size={13}/></a></div>
      <div className="mt-4 rounded-xl border border-amber-100 bg-amber-50 px-3 py-2 text-[10px] leading-4 text-amber-800">Signed in as {fullName} · Reports stay in this browser only</div>
    </aside>
    <div className="min-h-screen lg:pl-[258px]">
      <header className="sticky top-0 z-20 flex h-[76px] items-center justify-between border-b border-slate-200 bg-white/90 px-4 backdrop-blur-xl sm:px-7">
        <div className="flex items-center gap-3"><button onClick={() => setMobileNav(true)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 lg:hidden"><Menu size={19}/></button><div><div className="text-[10px] font-bold uppercase tracking-[.16em] text-slate-400">CyberSaathi workspace</div><h1 className="mt-0.5 text-lg font-extrabold text-slate-900">{title}</h1></div></div>
        <div className="flex items-center gap-3"><span className="hidden text-sm font-semibold text-slate-700 sm:inline">{fullName}</span><div className="grid h-9 w-9 place-items-center rounded-full bg-teal-100 text-xs font-extrabold text-teal-800">{initials(guestUser)}</div><button onClick={() => { setIsLoggedIn(false); setPassword(""); }} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50">Log out</button></div>
      </header>
      <main className="mx-auto max-w-[1440px] px-4 py-7 sm:px-7 lg:px-9">
        {page === "overview" && <Overview user={guestUser} incidents={incidents} onNew={() => setPage("analyze")} onIncidents={() => setPage("incidents")} onOpen={setSelected}/>}
        {page === "analyze" && <AnalysisPanel session={session} onSaved={saveIncident}/>}
        {page === "incidents" && <div className="space-y-5"><div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-2xl font-extrabold text-slate-900">Your incident history</h2><p className="mt-1 text-sm text-slate-500">Reports saved locally in this browser.</p></div><div className="flex gap-2"><button onClick={clearHistory} disabled={!incidents.length} className="rounded-xl border border-slate-200 px-3 py-2.5 text-xs font-bold text-slate-500 hover:bg-slate-50 disabled:opacity-40">Clear history</button><button onClick={() => setPage("analyze")} className="inline-flex items-center gap-2 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-teal-700"><Plus size={16}/> New analysis</button></div></div>{historyLoading ? <div className="py-10 text-center text-sm text-slate-400"><LoaderCircle className="mx-auto mb-2 animate-spin"/>Loading your reports…</div> : <IncidentList incidents={incidents} onOpen={setSelected} onNew={() => setPage("analyze")}/>}</div>}
        {page === "safety" && <SafetyPage/>}
      </main>
      <footer className="border-t border-slate-200 bg-white px-5 py-5 text-center text-[11px] text-slate-400">CyberSaathi · A digital safety companion prototype · Reports are stored in this browser</footer>
    </div>
    {selected && <DetailModal incident={selected} onClose={() => setSelected(null)}/>}
    {toast && <div role="status" className="fixed bottom-5 right-5 z-50 flex max-w-sm items-center gap-2 rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white shadow-xl"><Check size={16} className="text-emerald-400"/>{toast}</div>}
  </div>;
}
