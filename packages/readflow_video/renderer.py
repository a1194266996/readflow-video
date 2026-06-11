import hashlib
import math
import shutil
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from PIL import Image, ImageDraw, ImageFont

from .ai_video import render_svd_segment, render_wan_segment
from .schemas import VideoProject
from .tts import synthesize_voice

WIDTH = 1080
HEIGHT = 1920
FPS = 24


@dataclass
class RenderOptions:
    output_dir: Path
    voice: str = "zh-CN-XiaoxiaoNeural"
    with_tts: bool = True
    animated: bool = True
    ai_engine: str = "template"
    visual_style: str = "story"
    character: str = "presenter"
    karaoke: bool = True
    progress_callback: Callable[[dict[str, Any]], None] | None = None


@dataclass
class RenderResult:
    video_path: Path
    srt_path: Path
    duration: float


def _run_ffmpeg(args: list[str]) -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required. Install it with: sudo apt install ffmpeg")
    completed = subprocess.run(["ffmpeg", "-y", *args], text=True, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr[-2000:])


def _font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def _wrap(text: str, width: int) -> str:
    if not text:
        return ""
    if " " in text:
        return "\n".join(textwrap.wrap(text, width=width, break_long_words=False, replace_whitespace=False))
    return "\n".join(text[i : i + width] for i in range(0, len(text), width))


def _draw_centered(draw: ImageDraw.ImageDraw, text: str, y: int, font: ImageFont.ImageFont, fill: str, spacing: int = 16) -> int:
    lines = text.splitlines()
    line_heights = [draw.textbbox((0, 0), line, font=font)[3] for line in lines]
    total_height = sum(line_heights) + spacing * (len(lines) - 1)
    current_y = y - total_height // 2
    for line, line_height in zip(lines, line_heights):
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (WIDTH - (bbox[2] - bbox[0])) // 2
        draw.text((x, current_y), line, font=font, fill=fill)
        current_y += line_height + spacing
    return current_y


def _ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


def _alpha_for_time(t: float) -> float:
    return min(1.0, t / 0.35, (1.0 - t) / 0.35 if t > 0.65 else 1.0)


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    return tuple(int(color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))


def _draw_centered_alpha(
    base: Image.Image,
    text: str,
    y: int,
    font: ImageFont.ImageFont,
    fill: str,
    alpha: int,
    spacing: int = 16,
) -> None:
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    lines = text.splitlines()
    line_heights = [draw.textbbox((0, 0), line, font=font)[3] for line in lines]
    total_height = sum(line_heights) + spacing * (len(lines) - 1)
    current_y = y - total_height // 2
    rgb = _hex_to_rgb(fill)
    for line, line_height in zip(lines, line_heights):
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (WIDTH - (bbox[2] - bbox[0])) // 2
        draw.text((x, current_y), line, font=font, fill=(*rgb, alpha))
        current_y += line_height + spacing
    base.alpha_composite(overlay)


def _draw_centered_boxed(
    base: Image.Image,
    text: str,
    y: int,
    font: ImageFont.ImageFont,
    fill: str,
    box_fill: str,
    accent: str,
    alpha: int,
    spacing: int = 14,
) -> None:
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    lines = text.splitlines()
    boxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
    text_width = max((box[2] - box[0] for box in boxes), default=0)
    line_heights = [box[3] - box[1] for box in boxes]
    text_height = sum(line_heights) + spacing * (len(lines) - 1)
    pad_x = 34
    pad_y = 26
    left = (WIDTH - text_width) // 2 - pad_x
    top = y - text_height // 2 - pad_y
    right = left + text_width + pad_x * 2
    bottom = top + text_height + pad_y * 2
    draw.rounded_rectangle((left, top, right, bottom), radius=24, fill=(*_hex_to_rgb(box_fill), int(alpha * 0.88)))
    draw.rounded_rectangle((left, top, right, bottom), radius=24, outline=(*_hex_to_rgb(accent), alpha), width=4)

    current_y = top + pad_y
    for line, line_height in zip(lines, line_heights):
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (WIDTH - (bbox[2] - bbox[0])) // 2
        draw.text((x, current_y), line, font=font, fill=(*_hex_to_rgb(fill), alpha))
        current_y += line_height + spacing
    base.alpha_composite(overlay)


def _render_scene_card(project: VideoProject, scene_index: int, work_dir: Path) -> Path:
    scene = project.scenes[scene_index]
    palette = [
        ("#f6f1e8", "#153426", "#a63a2d"),
        ("#eef4f1", "#102a43", "#047857"),
        ("#fff7ed", "#1f2937", "#b45309"),
        ("#f7f7fb", "#172554", "#7c3aed"),
    ][scene_index % 4]
    background, ink, accent = palette

    img = Image.new("RGB", (WIDTH, HEIGHT), background)
    draw = ImageDraw.Draw(img)
    draw.rectangle((70, 80, 150, 92), fill=accent)
    draw.rectangle((70, HEIGHT - 145, WIDTH - 70, HEIGHT - 140), fill=accent)

    title_font = _font(76)
    body_font = _font(54)
    meta_font = _font(34)

    draw.text((70, 130), f"{scene.index:02d}", font=meta_font, fill=accent)
    _draw_centered(draw, _wrap(scene.title, 10), 610, title_font, ink, spacing=18)
    _draw_centered(draw, _wrap(scene.body, 16), 1110, body_font, ink, spacing=24)
    draw.text((70, HEIGHT - 230), project.style, font=meta_font, fill=accent)

    image_path = work_dir / f"scene_{scene.index:02d}.png"
    img.save(image_path)
    return image_path


def _scene_keywords(text: str) -> str:
    if any(word in text for word in ["钱", "财富", "副业", "收入", "赚钱"]):
        return "wealth"
    if any(word in text for word in ["学习", "读书", "知识", "认知"]):
        return "study"
    if any(word in text for word in ["行动", "效率", "坚持", "习惯"]):
        return "action"
    if any(word in text for word in ["情绪", "关系", "焦虑", "能量"]):
        return "mind"
    return "growth"


def _draw_scene_illustration(
    draw: ImageDraw.ImageDraw,
    scene_text: str,
    progress: float,
    accent: str,
    ink: str,
    soft: str,
) -> None:
    kind = _scene_keywords(scene_text)
    float_y = int(math.sin(progress * math.tau) * 18)
    if kind == "wealth":
        for idx, height in enumerate([210, 270, 340, 420]):
            x = 130 + idx * 95
            draw.rounded_rectangle((x, 1320 - height, x + 58, 1320), radius=16, fill=soft, outline=accent, width=4)
        draw.line((120, 1340, 520, 1000 + float_y), fill=accent, width=10)
        draw.polygon((510, 1000 + float_y, 475, 1000 + float_y, 505, 960 + float_y), fill=accent)
    elif kind == "study":
        draw.rounded_rectangle((110, 1040 + float_y, 520, 1330 + float_y), radius=24, fill=soft, outline=accent, width=5)
        draw.line((315, 1050 + float_y, 315, 1325 + float_y), fill=accent, width=5)
        for row in range(5):
            draw.line((150, 1100 + row * 42 + float_y, 280, 1100 + row * 42 + float_y), fill=ink, width=4)
            draw.line((350, 1100 + row * 42 + float_y, 480, 1100 + row * 42 + float_y), fill=ink, width=4)
    elif kind == "action":
        draw.ellipse((150, 1050 + float_y, 500, 1400 + float_y), fill=soft, outline=accent, width=6)
        draw.line((240, 1230 + float_y, 330, 1320 + float_y), fill=accent, width=18)
        draw.line((330, 1320 + float_y, 460, 1120 + float_y), fill=accent, width=18)
    elif kind == "mind":
        draw.rounded_rectangle((120, 1035 + float_y, 530, 1325 + float_y), radius=80, fill=soft, outline=accent, width=6)
        draw.ellipse((210, 1130 + float_y, 245, 1165 + float_y), fill=ink)
        draw.ellipse((395, 1130 + float_y, 430, 1165 + float_y), fill=ink)
        draw.arc((250, 1170 + float_y, 390, 1270 + float_y), 10, 170, fill=accent, width=8)
    else:
        draw.arc((140, 1010 + float_y, 520, 1390 + float_y), 210, 330, fill=accent, width=16)
        draw.polygon((500, 1190 + float_y, 540, 1212 + float_y, 500, 1240 + float_y), fill=accent)
        for idx in range(4):
            draw.ellipse((180 + idx * 78, 1200 - idx * 45 + float_y, 238 + idx * 78, 1258 - idx * 45 + float_y), fill=soft, outline=accent, width=4)


def _draw_character(
    draw: ImageDraw.ImageDraw,
    progress: float,
    accent: str,
    ink: str,
    soft: str,
    character: str,
) -> None:
    bob = int(math.sin(progress * math.tau * 1.4) * 12)
    x = 760
    y = 1210 + bob
    skin = "#f0c8a6"
    shirt = accent if character == "presenter" else soft
    draw.ellipse((x - 78, y - 250, x + 78, y - 94), fill=skin, outline=ink, width=5)
    draw.arc((x - 48, y - 195, x + 48, y - 125), 15, 165, fill=ink, width=5)
    draw.ellipse((x - 34, y - 188, x - 20, y - 174), fill=ink)
    draw.ellipse((x + 20, y - 188, x + 34, y - 174), fill=ink)
    draw.rounded_rectangle((x - 110, y - 96, x + 110, y + 180), radius=52, fill=shirt, outline=ink, width=5)
    left_hand = int(math.sin(progress * math.tau * 2) * 24)
    draw.line((x - 100, y - 20, x - 190, y + 55 + left_hand), fill=ink, width=14)
    draw.line((x + 100, y - 18, x + 190, y + 58 - left_hand), fill=ink, width=14)
    draw.ellipse((x - 206, y + 40 + left_hand, x - 166, y + 80 + left_hand), fill=skin, outline=ink, width=4)
    draw.ellipse((x + 166, y + 43 - left_hand, x + 206, y + 83 - left_hand), fill=skin, outline=ink, width=4)
    draw.rounded_rectangle((x - 78, y + 35, x + 78, y + 128), radius=18, fill="#fffdf8", outline=ink, width=4)
    draw.line((x - 48, y + 76, x + 48, y + 76), fill=accent, width=5)


def _draw_karaoke_subtitle(
    base: Image.Image,
    text: str,
    progress: float,
    ink: str,
    accent: str,
) -> None:
    compact = text.replace("\n", "")
    if len(compact) > 42:
        compact = compact[:40] + "..."
    lines = [compact[i : i + 18] for i in range(0, len(compact), 18)][:3]
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _font(38)
    x0, y0, x1, y1 = 80, 1498, WIDTH - 80, 1708
    draw.rounded_rectangle((x0, y0, x1, y1), radius=28, fill=(255, 253, 248, 232))
    draw.rounded_rectangle((x0, y0, x1, y1), radius=28, outline=(*_hex_to_rgb(accent), 230), width=4)
    visible_chars = int(len(compact) * max(0.0, min(1.0, progress)))
    consumed = 0
    for idx, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_x = (WIDTH - (bbox[2] - bbox[0])) // 2
        text_y = y0 + 32 + idx * 56
        draw.text((text_x, text_y), line, font=font, fill=(*_hex_to_rgb(ink), 180))
        line_visible = max(0, min(len(line), visible_chars - consumed))
        if line_visible:
            highlighted = line[:line_visible]
            draw.text((text_x, text_y), highlighted, font=font, fill=(*_hex_to_rgb(accent), 255))
        consumed += len(line)
    base.alpha_composite(overlay)


def _apply_camera_motion(frame: Image.Image, progress: float, scene_index: int) -> Image.Image:
    zoom = 1.025 + 0.035 * _ease_out(progress)
    scaled_w = int(WIDTH * zoom)
    scaled_h = int(HEIGHT * zoom)
    scaled = frame.resize((scaled_w, scaled_h), Image.Resampling.BICUBIC)
    pan_x = int((scaled_w - WIDTH) * (0.18 + 0.64 * progress if scene_index % 2 == 0 else 0.82 - 0.64 * progress))
    pan_y = int((scaled_h - HEIGHT) * (0.5 + 0.18 * math.sin(progress * math.tau)))
    return scaled.crop((pan_x, pan_y, pan_x + WIDTH, pan_y + HEIGHT))


def _render_animation_frame(project: VideoProject, scene_index: int, progress: float, options: RenderOptions) -> Image.Image:
    scene = project.scenes[scene_index]
    palette = [
        ("#f6f1e8", "#153426", "#a63a2d", "#e9d5c0"),
        ("#eef4f1", "#102a43", "#047857", "#c7dfd7"),
        ("#fff7ed", "#1f2937", "#b45309", "#f5d0a9"),
        ("#f7f7fb", "#172554", "#7c3aed", "#ddd6fe"),
    ][scene_index % 4]
    background, ink, accent, soft = palette
    img = Image.new("RGBA", (WIDTH, HEIGHT), background)
    draw = ImageDraw.Draw(img)

    wave = math.sin(progress * math.tau)
    drift = _ease_out(progress)
    for idx in range(5):
        radius = 120 + idx * 46
        x = int(170 + idx * 210 + math.sin(progress * math.tau + idx) * 55)
        y = int(250 + idx * 255 + math.cos(progress * math.tau * 0.75 + idx) * 80)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=soft)

    _draw_scene_illustration(draw, scene.title + scene.body + project.prompt, progress, accent, ink, soft)

    img = _apply_camera_motion(img.convert("RGB"), progress, scene_index).convert("RGBA")
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((62, 74, WIDTH - 62, HEIGHT - 78), radius=36, outline=accent, width=5)
    draw.rectangle((70, 105, 150 + int(120 * progress), 118), fill=accent)
    draw.rectangle((70, HEIGHT - 150, WIDTH - 70, HEIGHT - 144), fill=accent)
    draw.ellipse((WIDTH - 250 + int(wave * 26), 150, WIDTH - 120 + int(wave * 26), 280), outline=accent, width=6)

    title_font = _font(76)
    body_font = _font(54)
    meta_font = _font(34)
    alpha = max(0, min(255, int(255 * _alpha_for_time(progress))))

    draw.text((70, 138), f"{scene.index:02d}", font=meta_font, fill=accent)
    title_y = int(510 - (1 - drift) * 90)
    body_y = int(790 + (1 - _ease_out(max(0, progress - 0.16) / 0.84)) * 110)
    _draw_centered_boxed(img, _wrap(scene.title, 10), title_y, title_font, ink, "#fffdf8", accent, alpha, spacing=18)
    _draw_centered_alpha(img, _wrap(scene.body, 16), body_y, body_font, ink, alpha, spacing=24)
    _draw_character(draw, progress, accent, ink, soft, options.character)
    if options.karaoke:
        _draw_karaoke_subtitle(img, scene.body, progress, ink, accent)
    draw.text((70, 210), project.style, font=meta_font, fill=accent)

    return img.convert("RGB")


def _render_animated_segment(project: VideoProject, scene_index: int, work_dir: Path, options: RenderOptions) -> Path:
    scene = project.scenes[scene_index]
    frame_dir = work_dir / f"frames_{scene.index:02d}"
    frame_dir.mkdir(parents=True, exist_ok=True)
    frame_count = max(1, int(scene.duration * FPS))
    for frame in range(frame_count):
        progress = frame / max(1, frame_count - 1)
        image = _render_animation_frame(project, scene_index, progress, options)
        image.save(frame_dir / f"frame_{frame:04d}.png")

    segment_path = work_dir / f"segment_{scene.index:02d}.mp4"
    _run_ffmpeg(
        [
            "-framerate",
            str(FPS),
            "-i",
            str(frame_dir / "frame_%04d.png"),
            "-vf",
            "format=yuv420p",
            "-r",
            "30",
            str(segment_path),
        ]
    )
    return segment_path


def _render_svd_segment(project: VideoProject, scene_index: int, work_dir: Path, options: RenderOptions) -> Path:
    scene = project.scenes[scene_index]
    keyframe = _render_animation_frame(project, scene_index, 0.52, options)
    keyframe_path = work_dir / f"svd_keyframe_{scene.index:02d}.png"
    keyframe.save(keyframe_path)
    if options.progress_callback:
        options.progress_callback(
            {
                "stage": "keyframe",
                "scene_index": scene.index,
                "message": f"已生成第 {scene.index} 个分镜关键帧",
                "preview_path": keyframe_path,
            }
        )
    segment_path = work_dir / f"segment_{scene.index:02d}.mp4"
    result = render_svd_segment(
        keyframe_path=keyframe_path,
        output_path=segment_path,
        duration=scene.duration,
        seed=scene.index * 9973,
    )
    if options.progress_callback:
        options.progress_callback(
            {
                "stage": "segment",
                "scene_index": scene.index,
                "message": f"已生成第 {scene.index} 个分镜视频",
                "preview_path": result,
            }
        )
    return result


def _wan_prompt(project: VideoProject, scene_index: int) -> str:
    scene = project.scenes[scene_index]
    subject = project.prompt.strip()
    story = f"{scene.title}。{scene.body}".strip("。")
    return (
        f"{subject}。{story}。"
        "vertical 9:16 cinematic animated short video, expressive character action, "
        "clear subject, dynamic camera movement, smooth motion, detailed scene, "
        "high quality, no text on screen"
    )


def _render_wan_segment(project: VideoProject, scene_index: int, work_dir: Path, options: RenderOptions) -> Path:
    scene = project.scenes[scene_index]
    if options.progress_callback:
        preview = _render_animation_frame(project, scene_index, 0.52, options)
        preview_path = work_dir / f"wan_preview_{scene.index:02d}.png"
        preview.save(preview_path)
        options.progress_callback(
            {
                "stage": "wan_prompt",
                "scene_index": scene.index,
                "message": f"Wan2.2 正在生成第 {scene.index} 个动画镜头",
                "preview_path": preview_path,
            }
        )
    segment_path = work_dir / f"segment_{scene.index:02d}.mp4"
    result = render_wan_segment(
        prompt=_wan_prompt(project, scene_index),
        output_path=segment_path,
        duration=scene.duration,
        seed=scene.index * 17713,
    )
    if options.progress_callback:
        options.progress_callback(
            {
                "stage": "segment",
                "scene_index": scene.index,
                "message": f"Wan2.2 已完成第 {scene.index} 个动画镜头",
                "preview_path": result,
            }
        )
    return result


def _render_static_segment(project: VideoProject, scene_index: int, work_dir: Path) -> Path:
    scene = project.scenes[scene_index]
    image_path = _render_scene_card(project, scene_index, work_dir)
    segment_path = work_dir / f"segment_{scene.index:02d}.mp4"
    _run_ffmpeg(
        [
            "-loop",
            "1",
            "-i",
            str(image_path),
            "-t",
            f"{scene.duration:.2f}",
            "-vf",
            "scale=1080:1920,format=yuv420p",
            "-r",
            "30",
            "-an",
            str(segment_path),
        ]
    )
    return segment_path


def _srt_time(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    h = millis // 3_600_000
    millis %= 3_600_000
    m = millis // 60_000
    millis %= 60_000
    s = millis // 1000
    ms = millis % 1000
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def _write_srt(project: VideoProject, path: Path) -> None:
    cursor = 0.0
    blocks = []
    for scene in project.scenes:
        start = cursor
        end = cursor + scene.duration
        blocks.append(f"{scene.index}\n{_srt_time(start)} --> {_srt_time(end)}\n{scene.title}\n{scene.body}\n")
        cursor = end
    path.write_text("\n".join(blocks), encoding="utf-8")


def render_project(project: VideoProject, options: RenderOptions) -> RenderResult:
    options.output_dir.mkdir(parents=True, exist_ok=True)
    render_signature = (
        project.model_dump_json()
        + f"|animated={options.animated}|engine={options.ai_engine}|style={options.visual_style}|character={options.character}|karaoke={options.karaoke}"
    )
    digest = hashlib.sha1(render_signature.encode("utf-8")).hexdigest()[:10]
    work_dir = options.output_dir / f"work-{digest}"
    work_dir.mkdir(parents=True, exist_ok=True)

    scene_videos: list[Path] = []
    for i, _scene in enumerate(project.scenes):
        if options.progress_callback:
            options.progress_callback(
                {
                    "stage": "scene",
                    "scene_index": i + 1,
                    "message": f"正在生成第 {i + 1}/{len(project.scenes)} 个分镜",
                }
            )
        if options.ai_engine == "wan":
            scene_videos.append(_render_wan_segment(project, i, work_dir, options))
        elif options.ai_engine == "svd":
            scene_videos.append(_render_svd_segment(project, i, work_dir, options))
        elif options.animated:
            scene_videos.append(_render_animated_segment(project, i, work_dir, options))
        else:
            scene_videos.append(_render_static_segment(project, i, work_dir))
        if options.progress_callback:
            options.progress_callback(
                {
                    "stage": "scene_done",
                    "scene_index": i + 1,
                    "message": f"第 {i + 1}/{len(project.scenes)} 个分镜完成",
                    "preview_path": scene_videos[-1],
                }
            )

    concat_file = work_dir / "segments.txt"
    concat_file.write_text("".join(f"file '{path.resolve().as_posix()}'\n" for path in scene_videos), encoding="utf-8")
    video_no_audio = work_dir / "video-no-audio.mp4"
    _run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(video_no_audio)])
    if options.progress_callback:
        options.progress_callback({"stage": "concat", "message": "正在合成完整视频", "preview_path": video_no_audio})

    narration = "\n".join(f"{scene.title}。{scene.body}" for scene in project.scenes)
    duration = math.fsum(scene.duration for scene in project.scenes)
    audio_path = synthesize_voice(narration, work_dir / "voice.mp3", options.voice, duration, options.with_tts)

    output_path = options.output_dir / f"readflow-{digest}.mp4"
    _run_ffmpeg(
        [
            "-i",
            str(video_no_audio),
            "-i",
            str(audio_path),
            "-shortest",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(output_path),
        ]
    )

    srt_path = options.output_dir / f"readflow-{digest}.srt"
    _write_srt(project, srt_path)
    if options.progress_callback:
        options.progress_callback({"stage": "done", "message": "视频生成完成", "preview_path": output_path})
    return RenderResult(video_path=output_path, srt_path=srt_path, duration=duration)
