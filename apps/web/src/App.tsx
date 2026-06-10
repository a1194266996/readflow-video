import { useState } from "react";
import { FileText, Play, WandSparkles } from "lucide-react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API = import.meta.env.VITE_API_URL || "http://172.16.10.165:8010";

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

function App() {
  const [prompt, setPrompt] = useState("30岁以后一定要明白的5个人生道理");
  const [project, setProject] = useState<Project | null>(null);
  const [videoUrl, setVideoUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [character, setCharacter] = useState("presenter");
  const [karaoke, setKaraoke] = useState(true);

  async function generateScript() {
    setBusy(true);
    setVideoUrl("");
    try {
      const res = await fetch(`${API}/api/script`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, scene_count: 6, style: "小红书干货" }),
      });
      setProject(await res.json());
    } finally {
      setBusy(false);
    }
  }

  async function renderVideo() {
    setBusy(true);
    try {
      const res = await fetch(`${API}/api/render`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          project,
          with_tts: true,
          animated: true,
          character,
          karaoke,
          visual_style: "story",
        }),
      });
      const data = await res.json();
      setProject(data.project);
      setVideoUrl(`${API}${data.video_url}`);
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
              导出动画
            </button>
          </div>
        </aside>

        <section className="content">
          <div className="preview">
            {videoUrl ? (
              <video src={videoUrl} controls />
            ) : (
              <div className="empty">
                <Play size={38} />
                <span>{busy ? "正在处理..." : "生成后在这里预览竖屏视频"}</span>
              </div>
            )}
          </div>

          <div className="scenes">
            {(project?.scenes || []).map((scene) => (
              <article key={scene.index}>
                <strong>{scene.index}. {scene.title}</strong>
                <p>{scene.body}</p>
              </article>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
