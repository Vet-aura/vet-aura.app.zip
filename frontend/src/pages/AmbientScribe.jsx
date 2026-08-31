import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Mic, Square, Sparkles, FileCheck2, Save, Wand2, RotateCcw, Upload } from "lucide-react";
import { toast } from "sonner";

const SAMPLES = [
  {
    label: "Bella — Recheck otitis externa",
    text: "Bella is a 7-year-old spayed female golden retriever presenting for recheck of chronic otitis externa AU. Owner reports increased head shaking over the past three days and mild pruritus, worse on the right. Last cytology showed Malassezia. On exam: bright and alert, T 38.7, HR 108, RR 24, mucous membranes pink, CRT under 2 seconds. Ears: right pinna erythema mild, waxy brown discharge, canal not swollen. Left ear improved compared to prior visit. Remainder of exam unremarkable. Plan is to repeat ear cytology, continue current topical, add cleanser twice weekly, follow up in three weeks.",
  },
  {
    label: "Milo — CKD progress",
    text: "Milo is a 12-year-old neutered male domestic shorthair with IRIS stage 2 chronic kidney disease. Owner reports appetite slightly decreased over the last week, drinking more. Weight today 4.1 kg down from 4.3. On exam: BCS 4 out of 9, mild dehydration estimated at five percent, kidneys small and irregular on palpation. Vitals within range. Blood pressure 155 over 90. Assessment CKD progression suspected. Plan is renal panel, urinalysis, SDMA, and start subcutaneous fluids at home 100 mL every other day. Recheck in two weeks.",
  },
  {
    label: "Luna — Orthopedic exam",
    text: "Luna is a 3-year-old intact female French bulldog for orthopedic consult. Owner reports intermittent left hind lameness that started 2 weeks ago after park play. On exam: skips on left hind at trot, grade 2 medial patellar luxation reducible on manipulation, no cranial drawer, no pain on hip extension. Body condition score 5 out of 9. Recommend radiographs and physical therapy plan; surgical consultation if lameness progresses.",
  },
];

const emptySoap = { subjective: "", objective: "", assessment: "", plan: "", confidence: "", flags: [] };

export default function AmbientScribe() {
  const [patients, setPatients] = useState([]);
  const [patientId, setPatientId] = useState("");
  const [templates, setTemplates] = useState([]);
  const [templateId, setTemplateId] = useState("");
  const [transcript, setTranscript] = useState("");
  const [soap, setSoap] = useState(emptySoap);
  const [busy, setBusy] = useState(false);
  const [genBusy, setGenBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const mediaRef = useRef(null);
  const chunksRef = useRef([]);
  const tickRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    api.get("/patients").then((r) => setPatients(r.data)).catch(() => {});
    api.get("/scribe/templates").then((r) => setTemplates(r.data || [])).catch(() => {});
  }, []);

  useEffect(() => () => {
    if (tickRef.current) clearInterval(tickRef.current);
    if (mediaRef.current?.state === "recording") mediaRef.current.stop();
  }, []);

  function pickMime() {
    const candidates = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/mp4",
      "audio/mpeg",
      "audio/ogg;codecs=opus",
    ];
    for (const m of candidates) {
      if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(m)) return m;
    }
    return "";
  }

  async function startRec() {
    if (typeof MediaRecorder === "undefined") {
      return toast.error("Recording is not supported in this browser. Load a sample below.");
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = pickMime();
      const mr = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      const chosen = mr.mimeType || mime || "audio/webm";
      chunksRef.current = [];
      mr.ondataavailable = (e) => e.data.size && chunksRef.current.push(e.data);
      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: chosen });
        if (blob.size < 1000) {
          toast.error("Recording too short. Try again for at least 2 seconds.");
          return;
        }
        const ext = chosen.includes("mp4") ? "mp4" : chosen.includes("mpeg") ? "mp3" : chosen.includes("ogg") ? "ogg" : "webm";
        await uploadForTranscription(blob, `session.${ext}`);
      };
      mr.start(1000);
      mediaRef.current = mr;
      setRecording(true);
      setElapsed(0);
      tickRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
    } catch (e) {
      toast.error("Microphone permission required. You can also load a sample transcript below.");
    }
  }

  function stopRec() {
    if (mediaRef.current?.state === "recording") mediaRef.current.stop();
    clearInterval(tickRef.current);
    setRecording(false);
  }

  async function onFilePick(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > 25 * 1024 * 1024) return toast.error("Audio must be under 25 MB.");
    await uploadForTranscription(file, file.name);
  }

  async function uploadForTranscription(blob, filename = "session.webm") {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("audio", blob, filename);
      // NOTE: Do NOT set Content-Type manually — axios/browser must include the multipart boundary.
      const { data } = await api.post("/scribe/transcribe", fd);
      const chunk = (data.transcript || "").trim();
      if (!chunk) {
        toast.info("No speech detected. Try recording a bit longer.");
      } else {
        setTranscript((prev) => (prev ? prev + " " : "") + chunk);
        toast.success("Transcription complete");
      }
    } catch (e) {
      toast.error("Transcription failed. Try shorter audio or use a sample.");
    } finally {
      setBusy(false);
    }
  }

  async function generate() {
    if (!transcript.trim()) return toast.info("Add a transcript first — record, or load a sample.");
    setGenBusy(true);
    try {
      const { data } = await api.post("/scribe/soap", { transcript, patient_id: patientId || null, template_id: templateId || null });
      setSoap({
        subjective: data.subjective || "",
        objective: data.objective || "",
        assessment: data.assessment || "",
        plan: data.plan || "",
        confidence: data.confidence || "medium",
        flags: data.flags || [],
      });
      toast.success("SOAP draft ready — please review before signing.");
    } catch (e) {
      toast.error("SOAP generation failed.");
    } finally {
      setGenBusy(false);
    }
  }

  async function sign() {
    if (!patientId) return toast.info("Select a patient to sign the note.");
    try {
      await api.post("/scribe/save", {
        patient_id: patientId,
        subjective: soap.subjective,
        objective: soap.objective,
        assessment: soap.assessment,
        plan: soap.plan,
        signed_by: "Dr. Reyes",
      });
      toast.success("Note signed and filed to patient record.");
    } catch {
      toast.error("Failed to save.");
    }
  }

  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-6">
      <div>
        <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Ambient scribe</div>
        <h1 className="font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight mt-1">
          Record the visit. Sign the note.
        </h1>
        <p className="text-sm text-slate-600 mt-2 max-w-2xl">
          Vetaura transcribes the exam via OpenAI Whisper and drafts a structured SOAP note with Claude Sonnet 5. You review, edit and sign — nothing goes into the record without you.
        </p>
      </div>

      <div className="grid lg:grid-cols-12 gap-6">
        {/* Left: capture */}
        <div className="lg:col-span-5 space-y-4">
          <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold">Patient</div>
              <Badge variant="outline" className="text-[10px] border-emerald-200 text-emerald-800 bg-emerald-50">Optional</Badge>
            </div>
            <Select value={patientId} onValueChange={setPatientId}>
              <SelectTrigger data-testid="scribe-patient-select">
                <SelectValue placeholder="Select a patient (optional)" />
              </SelectTrigger>
              <SelectContent>
                {patients.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name} · {p.species} · {p.breed}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Card>

          <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold">Template</div>
                <div className="text-[11px] text-slate-500">Shape the draft to your house style.</div>
              </div>
              <Link to="/app/scribe/templates" className="text-[11px] text-emerald-700 hover:underline" data-testid="scribe-manage-templates-link">Manage →</Link>
            </div>
            <Select value={templateId || "__none__"} onValueChange={(v) => setTemplateId(v === "__none__" ? "" : v)}>
              <SelectTrigger data-testid="scribe-template-select">
                <SelectValue placeholder="No template (free-form)" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">No template · free-form</SelectItem>
                {templates.map((t) => (
                  <SelectItem key={t.id} value={t.id}>
                    {t.name}{t.is_default ? "" : " · custom"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {templateId && (
              <div className="mt-3 text-[11px] text-slate-500">
                {(templates.find((t) => t.id === templateId) || {}).description}
              </div>
            )}
          </Card>

          <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm relative overflow-hidden">
            <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold mb-3">Live capture</div>
            <div className="flex items-center gap-4">
              <button
                onClick={recording ? stopRec : startRec}
                data-testid="scribe-record-btn"
                className={`h-16 w-16 rounded-full grid place-items-center text-white shadow-md transition-all ${recording ? "bg-rose-600 ring-4 ring-rose-100 animate-pulse" : "bg-emerald-700 hover:bg-emerald-800"}`}
              >
                {recording ? <Square className="h-6 w-6" /> : <Mic className="h-6 w-6" />}
              </button>
              <div>
                <div className="font-mono-clinical text-2xl text-emerald-950">{mm}:{ss}</div>
                <div className="text-xs text-slate-500">{recording ? "Recording…" : busy ? "Transcribing…" : "Tap to start"}</div>
              </div>
              <div className="ml-auto flex items-end gap-1 h-10">
                {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
                  <div
                    key={i}
                    className={`w-1 rounded-full bg-emerald-500 ${recording ? "wave-bar" : ""}`}
                    style={{ height: recording ? "100%" : `${25 + i * 4}%`, animationDelay: `${i * 0.1}s`, opacity: recording ? 1 : 0.3 }}
                  />
                ))}
              </div>
            </div>
            <div className="text-[11px] text-slate-500 mt-3">Audio never leaves the browser except for transcription. Nothing is saved to the record until you sign.</div>
            <div className="mt-4 flex items-center gap-2 pt-3 border-t border-slate-100">
              <input
                ref={fileInputRef}
                type="file"
                accept="audio/*,.wav,.mp3,.m4a,.webm,.ogg,.mp4"
                onChange={onFilePick}
                className="hidden"
                data-testid="scribe-file-input"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={() => fileInputRef.current?.click()}
                disabled={busy || recording}
                data-testid="scribe-upload-btn"
                className="border-emerald-200 text-emerald-800 hover:bg-emerald-50 rounded-full text-xs"
              >
                <Upload className="h-3.5 w-3.5 mr-1.5" /> Upload audio file
              </Button>
              <span className="text-[11px] text-slate-500">WAV, MP3, M4A, WebM · up to 25 MB</span>
            </div>
          </Card>

          <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold">Sample cases</div>
              <RotateCcw className="h-3 w-3 text-slate-400" />
            </div>
            <div className="space-y-2">
              {SAMPLES.map((s, i) => (
                <button
                  key={i}
                  onClick={() => setTranscript(s.text)}
                  data-testid={`scribe-sample-${i}`}
                  className="w-full text-left p-3 rounded-xl border border-slate-100 hover:border-emerald-300 hover:bg-emerald-50/40 transition-all"
                >
                  <div className="font-semibold text-sm text-slate-900">{s.label}</div>
                  <div className="text-xs text-slate-500 line-clamp-2">{s.text}</div>
                </button>
              ))}
            </div>
          </Card>
        </div>

        {/* Right: transcript + SOAP */}
        <div className="lg:col-span-7 space-y-4">
          <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <div>
                <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold">Transcript</div>
                <div className="text-[11px] text-slate-500">Editable — clean up before drafting.</div>
              </div>
              <Button
                onClick={generate}
                disabled={genBusy || !transcript.trim()}
                data-testid="scribe-generate-btn"
                className="bg-emerald-700 hover:bg-emerald-800 text-white rounded-full"
              >
                <Sparkles className="h-4 w-4 mr-2" /> {genBusy ? "Drafting…" : "Draft SOAP"}
              </Button>
            </div>
            <Textarea
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              placeholder="Recorded speech will appear here. Or load a sample from the left."
              rows={7}
              data-testid="scribe-transcript-input"
              className="resize-none"
            />
          </Card>

          <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
              <div>
                <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold">SOAP draft</div>
                <div className="flex items-center gap-2 mt-1">
                  <Wand2 className="h-3 w-3 text-emerald-700" />
                  <div className="text-[11px] text-emerald-800 font-medium">Claude Sonnet 5 · {soap.confidence ? `confidence ${soap.confidence}` : "awaiting draft"}</div>
                </div>
              </div>
              <Button
                onClick={sign}
                disabled={!soap.subjective}
                data-testid="scribe-sign-btn"
                variant="outline"
                className="border-emerald-300 text-emerald-800 hover:bg-emerald-50 rounded-full"
              >
                <FileCheck2 className="h-4 w-4 mr-2" /> Sign & file
              </Button>
            </div>

            {soap.flags?.length > 0 && (
              <div className="mb-4 p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs">
                <div className="font-semibold uppercase tracking-widest mb-1">Verify before signing</div>
                <ul className="list-disc list-inside space-y-0.5">
                  {soap.flags.map((f, i) => <li key={i}>{f}</li>)}
                </ul>
              </div>
            )}

            <div className="grid gap-3">
              {[
                ["subjective", "S — Subjective", "bg-sky-50 border-sky-100 text-sky-900"],
                ["objective", "O — Objective", "bg-emerald-50 border-emerald-100 text-emerald-900"],
                ["assessment", "A — Assessment", "bg-amber-50 border-amber-100 text-amber-900"],
                ["plan", "P — Plan", "bg-purple-50 border-purple-100 text-purple-900"],
              ].map(([key, label, cls]) => (
                <div key={key}>
                  <div className={`inline-flex px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-widest border ${cls} mb-1.5`}>{label}</div>
                  <Textarea
                    value={soap[key]}
                    onChange={(e) => setSoap({ ...soap, [key]: e.target.value })}
                    rows={key === "objective" || key === "plan" ? 4 : 3}
                    data-testid={`scribe-${key}`}
                    className="resize-none"
                  />
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
