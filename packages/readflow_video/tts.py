import asyncio
import subprocess
from pathlib import Path


async def _edge_tts(text: str, output: Path, voice: str) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output))


def synthesize_voice(text: str, output: Path, voice: str, duration: float, enabled: bool = True) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    if enabled:
        try:
            asyncio.run(_edge_tts(text, output, voice))
            if output.exists() and output.stat().st_size > 0:
                return output
        except Exception:
            pass

    silent = output.with_suffix(".wav")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t",
            f"{duration:.2f}",
            str(silent),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return silent
