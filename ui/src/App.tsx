import { useEffect, useMemo, useRef, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

const PIPELINE_STEPS = [
  "Parsing document",
  "Structuring sections",
  "Making conversational",
  "Generating audio",
  "Assembling episode",
];

const LANGUAGES = [
  "Hindi",
  "Hinglish (Gen Z)",
  "English",
  "Tamil",
  "Telugu",
  "Kannada",
  "Malayalam",
  "Gujarati",
  "Marathi",
  "Bengali",
  "Punjabi",
  "Odia",
];
const VOICES = [
  "Shubh",
  "Ritu",
  "Amit",
  "Sumit",
  "Pooja",
  "Manan",
  "Simran",
  "Rahul",
  "Kavya",
  "Ratan",
  "Priya",
  "Ishita",
  "Shreya",
  "Shruti",
];

const STORAGE_KEY = "sarvam-episodes";

const MAIN_NAV = [
  { id: "listen-now", label: "Listen Now" },
  { id: "browse", label: "Browse" },
  { id: "library", label: "Library" },
  { id: "studio", label: "Studio" },
];

const LIBRARY_NAV = [
  { id: "library-downloads", label: "Downloads" },
  { id: "library-recent", label: "Recent" },
  { id: "library-made", label: "Made Podcasts" },
];

const BROWSE_CARDS = [
  {
    title: "Deep Dives",
    subtitle: "Long-form explainers and research",
    tone: "tone-0",
  },
  {
    title: "Daily Brief",
    subtitle: "Quick updates in 2-5 minutes",
    tone: "tone-1",
  },
  {
    title: "Tech Reviews",
    subtitle: "Product and paper breakdowns",
    tone: "tone-2",
  },
  {
    title: "Culture & History",
    subtitle: "Narrative storytelling",
    tone: "tone-3",
  },
];

type Episode = {
  id: string;
  title: string;
  subtitle: string;
  language: string;
  voice: string;
  length: string;
  createdAt: string;
  audioUrl?: string;
  transcript?: string;
};

const loadEpisodes = (): Episode[] => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Episode[];
    if (!Array.isArray(parsed)) return [];
    return parsed;
  } catch {
    return [];
  }
};

const saveEpisodes = (episodes: Episode[]) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(episodes));
  } catch {
    // ignore storage errors
  }
};

const formatDateTime = (value: string) => {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
};

const summarizeText = (value: string) => {
  const words = value.trim().split(/\s+/).slice(0, 8);
  if (words.length === 0) return "Untitled";
  const suffix = value.trim().split(/\s+/).length > 8 ? "..." : "";
  return `${words.join(" ")}${suffix}`;
};

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
  const [llmProvider, setLlmProvider] = useState("openai");
  const [llmModel, setLlmModel] = useState("openai/gpt-4o");
  const [llmApiKey, setLlmApiKey] = useState("");
  const [llmMaxTokens, setLlmMaxTokens] = useState("8192");
  const [showLlm, setShowLlm] = useState(false);
  const [sarvamKey, setSarvamKey] = useState("");
  const [showSarvam, setShowSarvam] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showTranscript, setShowTranscript] = useState(false);
  const [jobStartedAt, setJobStartedAt] = useState<number | null>(null);
  const [lastStatusAt, setLastStatusAt] = useState<number | null>(null);
  const [pollingActive, setPollingActive] = useState(true);
  const [episodes, setEpisodes] = useState<Episode[]>(() => loadEpisodes());
  const [nowPlayingId, setNowPlayingId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sourceSummary, setSourceSummary] = useState("Untitled");
  const [activeSection, setActiveSection] = useState("listen-now");
  const [newEpisodeId, setNewEpisodeId] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const sourceType = useMemo(() => {
    if (file) return "file";
    if (url.trim().length > 0) return "url";
    return "text";
  }, [file, url]);

  const progressPercent = useMemo(() => {
    if (!jobStatus?.steps) return 0;
    const completed = jobStatus.steps.filter((s: any) => s.status === "done").length;
    const current = jobStatus.steps.find((s: any) => s.status === "running");
    let percent = (completed / PIPELINE_STEPS.length) * 100;
    if (current) percent += 10;
    return Math.min(percent, 100);
  }, [jobStatus]);

  const latestAudioUrl = useMemo(() => {
    if (jobStatus?.artifacts?.audio_path && jobId) {
      return `${API_BASE}/api/jobs/${jobId}/artifact?name=audio.wav`;
    }
    return undefined;
  }, [jobStatus, jobId]);

  const nowPlaying = useMemo(() => {
    if (nowPlayingId) {
      return episodes.find((episode) => episode.id === nowPlayingId) || null;
    }
    return null;
  }, [episodes, nowPlayingId]);

  const filteredEpisodes = useMemo(() => {
    if (!search.trim()) return episodes;
    const query = search.toLowerCase();
    return episodes.filter((episode) => {
      return (
        episode.title.toLowerCase().includes(query) ||
        episode.subtitle.toLowerCase().includes(query)
      );
    });
  }, [episodes, search]);

  const recentEpisodes = useMemo(() => episodes.slice(0, 3), [episodes]);

  useEffect(() => {
    if (!jobId) return;
    if (!pollingActive) return;

    let alive = true;
    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/jobs/${jobId}`);
        if (res.status === 404) {
          setJobId(null);
          setJobStatus(null);
          setToastMessage("Previous job expired. Start a new Deep Dive.");
          return;
        }
        if (!res.ok) return;
        const data = await res.json();
        if (alive) {
          setJobStatus(data);
          setLastStatusAt(Date.now());
        }
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
  }, [jobId, pollingActive]);

  useEffect(() => {
    if (!jobId || !jobStatus) return;
    if (jobStatus.status !== "running") return;
    if (!lastStatusAt || !jobStartedAt) return;

    const interval = setInterval(() => {
      const elapsed = Date.now() - lastStatusAt;
      if (elapsed > 15 * 60 * 1000) {
        setError("Job appears stuck. Please restart the job.");
        setPollingActive(false);
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [jobId, jobStatus, lastStatusAt, jobStartedAt]);

  useEffect(() => {
    if (!jobId || jobStatus?.status !== "completed") return;
    if (episodes.some((episode) => episode.id === jobId)) return;

    const audioUrl = latestAudioUrl;
    const nextEpisode: Episode = {
      id: jobId,
      title: sourceSummary,
      subtitle: `${language} conversation`,
      language,
      voice: useDuo ? `${voice} + ${voiceSecondary}` : voice,
      length: length === "full" ? "Deep Dive" : "Brief",
      createdAt: new Date().toISOString(),
      audioUrl,
      transcript: jobStatus?.artifacts?.transcript_preview || "",
    };

    setEpisodes((prev) => {
      const next = [nextEpisode, ...prev];
      saveEpisodes(next);
      return next;
    });

    if (audioUrl) {
      setNowPlayingId(jobId);
    }

    setNewEpisodeId(jobId);
    setToastMessage(`Created ${sourceSummary}`);

    const clearNew = setTimeout(() => setNewEpisodeId(null), 3200);
    const clearToast = setTimeout(() => setToastMessage(null), 4200);
    return () => {
      clearTimeout(clearNew);
      clearTimeout(clearToast);
    };
  }, [
    jobId,
    jobStatus,
    episodes,
    language,
    length,
    latestAudioUrl,
    sourceSummary,
    useDuo,
    voice,
    voiceSecondary,
  ]);

  useEffect(() => {
    const sections = Array.from(
      document.querySelectorAll<HTMLElement>("[data-section]")
    );
    if (!sections.length) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible[0]) {
          const id = visible[0].target.getAttribute("data-section");
          if (id) setActiveSection(id);
        }
      },
      { rootMargin: "-20% 0px -60% 0px", threshold: [0.1, 0.3, 0.6] }
    );

    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, []);

  const stepStatus = (name: string) => {
    if (!jobStatus?.steps) return "pending";
    const match = jobStatus.steps.find((step: any) => step.name === name);
    return match?.status || "pending";
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (event.dataTransfer.files && event.dataTransfer.files[0]) {
      setFile(event.dataTransfer.files[0]);
      setText("");
      setUrl("");
    }
  };

  const buildSourceSummary = () => {
    if (file) return file.name;
    if (url.trim()) {
      try {
        const host = new URL(url).hostname.replace("www.", "");
        return host || "Website";
      } catch {
        return url;
      }
    }
    if (text.trim()) return summarizeText(text);
    return "Untitled";
  };

  const handleSubmit = async () => {
    setError(null);

    if (!file && text.trim().length === 0 && url.trim().length === 0) {
      setError("Add a file, text, or URL to continue.");
      return;
    }

    const summary = buildSourceSummary();
    setSourceSummary(summary);

    setLoading(true);
    try {
      const form = new FormData();
      form.append("source_type", sourceType);
      form.append("language", language);
      form.append("voice", voice);
      if (useDuo && voiceSecondary) {
        form.append("voice_secondary", voiceSecondary);
      }
      if (showLlm || llmApiKey.trim()) {
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
      setJobStartedAt(Date.now());
      setLastStatusAt(Date.now());
      setPollingActive(true);
    } catch (err: any) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const resetJob = () => {
    setJobId(null);
    setJobStatus(null);
    setError(null);
    setShowTranscript(false);
    setPollingActive(true);
    setJobStartedAt(null);
    setLastStatusAt(null);
  };

  const scrollToSection = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  };

  const isMainActive = (id: string) => {
    if (id === "library") return activeSection.startsWith("library");
    return activeSection === id;
  };

  return (
    <div className="app">
      <div className="shell">
        <aside className="sidebar">
          <div className="brand">
            <div className="brand-mark" />
            <div>
              <div className="brand-name">Sarvamcast</div>
              <div className="brand-subtitle">Podcastify AI</div>
            </div>
          </div>
          <nav className="nav">
            {MAIN_NAV.map((item) => (
              <button
                key={item.id}
                className={`nav-item ${isMainActive(item.id) ? "active" : ""}`}
                onClick={() => scrollToSection(item.id)}
                type="button"
              >
                {item.label}
              </button>
            ))}
          </nav>
          <div className="nav-section">
            <div className="nav-title">Library</div>
            {LIBRARY_NAV.map((item) => (
              <button
                key={item.id}
                className={`nav-item ${
                  activeSection === item.id ? "active" : ""
                }`}
                onClick={() => scrollToSection(item.id)}
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>
          <div className="sidebar-card tilt-card">
            <div className="panel-title">Production Queue</div>
            <div className="progress-bar-container">
              <div
                className="progress-bar-fill"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
            <div className="progress-list">
              {PIPELINE_STEPS.map((step) => (
                <div key={step} className={`progress-item ${stepStatus(step)}`}>
                  <span>{step}</span>
                  <span className="progress-state">{stepStatus(step)}</span>
                </div>
              ))}
            </div>
          </div>
        </aside>

        <main className="main">
          <header className="topbar">
            <div className="search">
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search your library"
              />
            </div>
            <button className="cta" onClick={() => scrollToSection("studio")}>
              Create Podcast
            </button>
          </header>

          {toastMessage && (
            <div className="creation-toast">
              <div className="toast-title">Podcast created</div>
              <div className="toast-subtitle">{toastMessage}</div>
            </div>
          )}

          <section
            id="listen-now"
            data-section="listen-now"
            className="section fade-up"
          >
            <div className="section-header">
              <div>
                <div className="section-title">Listen Now</div>
                <div className="section-subtitle">
                  Your newest generations, ready to play.
                </div>
              </div>
            </div>

            <div className="listen-grid">
              <div className="hero-card tilt-card">
                <div>
                  <div className="hero-title">Create-to-Listen</div>
                  <p className="hero-subtitle">
                    Turn any document into a calm, conversational podcast in
                    Indian languages. Built for deep understanding and natural
                    voices.
                  </p>
                  <div className="chip-row">
                    <span className="chip">Smart ingestion</span>
                    <span className="chip">Deep dive scripts</span>
                    <span className="chip">Bulbul v3 voices</span>
                    <span className="chip">Multi-language</span>
                  </div>
                </div>
                <div className="hero-metrics">
                  <div className="metric">
                    <div className="metric-value">10-15 min</div>
                    <div className="metric-label">Deep dive</div>
                  </div>
                  <div className="metric">
                    <div className="metric-value">2-5 min</div>
                    <div className="metric-label">Brief summary</div>
                  </div>
                  <div className="metric">
                    <div className="metric-value">11+</div>
                    <div className="metric-label">Languages</div>
                  </div>
                </div>
              </div>

              <div className="listen-stack">
                <div className="now-card tilt-card">
                  <div className="now-title">
                    {nowPlaying?.title || "Create-to-Listen Episode"}
                  </div>
                  <div className="now-subtitle">
                    {jobStatus?.status === "completed"
                      ? "Audio ready to stream"
                      : "Audio will appear when generation completes"}
                  </div>
                  <div className="now-controls">
                    <audio controls src={nowPlaying?.audioUrl || latestAudioUrl} />
                    {(nowPlaying?.audioUrl || latestAudioUrl) && (
                      <a
                        className="download"
                        href={nowPlaying?.audioUrl || latestAudioUrl}
                      >
                        Download
                      </a>
                    )}
                  </div>
                </div>

                <div className="progress-panel tilt-card">
                  <div className="panel-title">In Progress</div>
                  <div className="progress-bar-container">
                    <div
                      className="progress-bar-fill"
                      style={{ width: `${progressPercent}%` }}
                    />
                  </div>
                  <div className="progress-grid">
                    {PIPELINE_STEPS.map((step) => (
                      <div
                        key={step}
                        className={`progress-card ${stepStatus(step)}`}
                      >
                        <div className="progress-title">{step}</div>
                        <div className="progress-status">{stepStatus(step)}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="transcript-block">
              <div className="section-header">
                <div>
                  <div className="section-title">Transcript</div>
                  <div className="section-subtitle">
                    Preview the latest conversation while it is generating.
                  </div>
                </div>
                <button
                  className="pill"
                  onClick={() => setShowTranscript((prev) => !prev)}
                  type="button"
                >
                  {showTranscript ? "Hide" : "Show"}
                </button>
              </div>
              {showTranscript && (
                <pre className="transcript-body">
                  {jobStatus?.artifacts?.transcript_preview ||
                    "Transcript preview will appear here."}
                </pre>
              )}
            </div>
          </section>

          <section id="browse" data-section="browse" className="section fade-up">
            <div className="section-header">
              <div>
                <div className="section-title">Browse</div>
                <div className="section-subtitle">
                  Spark a new generation with one click.
                </div>
              </div>
            </div>
            <div className="browse-grid">
              {BROWSE_CARDS.map((card) => (
                <button
                  key={card.title}
                  className={`browse-card tilt-card ${card.tone}`}
                  onClick={() => scrollToSection("studio")}
                  type="button"
                >
                  <div className="browse-title">{card.title}</div>
                  <div className="browse-subtitle">{card.subtitle}</div>
                  <div className="browse-action">Create with this style</div>
                </button>
              ))}
            </div>
          </section>

          <section id="library" className="section fade-up">
            <div className="section-header">
              <div>
                <div className="section-title">Library</div>
                <div className="section-subtitle">
                  Everything you have generated, organized in one place.
                </div>
              </div>
              <div className="section-meta">{filteredEpisodes.length} episodes</div>
            </div>

            <div
              id="library-downloads"
              data-section="library-downloads"
              className="library-block"
            >
              <div className="library-title">Downloads</div>
              <div className="library-body empty">
                Downloads will show up once you save episodes for offline use.
              </div>
            </div>

            <div
              id="library-recent"
              data-section="library-recent"
              className="library-block"
            >
              <div className="library-title">Recent</div>
              <div className="recent-list">
                {recentEpisodes.length === 0 && (
                  <div className="empty">No recent episodes yet.</div>
                )}
                {recentEpisodes.map((episode) => (
                  <button
                    key={episode.id}
                    className="recent-card tilt-card"
                    onClick={() => setNowPlayingId(episode.id)}
                    type="button"
                  >
                    <div className="recent-title">{episode.title}</div>
                    <div className="recent-subtitle">{episode.subtitle}</div>
                    <div className="recent-meta">
                      {episode.language} · {episode.length}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div
              id="library-made"
              data-section="library-made"
              className="library-block"
            >
              <div className="library-title">Made Podcasts</div>
              <div className="episode-grid">
                {filteredEpisodes.length === 0 && (
                  <div className="empty">No podcasts yet. Start in Studio.</div>
                )}
                {filteredEpisodes.map((episode, index) => (
                  <button
                    key={episode.id}
                    className={`episode-card tilt-card ${
                      episode.id === newEpisodeId ? "new" : ""
                    }`}
                    onClick={() => setNowPlayingId(episode.id)}
                    type="button"
                  >
                    <div className={`episode-cover tone-${index % 5}`} />
                    <div className="episode-info">
                      <div className="episode-title">{episode.title}</div>
                      <div className="episode-subtitle">{episode.subtitle}</div>
                      <div className="episode-meta">
                        <span>{episode.language}</span>
                        <span>{episode.voice}</span>
                        <span>{episode.length}</span>
                      </div>
                      <div className="episode-time">
                        {formatDateTime(episode.createdAt)}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </section>
        </main>

        <aside className="studio" id="studio" data-section="studio">
          <div className="studio-card tilt-card">
            <div className="panel-title">Studio</div>
            <p className="panel-subtitle">
              Paste a URL, upload a file, or drop raw text to start.
            </p>
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
              <div className="dropzone-label">Drag and drop file</div>
              <div className="dropzone-meta">
                {file ? `Selected: ${file.name}` : "PDF, DOCX, TXT, MD"}
              </div>
            </div>

            <div className="input-block">
              <label>Paste text</label>
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

            <div className="options">
              <div className="option">
                <label>Language</label>
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
                <label>Two voices</label>
                <div className="pill-group">
                  <button
                    className={useDuo ? "pill active" : "pill"}
                    onClick={() => setUseDuo(true)}
                    type="button"
                  >
                    Duo
                  </button>
                  <button
                    className={!useDuo ? "pill active" : "pill"}
                    onClick={() => setUseDuo(false)}
                    type="button"
                  >
                    Solo
                  </button>
                </div>
              </div>
              {useDuo && (
                <div className="option">
                  <label>Secondary voice</label>
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
                <label>Detail level</label>
                <div className="pill-group">
                  <button
                    className={length === "full" ? "pill active" : "pill"}
                    onClick={() => setLength("full")}
                    type="button"
                  >
                    Deep dive
                  </button>
                  <button
                    className={length === "slightly-shorter" ? "pill active" : "pill"}
                    onClick={() => setLength("slightly-shorter")}
                    type="button"
                  >
                    Brief
                  </button>
                </div>
              </div>
            </div>

            {error && <div className="error">{error}</div>}

            <div className="cta-row">
              <button className="cta" onClick={handleSubmit} disabled={loading}>
                {loading ? "Generating..." : "Generate podcast"}
              </button>
              {jobId && (
                <button className="pill" onClick={resetJob} type="button">
                  Reset Job
                </button>
              )}
            </div>
          </div>

          <div className="studio-card tilt-card">
            <div className="llm-header">
              <div>
                <div className="panel-title">LLM Settings</div>
                <div className="panel-subtitle">Optional overrides per run.</div>
              </div>
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
                  <option value="openai">OpenAI</option>
                  <option value="gemini">Gemini</option>
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
                  <label>API key</label>
                  <input
                    type="password"
                    value={llmApiKey}
                    onChange={(e) => setLlmApiKey(e.target.value)}
                    placeholder="Paste key (not stored)"
                  />
                </div>
                <div className="option">
                  <label>Max tokens</label>
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

          <div className="studio-card tilt-card">
            <div className="llm-header">
              <div>
                <div className="panel-title">Sarvam API</div>
                <div className="panel-subtitle">Optional override per run.</div>
              </div>
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
                  <label>API key</label>
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
        </aside>
      </div>

      <div className="now-playing">
        <div>
          <div className="now-title">
            {nowPlaying?.title || "Create-to-Listen Episode"}
          </div>
          <div className="now-subtitle">
            {jobStatus?.status === "completed"
              ? "Audio ready to stream"
              : "Audio will appear when generation completes"}
          </div>
        </div>
        <div className="now-controls">
          <audio controls src={nowPlaying?.audioUrl || latestAudioUrl} />
          {(nowPlaying?.audioUrl || latestAudioUrl) && (
            <a className="download" href={nowPlaying?.audioUrl || latestAudioUrl}>
              Download
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
