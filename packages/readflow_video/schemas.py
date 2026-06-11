from pydantic import BaseModel, Field


class Scene(BaseModel):
    index: int
    title: str
    body: str
    duration: float = Field(default=4.8, ge=2.0, le=12.0)


class VideoProject(BaseModel):
    title: str
    prompt: str
    style: str = "小红书干货"
    scenes: list[Scene]


class ScriptRequest(BaseModel):
    prompt: str
    scene_count: int = Field(default=6, ge=3, le=10)
    style: str = "小红书干货"


class RenderRequest(ScriptRequest):
    project: VideoProject | None = None
    voice: str = "zh-CN-XiaoxiaoNeural"
    with_tts: bool = True
    animated: bool = True
    ai_engine: str = "svd"
    visual_style: str = "story"
    character: str = "presenter"
    karaoke: bool = True
