import json
import os
import re
from typing import Any

import httpx


DEFAULT_LLM_BASE_URL = "http://127.0.0.1:8020/v1"
DEFAULT_LLM_MODEL = "qwen3-14b-q4"


def get_llm_status() -> dict[str, Any]:
    base_url = os.getenv("READFLOW_LLM_BASE_URL", DEFAULT_LLM_BASE_URL).rstrip("/")
    model = os.getenv("READFLOW_LLM_MODEL", DEFAULT_LLM_MODEL)
    provider = os.getenv("READFLOW_LLM_PROVIDER", "openai-compatible")
    status: dict[str, Any] = {
        "provider": provider,
        "base_url": base_url,
        "model": model,
        "ready": False,
    }
    try:
        response = httpx.get(f"{base_url}/models", timeout=3)
        status["ready"] = response.status_code < 500
        if response.status_code >= 400:
            status["reason"] = f"LLM server returned HTTP {response.status_code}"
    except Exception as exc:
        status["reason"] = str(exc)
    return status


def _json_from_text(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("LLM did not return JSON")


def _chat(messages: list[dict[str, str]], temperature: float = 0.4) -> str:
    base_url = os.getenv("READFLOW_LLM_BASE_URL", DEFAULT_LLM_BASE_URL).rstrip("/")
    model = os.getenv("READFLOW_LLM_MODEL", DEFAULT_LLM_MODEL)
    api_key = os.getenv("READFLOW_LLM_API_KEY", "not-needed")
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 1800,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(timeout=120) as client:
        response = client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"]


def optimize_video_prompt(prompt: str, style: str = "short-video") -> dict[str, Any]:
    system = (
        "You are an AI short-video director for Wan2.2 text-to-video. "
        "Rewrite user ideas into stable video-generation prompts. "
        "Return strict JSON only. Do not include markdown. "
        "Avoid on-screen text, subtitles, watermarks, logos, gore, and unsafe content."
    )
    user = (
        "Create a vertical short-video plan from this idea.\n"
        f"Idea: {prompt}\n"
        f"Style: {style}\n\n"
        "JSON schema:\n"
        "{\n"
        '  "title": "short Chinese title",\n'
        '  "optimized_prompt": "detailed Wan2.2 prompt, Chinese or bilingual, vertical 9:16, cinematic motion, no text",\n'
        '  "negative_prompt": "bad quality terms",\n'
        '  "scenes": [\n'
        '    {"title": "scene title", "body": "shot/action description", "duration": 5.0}\n'
        "  ]\n"
        "}\n"
        "Use 1 to 3 scenes. Keep each scene visually concrete."
    )
    raw = _chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
    )
    data = _json_from_text(raw)
    scenes = data.get("scenes") or []
    normalized_scenes = []
    for index, scene in enumerate(scenes[:3], start=1):
        normalized_scenes.append(
            {
                "index": index,
                "title": str(scene.get("title") or data.get("title") or prompt)[:80],
                "body": str(scene.get("body") or data.get("optimized_prompt") or prompt)[:500],
                "duration": float(scene.get("duration") or 5.0),
            }
        )
    if not normalized_scenes:
        normalized_scenes.append(
            {
                "index": 1,
                "title": str(data.get("title") or prompt)[:80],
                "body": str(data.get("optimized_prompt") or prompt)[:500],
                "duration": 5.0,
            }
        )
    return {
        "title": str(data.get("title") or prompt)[:80],
        "optimized_prompt": str(data.get("optimized_prompt") or prompt),
        "negative_prompt": str(data.get("negative_prompt") or ""),
        "scenes": normalized_scenes,
        "raw": data,
    }


def chat_video_director(
    history: list[dict[str, str]],
    message: str,
    prompt: str = "",
    project: dict[str, Any] | None = None,
    style: str = "short-video",
) -> dict[str, Any]:
    system = (
        "You are an AI director for a Chinese short-video generator. "
        "Help the user develop continuous video ideas, recurring characters, style, scripts, and Wan2.2 prompts. "
        "Return strict JSON only. Do not include markdown. "
        "When useful, include a video_plan that can be used directly by the renderer. "
        "Keep continuity across the conversation. "
        "Do not use names, likenesses, or story elements from existing copyrighted characters or franchises; "
        "create original character names and original settings instead."
    )
    context = {
        "current_prompt": prompt,
        "current_project": project,
        "style": style,
    }
    user = (
        "Current project context:\n"
        f"{json.dumps(context, ensure_ascii=False)}\n\n"
        f"User message: {message}\n\n"
        "Return JSON with this schema:\n"
        "{\n"
        '  "reply": "natural Chinese assistant reply",\n'
        '  "optimized_prompt": "optional improved Wan2.2 prompt",\n'
        '  "video_plan": {\n'
        '    "title": "optional title",\n'
        '    "prompt": "optional prompt for generation",\n'
        '    "style": "optional style",\n'
        '    "scenes": [{"title": "scene title", "body": "shot/action/script description", "duration": 5.0}]\n'
        "  },\n"
        '  "suggestions": ["optional next action"]\n'
        "}\n"
        "Use null for video_plan if the user is only asking a question."
    )
    messages = [{"role": "system", "content": system}, *history[-12:], {"role": "user", "content": user}]
    raw = _chat(messages, temperature=0.55)
    try:
        data = _json_from_text(raw)
    except Exception:
        return {"reply": raw, "optimized_prompt": "", "project": None, "suggestions": []}

    reply = str(data.get("reply") or "")
    video_plan = data.get("video_plan") or {}
    optimized_prompt = str(data.get("optimized_prompt") or video_plan.get("prompt") or "")
    scenes = video_plan.get("scenes") or []
    project_payload = None
    if optimized_prompt or scenes:
        title = str(video_plan.get("title") or data.get("title") or prompt or "AI 导演方案")[:80]
        normalized_scenes = []
        for index, scene in enumerate(scenes[:6], start=1):
            normalized_scenes.append(
                {
                    "index": index,
                    "title": str(scene.get("title") or title)[:80],
                    "body": str(scene.get("body") or optimized_prompt or prompt)[:500],
                    "duration": float(scene.get("duration") or 5.0),
                }
            )
        if not normalized_scenes:
            normalized_scenes.append(
                {
                    "index": 1,
                    "title": title,
                    "body": optimized_prompt or prompt,
                    "duration": 5.0,
                }
            )
        project_payload = {
            "title": title,
            "prompt": optimized_prompt or str(video_plan.get("prompt") or prompt),
            "style": str(video_plan.get("style") or style),
            "scenes": normalized_scenes,
        }
    return {
        "reply": reply or "我已经根据上下文整理好了一个新方向。",
        "optimized_prompt": optimized_prompt,
        "project": project_payload,
        "suggestions": data.get("suggestions") or [],
        "raw": data,
    }
