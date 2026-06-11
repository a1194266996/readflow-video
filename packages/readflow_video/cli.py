import argparse
from pathlib import Path

from .renderer import RenderOptions, render_project
from .script import generate_script


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a vertical reading video.")
    parser.add_argument("prompt", help="Prompt or topic for the video.")
    parser.add_argument("--output-dir", default="storage/outputs")
    parser.add_argument("--scene-count", type=int, default=6)
    parser.add_argument("--no-tts", action="store_true")
    parser.add_argument("--static", action="store_true", help="Render static cards instead of animated scenes.")
    parser.add_argument("--ai-engine", choices=["template", "svd"], default="template")
    parser.add_argument("--character", default="presenter")
    parser.add_argument("--no-karaoke", action="store_true")
    args = parser.parse_args()

    project = generate_script(args.prompt, scene_count=args.scene_count)
    result = render_project(
        project,
        RenderOptions(
            output_dir=Path(args.output_dir),
            with_tts=not args.no_tts,
            animated=not args.static,
            ai_engine=args.ai_engine,
            character=args.character,
            karaoke=not args.no_karaoke,
        ),
    )
    print(result.video_path)


if __name__ == "__main__":
    main()
