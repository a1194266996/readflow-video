from readflow_video.script import generate_script


def test_generate_script_returns_requested_scene_count():
    project = generate_script("给普通人的财富认知", scene_count=6)

    assert project.title == "给普通人的财富认知"
    assert len(project.scenes) == 6
    assert project.scenes[0].index == 1
    assert all(scene.body for scene in project.scenes)
