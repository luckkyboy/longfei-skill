#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TASKS_PATH = ROOT / "references" / "nvwa" / "tasks" / "transcript_extract_tasks.jsonl"
DEFAULT_OUTPUT_PATH = ROOT / "references" / "nvwa" / "output" / "transcript_extract.jsonl"
DEFAULT_ERRORS_PATH = ROOT / "references" / "nvwa" / "output" / "transcript_extract.errors.jsonl"
DEFAULT_DEVELOPER_PROMPT_PATH = ROOT / "references" / "nvwa" / "prompts" / "cleaned_md_extraction_developer_prompt.md"
DEFAULT_USER_PROMPT_PATH = ROOT / "references" / "nvwa" / "prompts" / "cleaned_md_extraction_user_prompt.md"
DEFAULT_SCHEMA_PATH = ROOT / "references" / "nvwa" / "schema" / "cleaned_md_extraction.schema.json"
DEFAULT_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_MODEL = "z-ai/glm4.7"
RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}
HOST_REFRAME_ENABLED_CONTENT_TYPES = {"fan_call_case", "opinion_monologue"}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def existing_task_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            ids.add(json.loads(line)["task_id"])
        except Exception:
            continue
    return ids


def build_chat_payload(
    task: dict,
    model: str,
    max_tokens: int,
    temperature: float,
    developer_prompt: str,
    user_prompt_template: str,
    response_schema: dict,
) -> dict:
    cleaned_md_text = task.get("cleaned_md_text")
    if not isinstance(cleaned_md_text, str) or not cleaned_md_text.strip():
        cleaned_md_text = task.get("input", "")
    user_content = user_prompt_template.replace("{{cleaned_md_text}}", cleaned_md_text)
    return {
        "model": model,
        "messages": [
            {"role": "developer", "content": developer_prompt},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {"type": "json_schema", "json_schema": response_schema},
    }


def extract_json_object(text: str) -> dict:
    content = text.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in model response")
    return json.loads(content[start : end + 1])


def call_nim_api(api_key: str, payload: dict, api_url: str) -> dict:
    request = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.loads(response.read().decode("utf-8"))


def compute_retry_delay(attempt: int, retry_after: str | None = None) -> float:
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            pass
    base = min(5 * (2 ** max(0, attempt - 1)), 60)
    jitter = random.uniform(0, 1)
    return base + jitter


def call_nim_api_with_retry(
    api_key: str,
    payload: dict,
    api_url: str,
    max_retries: int,
) -> dict:
    attempt = 0
    while True:
        attempt += 1
        try:
            return call_nim_api(api_key=api_key, payload=payload, api_url=api_url)
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRYABLE_HTTP_CODES or attempt > max_retries:
                raise
            delay = compute_retry_delay(attempt, exc.headers.get("Retry-After"))
            time.sleep(delay)


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def normalize_output_by_metadata(output: dict, metadata: dict) -> dict:
    """Apply deterministic post-rules to keep extraction behavior stable."""
    content_type = metadata.get("content_type")
    if content_type not in HOST_REFRAME_ENABLED_CONTENT_TYPES:
        output["host_reframe"] = ""
    return output


def process_tasks(
    tasks_path: Path,
    output_path: Path,
    errors_path: Path,
    developer_prompt_path: Path,
    user_prompt_path: Path,
    schema_path: Path,
    api_key: str,
    api_url: str = DEFAULT_API_URL,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 2048,
    temperature: float = 0.0,
    limit: int | None = None,
    sleep_seconds: float = 0.0,
    max_retries: int = 5,
) -> dict:
    tasks = load_jsonl(tasks_path)
    developer_prompt = developer_prompt_path.read_text(encoding="utf-8")
    user_prompt_template = user_prompt_path.read_text(encoding="utf-8")
    response_schema = json.loads(schema_path.read_text(encoding="utf-8"))
    done_ids = existing_task_ids(output_path)
    processed = 0
    failed = 0

    for task in tasks:
        if task["task_id"] in done_ids:
            continue
        if limit is not None and processed >= limit:
            break

        payload = build_chat_payload(
            task=task,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            developer_prompt=developer_prompt,
            user_prompt_template=user_prompt_template,
            response_schema=response_schema,
        )
        try:
            response = call_nim_api_with_retry(
                api_key=api_key,
                payload=payload,
                api_url=api_url,
                max_retries=max_retries,
            )
            message_text = response["choices"][0]["message"]["content"]
            parsed = extract_json_object(message_text)
            parsed = normalize_output_by_metadata(parsed, task["metadata"])
            append_jsonl(
                output_path,
                {
                    "task_id": task["task_id"],
                    "model": model,
                    "metadata": task["metadata"],
                    "output": parsed,
                    "raw_response": response,
                },
            )
            processed += 1
            if sleep_seconds:
                time.sleep(sleep_seconds)
        except Exception as exc:
            append_jsonl(
                errors_path,
                {
                    "task_id": task["task_id"],
                    "model": model,
                    "metadata": task["metadata"],
                    "error": str(exc),
                },
            )
            failed += 1

    return {
        "processed": processed,
        "failed": failed,
        "output_path": str(output_path),
        "errors_path": str(errors_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-path", default=str(DEFAULT_TASKS_PATH))
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--errors-path", default=str(DEFAULT_ERRORS_PATH))
    parser.add_argument("--developer-prompt-path", default=str(DEFAULT_DEVELOPER_PROMPT_PATH))
    parser.add_argument("--user-prompt-path", default=str(DEFAULT_USER_PROMPT_PATH))
    parser.add_argument("--schema-path", default=str(DEFAULT_SCHEMA_PATH))
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--api-key-env", default="NVIDIA_NIM_API_KEY")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--max-retries", type=int, default=5)
    args = parser.parse_args()

    api_key = os.environ.get(args.api_key_env) or os.environ.get("NIM_API_KEY")
    if not api_key:
        raise SystemExit(
            f"Missing API key. Set {args.api_key_env} or NIM_API_KEY in the environment before running."
        )

    result = process_tasks(
        tasks_path=Path(args.tasks_path),
        output_path=Path(args.output_path),
        errors_path=Path(args.errors_path),
        developer_prompt_path=Path(args.developer_prompt_path),
        user_prompt_path=Path(args.user_prompt_path),
        schema_path=Path(args.schema_path),
        api_key=api_key,
        api_url=args.api_url,
        model=args.model,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        limit=args.limit,
        sleep_seconds=args.sleep_seconds,
        max_retries=args.max_retries,
    )
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
