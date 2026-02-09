import { useEffect, useMemo, useRef, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

const PIPELINE_STEPS = [
  "Parsing document",
  "Structuring sections",
  "Making conversational",
  "Generating audio",
  "Assembling episode",
];

const LANGUAGES = ["Hindi", "Telugu", "Tamil", "English"];
const VOICES = [
  "Aditya",
  "Rahul",
  "Rohan",
  "Amit",
  "Dev",
  "Ratan",
  "Varun",
  "Manan",
  "Sumit",
  "Kabir",
  "Aayan",
  "Shubh",
  "Ashutosh",
  "Advait",
  "Anand",
  "Tarun",
  "Sunny",
  "Mani",
  "Gokul",
  "Vijay",
  "Mohit",
  "Rehan",
  "Soham",
  "Ritu",
  "Priya",
  "Neha",
  "Pooja",
  "Simran",
  "Kavya",
  "Ishita",
  "Shreya",
  "Roopa",
  "Amelia",
  "Sophia",
  "Tanya",
  "Shruti",
  "Suhani",
  "Kavitha",
  "Rupali",
];

function App() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [language, setLanguage] = useState(LANGUAGES[0]);
  const [voice, setVoice] = useState(VOICES[0]);
  const [useDuo, setUseDuo] = useState(false);
  const [voiceSecondary, setVoiceSecondary] = useState(VOICES[1] || VOICES[0]);
  const [length, setLength] = useState("full");
  const [llmProvider, setLlmProvider] = useState("anthropic");
  const [llmModel, setLlmModel] = useState(
    "anthropic/claude-3-5-sonnet-20241022"
  );
  const [llmApiKey, setLlmApiKey] = useState("");
  const [llmMaxTokens, setLlmMaxTokens] = useState("4096");
  const [showLlm, setShowLlm] = useState(false);
  const [sarvamKey, setSarvamKey] = useState("");
  const [showSarvam, setShowSarvam] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showTranscript, setShowTranscript] = useState(false);

  const sourceType = useMemo(() => {
    if (file) return "file";
    if (url.trim().length > 0) return "url";
    return "text";
  }, [file, url]);

  useEffect(() => {
    if (!jobId) return;

    let alive = true;
    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/jobs/${jobId}`);
        if (!res.ok) return;
        const data = await res.json();
        if (alive) setJobStatus(data);
        if (data.status === "completed" || data.status === "failed") {
          return;
        }
      } catch {
        // ignore polling errors
      }
    };

    poll();
    const interval = setInterval(poll, 2000);
    return () => {
      alive = false;
      clearInterval(interval);
    };
  }, [jobId]);

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (event.dataTransfer.files && event.dataTransfer.files[0]) {
      setFile(event.dataTransfer.files[0]);
      setText("");
      setUrl("");
    }
  };

  const handleSubmit = async () => {
    setError(null);

    if (!file && text.trim().length === 0 && url.trim().length === 0) {
      setError("Add a file, text, or URL to continue.");
      return;
    }

    setLoading(true);
    try {
      const form = new FormData();
      form.append("source_type", sourceType);
      form.append("language", language);
      form.append("voice", voice);
      if (useDuo && voiceSecondary) {
        form.append("voice_secondary", voiceSecondary);
      }
      if (llmApiKey.trim()) {
        form.append("llm_api_key", llmApiKey.trim());
      }
      if (llmProvider.trim()) {
        form.append("llm_provider", llmProvider.trim());
      }
      if (llmModel.trim()) {
        form.append("llm_model", llmModel.trim());
      }
      if (llmMaxTokens.trim()) {
        form.append("llm_max_tokens", llmMaxTokens.trim());
      }
      if (sarvamKey.trim()) {
        form.append("sarvam_api_key", sarvamKey.trim());
      }
      form.append("length", length);

      if (sourceType === "file" && file) {
        form.append("file", file);
      } else if (sourceType === "url") {
        form.append("source_url", url);
      } else {
        form.append("source_text", text);
      }

      const res = await fetch(`${API_BASE}/api/jobs`, {
        method: "POST",
        body: form,
      });

      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || "Failed to create job");
      }

      const data = await res.json();
      setJobId(data.job_id);
      setJobStatus(null);
    } catch (err: any) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const stepStatus = (name: string) => {
    if (!jobStatus?.steps) return "pending";
    const match = jobStatus.steps.find((step: any) => step.name === name);
    return match?.status || "pending";
  };

  const progressPercent = useMemo(() => {
    if (!jobStatus?.steps) return 0;
    const completed = jobStatus.steps.filter((s: any) => s.status === "done").length;
    const current = jobStatus.steps.find((s: any) => s.status === "running");
    let percent = (completed / PIPELINE_STEPS.length) * 100;
    if (current) percent += 10; // Bump for running step
    return Math.min(percent, 100);
  }, [jobStatus]);

  return (
    <div className="page">
      <header className="hero">
        <div className="hero-title">Create-to-Listen</div>
        <p className="hero-subtitle">
          Turn any English content into a calm, conversational podcast in Indian
          languages.
        </p>
      </header>

      <section className="panel">
        <div
          className="dropzone"
          onDragOver={(event) => event.preventDefault()}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            hidden
            onChange={(event) => {
              const selected = event.target.files?.[0] || null;
              setFile(selected);
              if (selected) {
                setText("");
                setUrl("");
              }
            }}
          />
          <div className="dropzone-label">Drag & Drop File</div>
          <div className="dropzone-meta">
            {file ? `Selected: ${file.name}` : "PDF, DOCX, TXT, MD"}
          </div>
        </div>

        <div className="input-grid">
          <div className="input-block">
            <label>Paste Text</label>
            <textarea
              value={text}
              onChange={(event) => {
                setText(event.target.value);
                if (event.target.value) setFile(null);
              }}
              placeholder="Paste English content here"
            />
          </div>
          <div className="input-block">
            <label>Paste URL</label>
            <input
              type="url"
              value={url}
              onChange={(event) => {
                setUrl(event.target.value);
                if (event.target.value) setFile(null);
              }}
              placeholder="https://"
            />
          </div>
        </div>

        <div className="options">
          <div className="option">
            <label>Output Type</label>
            <div className="pill">Conversational Podcast</div>
          </div>
          <div className="option">
            <label>Input Language</label>
            <select value={language} onChange={(e) => setLanguage(e.target.value)}>
              {LANGUAGES.map((lang) => (
                <option key={lang} value={lang}>
                  {lang}
                </option>
              ))}
            </select>
          </div>
          <div className="option">
            <label>Voice</label>
            <select value={voice} onChange={(e) => setVoice(e.target.value)}>
              {VOICES.map((voiceOption) => (
                <option key={voiceOption} value={voiceOption}>
                  {voiceOption}
                </option>
              ))}
            </select>
          </div>
          <div className="option">
            <label>Two Voices</label>
            <div className="pill-group">
              <button
                className={useDuo ? "pill active" : "pill"}
                onClick={() => setUseDuo(true)}
              >
                Duo
              </button>
              <button
                className={!useDuo ? "pill active" : "pill"}
                onClick={() => setUseDuo(false)}
              >
                Solo
              </button>
            </div>
          </div>
          {useDuo && (
            <div className="option">
              <label>Secondary Voice</label>
              <select
                value={voiceSecondary}
                onChange={(e) => setVoiceSecondary(e.target.value)}
              >
                {VOICES.map((voiceOption) => (
                  <option key={voiceOption} value={voiceOption}>
                    {voiceOption}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="option">
            <label>Detail Level</label>
            <div className="pill-group">
              <button
                className={length === "full" ? "pill active" : "pill"}
                onClick={() => setLength("full")}
              >
                Deep Dive (Detailed)
              </button>
              <button
                className={
                  length === "slightly-shorter" ? "pill active" : "pill"
                }
                onClick={() => setLength("slightly-shorter")}
              >
                Brief Summary
              </button>
            </div>
          </div>
        </div>

        <div className="llm-block">
          <div className="llm-header">
            <div className="panel-title">LLM Settings (Optional)</div>
            <button className="pill" onClick={() => setShowLlm((prev) => !prev)}>
              {showLlm ? "Hide" : "Show"}
            </button>
          </div>
          {showLlm && (
            <div className="llm-grid">
              <div className="option">
                <label>Provider</label>
                <select
                  value={llmProvider}
                  onChange={(e) => setLlmProvider(e.target.value)}
                >
                  <option value="anthropic">Anthropic</option>
                  <option value="openai">OpenAI</option>
                </select>
              </div>
              <div className="option">
                <label>Model</label>
                <input
                  value={llmModel}
                  onChange={(e) => setLlmModel(e.target.value)}
                  placeholder="anthropic/claude-3-5-sonnet-20241022"
                />
              </div>
              <div className="option">
                <label>API Key</label>
                <input
                  type="password"
                  value={llmApiKey}
                  onChange={(e) => setLlmApiKey(e.target.value)}
                  placeholder="Paste key (not stored)"
                />
              </div>
              <div className="option">
                <label>Max Tokens</label>
                <input
                  value={llmMaxTokens}
                  onChange={(e) => setLlmMaxTokens(e.target.value)}
                  placeholder="4096"
                />
              </div>
            </div>
          )}
          <div className="llm-note">
            Keys are used only for the current run and never stored on disk.
          </div>
        </div>

        <div className="llm-block">
          <div className="llm-header">
            <div className="panel-title">Sarvam API (Optional)</div>
            <button
              className="pill"
              onClick={() => setShowSarvam((prev) => !prev)}
            >
              {showSarvam ? "Hide" : "Show"}
            </button>
          </div>
          {showSarvam && (
            <div className="llm-grid">
              <div className="option">
                <label>API Key</label>
                <input
                  type="password"
                  value={sarvamKey}
                  onChange={(e) => setSarvamKey(e.target.value)}
                  placeholder="Paste key (not stored)"
                />
              </div>
            </div>
          )}
          <div className="llm-note">
            Key is used only for the current run and never stored on disk.
          </div>
        </div>

        {error && <div className="error">{error}</div>}

        <div className="cta-row">
          <button className="cta" onClick={handleSubmit} disabled={loading}>
            {loading ? "Generating..." : "Generate Podcast"}
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel-title">Generation Progress</div>

        <div className="progress-bar-container">
          <div
            className="progress-bar-fill"
            style={{ width: `${progressPercent}%` }}
          />
        </div>

        <div className="progress-grid">
          {PIPELINE_STEPS.map((step) => (
            <div key={step} className={`progress-card ${stepStatus(step)}`}>
              <div className="progress-title">{step}</div>
              <div className="progress-status">{stepStatus(step)}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-title">Listen</div>
        <div className="player">
          <div className="player-meta">
            <div className="player-title">Create-to-Listen Episode</div>
            <div className="player-subtitle">
              {jobStatus?.status === "completed"
                ? "Audio ready to stream"
                : "Audio will appear when generation completes"}
            </div>
          </div>
          <div className="player-controls">
            <audio
              controls
              src={
                jobStatus?.artifacts?.audio_path
                  ? `${API_BASE}/api/jobs/${jobId}/artifact?name=audio.wav`
                  : undefined
              }
            />
          </div>
          {jobStatus?.artifacts?.audio_path && (
            <a
              className="download"
              href={`${API_BASE}/api/jobs/${jobId}/artifact?name=audio.wav`}
            >
              Download Audio
            </a>
          )}
        </div>

        <div className="transcript">
          <button
            className="pill"
            onClick={() => setShowTranscript((prev) => !prev)}
          >
            {showTranscript ? "Hide Transcript" : "Show Transcript"}
          </button>
          {showTranscript && (
            <pre className="transcript-body">
              {jobStatus?.artifacts?.transcript_preview ||
                "Transcript preview will appear here."}
            </pre>
          )}
        </div>
      </section>
    </div>
  );
}

export default App;
