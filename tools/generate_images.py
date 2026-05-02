#!/usr/bin/env python3
"""Generate brand images for LUMKO landing using DefAPI or OpenAI Images API.

Uses DefAPI gpt-image-2 when DEFAPI, DEFAPI_API_KEY, or DEFAPI_KEY is set.
Falls back to OpenAI gpt-image-2, gpt-image-1.5, and gpt-image-1 when available.
Reads API keys from ../.env (KEY=VALUE format).
Saves outputs to ../assets/ai/.
"""
from __future__ import annotations

import base64
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"
OUT = ROOT / "assets" / "ai"
OUT.mkdir(parents=True, exist_ok=True)


def load_env() -> dict[str, str]:
    if not ENV.exists():
        sys.exit(f"missing {ENV}")
    values: dict[str, str] = {}
    for line in ENV.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def request_openai_image(api_key: str, model: str, prompt: str, size: str) -> bytes:
    payload = {"model": model, "prompt": prompt, "size": size, "n": 1}
    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        body = json.loads(resp.read())
    item = body["data"][0]
    if "b64_json" in item and item["b64_json"]:
        return base64.b64decode(item["b64_json"])
    if "url" in item and item["url"]:
        with urllib.request.urlopen(item["url"], timeout=120) as r:
            return r.read()
    raise RuntimeError(f"unexpected response: {body}")


def request_json(url: str, api_key: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key.removeprefix('Bearer ')}",
            "Content-Type": "application/json",
        },
        method="GET" if payload is None else "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {e.code} from {url}: {body[:500]}") from e


def request_defapi_image(api_key: str, prompt: str, size: str, quality: str = "high") -> bytes:
    payload = {
        "model": "openai/gpt-image-2",
        "prompt": prompt,
        "size": size,
        "quality": quality,
    }
    created = request_json("https://api.defapi.org/api/gpt-image/gen", api_key, payload)
    task_id = (created.get("data") or {}).get("task_id") if isinstance(created.get("data"), dict) else None
    if not task_id:
        raise RuntimeError(f"unexpected DefAPI create response: {created}")
    print(f"  DefAPI task {task_id}: created", flush=True)

    query = "https://api.defapi.org/api/task/query?" + urllib.parse.urlencode({"task_id": task_id})
    for attempt in range(60):
        time.sleep(5 if attempt else 2)
        try:
            body = request_json(query, api_key)
        except RuntimeError as e:
            if "HTTP 404" in str(e) and attempt < 6:
                print(f"  DefAPI task {task_id}: not indexed yet", flush=True)
                continue
            raise
        data = body.get("data")
        if not isinstance(data, dict):
            raise RuntimeError(f"unexpected DefAPI task response: {body}")

        status = data.get("status")
        if status in {"pending", "in_progress"}:
            print(f"  DefAPI task {task_id}: {status}", flush=True)
            continue
        if status == "failed":
            raise RuntimeError(f"DefAPI task failed: {data.get('status_reason')}")
        if status == "success":
            result = data.get("result")
            if not isinstance(result, list) or not result:
                raise RuntimeError(f"DefAPI task succeeded with no result: {body}")
            image_url = result[0].get("image") if isinstance(result[0], dict) else None
            if not image_url:
                raise RuntimeError(f"DefAPI result missing image URL: {body}")
            print(f"  DefAPI task {task_id}: downloading result", flush=True)
            image_req = urllib.request.Request(
                str(image_url),
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                    ),
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                },
            )
            try:
                with urllib.request.urlopen(image_req, timeout=180) as resp:
                    return resp.read()
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="ignore")
                raise RuntimeError(f"HTTP {e.code} downloading DefAPI result: {body[:500]}") from e

        raise RuntimeError(f"unexpected DefAPI task status: {body}")
    raise TimeoutError(f"DefAPI task timed out: {task_id}")


def generate_defapi(api_key: str, prompt: str, out_name: str, size: str) -> Path:
    print(f"[{out_name}] requesting DefAPI openai/gpt-image-2 {size} ...", flush=True)
    data = request_defapi_image(api_key, prompt, size)
    path = OUT / out_name
    path.write_bytes(data)
    print(f"[{out_name}] saved ({len(data)//1024} KB) via DefAPI openai/gpt-image-2")
    return path


def generate_openai(api_key: str, prompt: str, out_name: str, size: str) -> Path:
    last_err: Exception | None = None
    for model in ("gpt-image-2", "gpt-image-1.5", "gpt-image-1"):
        try:
            print(f"[{out_name}] requesting {model} {size} ...", flush=True)
            data = request_openai_image(api_key, model, prompt, size)
            path = OUT / out_name
            path.write_bytes(data)
            print(f"[{out_name}] saved ({len(data)//1024} KB) via {model}")
            return path
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            print(f"[{out_name}] {model} -> HTTP {e.code}: {err_body[:240]}", flush=True)
            last_err = e
        except Exception as e:  # noqa: BLE001
            print(f"[{out_name}] {model} -> {type(e).__name__}: {e}", flush=True)
            last_err = e
    raise RuntimeError(f"all models failed for {out_name}: {last_err}")


def generate(env: dict[str, str], prompt: str, out_name: str, size: str = "1536x1024") -> Path:
    defapi_key = env.get("DEFAPI") or env.get("DEFAPI_API_KEY") or env.get("DEFAPI_KEY")
    if defapi_key:
        return generate_defapi(defapi_key, prompt, out_name, size)

    openai_key = env.get("OPENAI_API_KEY")
    if not openai_key:
        sys.exit("Set DEFAPI, DEFAPI_API_KEY, DEFAPI_KEY, or OPENAI_API_KEY in .env")
    return generate_openai(openai_key, prompt, out_name, size)


JOBS = [
    {
        "name": "hero-bg.png",
        "size": "1536x1024",
        "prompt": (
            "Premium editorial hero photograph for a boutique web design studio. "
            "A modern laptop computer open on a refined warm cream desk, showing a clean abstract website layout "
            "with teal (#33596c) and mint (#6fcbc7) interface shapes, no readable text, no logos. "
            "Elegant studio lighting, soft shadows, subtle glass and paper textures, high-end magazine composition, "
            "generous negative space on the left side for large headline typography, warm off-white background, "
            "minimal, sophisticated, realistic photographic depth of field."
        ),
    },
    {
        "name": "studio-vibe.png",
        "size": "1024x1024",
        "prompt": (
            "Premium abstract illustration of a modern web design studio essence. "
            "Floating geometric and organic forms — a glowing soft mint (#6fcbc7) liquid orb, "
            "a deep teal (#33596c) curved ribbon, light gray (#d9d9d9) thin grid lines, "
            "warm cream (#faf6ef) background. 3D soft-render, clay material, depth of field, "
            "luxurious and minimalist, no text, no logos, square composition, art-gallery quality."
        ),
    },
    {
        "name": "process-bg.png",
        "size": "1536x1024",
        "prompt": (
            "Ultra wide cinematic minimal background. Warm cream (#faf6ef) base, large soft "
            "mint (#6fcbc7) gradient blob in lower-left, subtle deep teal (#33596c) flowing line "
            "across the middle, very faint dotted grid texture, premium editorial feel, "
            "lots of negative space, no text, no objects, ready to host typography."
        ),
    },
    {
        "name": "cta-bg.png",
        "size": "1536x1024",
        "prompt": (
            "Premium magazine-style background. Deep teal (#33596c) base, smooth gradient to a "
            "mint (#6fcbc7) glow on the right, subtle abstract liquid waves, very high-end, "
            "minimal, calm, sophisticated, no text, no logos, ample empty space for headline."
        ),
    },
]


def main() -> int:
    env = load_env()
    failures = 0
    for job in JOBS:
        try:
            generate(env, job["prompt"], job["name"], job["size"])
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {job['name']}: {e}")
            failures += 1
    return failures


if __name__ == "__main__":
    sys.exit(main())
