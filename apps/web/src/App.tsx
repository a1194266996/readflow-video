import { useEffect, useState } from "react";
import { FileText, Play, RefreshCw, WandSparkles } from "lucide-react";
import { createRoot } from "react-dom/client";
import "./styles.css";

function getApiBaseUrl() {
  const configured = import.meta.env.VITE_API_URL;
  if (configured) {
    return configured;
  }
  return `${window.location.protocol}//${window.location.hostname}:8010`;
}

const API = getApiBaseUrl();

type Scene = {
  index: number;
  title: string;
  body: string;
  duration: number;
};

type Project = {
  title: string;
  prompt: string;
  style: string;
  scenes: Scene[];
};

type AiStatus = {
  ready: boolean;
  model: string;
  reason?: string;
  device?: string | null;
};

type SystemStatus = {
  cpu_percent: number | null;
  memory: {
    percent: number;
    used_mb: number;
    total_mb: number;
  } | null;
  gpu: {
    utilization: number;
    memory_used_mb: number;
    memory_total_mb: number;
    memory_percent: number;
    temperature: number;
    power_w: number;
  } | null;
};

type RenderJob = {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  message: string;
  progress: number;
  title: string;
  prompt: string;
  engine: string;
  preview_url?: string | null;
  video_url?: string | null;
  error?: string | null;
  created_at: string;
  updated_at: string;
};

function App() {
  const [prompt, setPrompt] = useState("30岁以后一定要明白的5个人生道理");
  const [project, setProject] = useState<Project | null>(null);
  const [busy, setBusy] = useState(false);
  const [character, setCharacter] = useState("presenter");
  const [karaoke, setKaraoke] = useState(true);
  const [aiEngine, setAiEngine] = useState("wan");
  const [aiStatus, setAiStatus] = useState<AiStatus | null>(null);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [jobs, setJobs] = useState<RenderJob[]>([]);
  const [selectedJobId, setSelectedJobId] = useState("");

  useEffect(() => {
    fetch(`${API}/api/ai/status`)
      .then((res) => res.json())
      .then(setAiStatus)
      .catch(() => setAiStatus(null));
  }, []);

  async function loadJobs() {
    const res = await fetch(`${API}/api/jobs`);
    const data = await res.json();
    setJobs(data.jobs || []);
    if (!selectedJobId && data.jobs?.length) {
      setSelectedJobId(data.jobs[0].id);
    }
  }

  async function loadSystemStatus() {
    const res = await fetch(`${API}/api/system/status`);
    setSystemStatus(await res.json());
  }

  useEffect(() => {
    loadJobs().catch(() => undefined);
    const timer = window.setInterval(() => loadJobs().catch(() => undefined), 2000);
    return () => window.clearInterval(timer);
  }, [selectedJobId]);

  useEffect(() => {
    loadSystemStatus().catch(() => undefined);
    const timer = window.setInterval(() => loadSystemStatus().catch(() => undefined), 2000);
    return () => window.clearInterval(timer);
  }, []);

  const selectedJob = jobs.find((job) => job.id === selectedJobId) || jobs[0];
  const previewUrl = selectedJob?.video_url || selectedJob?.preview_url;
  const isVideoPreview = Boolean(previewUrl?.endsWith(".mp4"));

  async function generateScript() {
    setBusy(true);
    try {
      const sceneCount = aiEngine === "wan" ? 3 : aiEngine === "svd" ? 3 : 6;
      const res = await fetch(`${API}/api/script`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, scene_count: sceneCount, style: "小红书干货" }),
      });
      setProject(await res.json());
    } finally {
      setBusy(false);
    }
  }

  async function renderVideo() {
    setBusy(true);
    try {
      const renderProject = aiEngine === "wan" && project
        ? { ...project, scenes: project.scenes.slice(0, 1) }
        : aiEngine === "svd" && project
        ? { ...project, scenes: project.scenes.slice(0, 3) }
        : project;
      const res = await fetch(`${API}/api/render`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          project: renderProject,
          scene_count: aiEngine === "wan" ? 3 : aiEngine === "svd" ? 3 : 6,
          with_tts: true,
          animated: true,
          ai_engine: aiEngine,
          character,
          karaoke,
          visual_style: "story",
        }),
      });
      const data = await res.json();
      setSelectedJobId(data.job.id);
      await loadJobs();
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="app">
      <section className="workspace">
        <aside className="panel">
          <div className="brand">Readflow Video</div>
          <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} />
          <div className="controls">
            <label>
              视频引擎
              <select value={aiEngine} onChange={(event) => setAiEngine(event.target.value)}>
                <option value="template">模板动画</option>
                <option value="wan">Wan2.2 文生视频</option>
                <option value="svd">SVD 图生视频</option>
              </select>
            </label>
            {(aiEngine === "wan" || aiEngine === "svd") && aiStatus && (
              <div className={aiStatus.ready ? "status ready" : "status"}>
                {aiStatus.ready ? `${aiEngine.toUpperCase()} 就绪：${aiStatus.device}` : `${aiEngine.toUpperCase()} 未就绪：${aiStatus.reason}`}
              </div>
            )}
            <label>
              角色
              <select value={character} onChange={(event) => setCharacter(event.target.value)}>
                <option value="presenter">口播人物</option>
                <option value="coach">知识讲解</option>
              </select>
            </label>
            <label className="check">
              <input type="checkbox" checked={karaoke} onChange={(event) => setKaraoke(event.target.checked)} />
              跟读高亮
            </label>
          </div>
          <div className="actions">
            <button onClick={generateScript} disabled={busy}>
              <FileText size={18} />
              生成文案
            </button>
            <button className="primary" onClick={renderVideo} disabled={busy}>
              <WandSparkles size={18} />
              创建任务
            </button>
          </div>
          <section className="meter-panel">
            <div className="section-title">机器状态</div>
            <Meter label="CPU" value={systemStatus?.cpu_percent ?? 0} detail={`${Math.round(systemStatus?.cpu_percent ?? 0)}%`} />
            <Meter
              label="内存"
              value={systemStatus?.memory?.percent ?? 0}
              detail={
                systemStatus?.memory
                  ? `${Math.round(systemStatus.memory.used_mb / 1024)}G / ${Math.round(systemStatus.memory.total_mb / 1024)}G`
                  : "--"
              }
            />
            <Meter
              label="GPU"
              value={systemStatus?.gpu?.utilization ?? 0}
              detail={systemStatus?.gpu ? `${systemStatus.gpu.utilization}% · ${systemStatus.gpu.temperature}C` : "--"}
            />
            <Meter
              label="显存"
              value={systemStatus?.gpu?.memory_percent ?? 0}
              detail={
                systemStatus?.gpu
                  ? `${(systemStatus.gpu.memory_used_mb / 1024).toFixed(1)}G / ${(systemStatus.gpu.memory_total_mb / 1024).toFixed(1)}G`
                  : "--"
              }
            />
            {systemStatus?.gpu && <div className="power">功耗 {systemStatus.gpu.power_w.toFixed(1)}W</div>}
          </section>
        </aside>

        <section className="content">
          <div className="preview">
            {previewUrl && isVideoPreview ? (
              <video key={previewUrl} src={`${API}${previewUrl}`} controls autoPlay muted loop />
            ) : previewUrl ? (
              <img src={`${API}${previewUrl}`} alt="任务预览" />
            ) : (
              <div className="empty">
                <Play size={38} />
                <span>{busy ? "正在创建任务..." : "选择任务后在这里实时预览"}</span>
              </div>
            )}
          </div>

          <div className="side">
            <section className="jobs">
              <div className="section-title">
                <span>生成任务</span>
                <button className="icon" onClick={() => loadJobs()}>
                  <RefreshCw size={16} />
                </button>
              </div>
              {jobs.length ? (
                jobs.map((job) => (
                  <button
                    className={`job ${job.id === selectedJob?.id ? "active" : ""}`}
                    key={job.id}
                    onClick={() => setSelectedJobId(job.id)}
                  >
                    <strong>{job.title}</strong>
                    <span>{job.engine.toUpperCase()} · {job.status} · {job.progress}%</span>
                    <i style={{ width: `${job.progress}%` }} />
                    <em>{job.error || job.message}</em>
                  </button>
                ))
              ) : (
                <div className="empty-list">暂无任务</div>
              )}
            </section>

            <div className="scenes">
              {(project?.scenes || []).map((scene) => (
                <article key={scene.index}>
                  <strong>{scene.index}. {scene.title}</strong>
                  <p>{scene.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>
      </section>
    </main>
  );
}

function Meter({ label, value, detail }: { label: string; value: number; detail: string }) {
  const clamped = Math.max(0, Math.min(100, value || 0));
  return (
    <div className="meter">
      <div>
        <span>{label}</span>
        <strong>{detail}</strong>
      </div>
      <i>
        <b style={{ width: `${clamped}%` }} />
      </i>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
