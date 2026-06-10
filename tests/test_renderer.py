from readflow_video.renderer import RenderOptions, render_project
from readflow_video.script import generate_script


def test_render_project_smoke(tmp_path):
    project = generate_script("测试主题", scene_count=3)
    for scene in project.scenes:
        scene.duration = 2.0

    result = render_project(project, RenderOptions(output_dir=tmp_path, with_tts=False))

    assert result.video_path.exists()
    assert result.video_path.stat().st_size > 1000
    assert result.srt_path.exists()
