#!/usr/bin/env python3
"""Run the three-round GPT-5.5 Pro pipeline with checkpoint/resume support."""

import json
import os
import time
from pathlib import Path

import md2html


# ── Configuration ──────────────────────────────────────────────────────────────

API_KEY = ""  # Paste your API key here, or use the OPENAI_API_KEY environment variable
RUN_DIR = "output"

SYSTEM_PROMPT = """The provided theorem was recently proved, and the result is now accepted by the mathematical community. Your task is to independently construct a proof."""

ROUND_PROMPTS = [
    r"""**Theorem.** There exist an absolute constant $\delta > 0$ and an infinite sequence $\{P_i\}$ of finite point sets in $\mathbb{R}^2$ such that $|P_i| \to \infty$ and $u(P_i) \ge |P_i|^{1+\delta}$ for all $i$, where $u(P_i) = \frac{1}{2} | \{ (p,q) \in P_i \times P_i : \|p-q\|_2 = 1 \} |$ is the number of unit-distance pairs.

**Remark.** This result disproves the Erdős Unit Distance Conjecture.

***

As a first step, brainstorm and propose three most promising approaches to prove this theorem. Explore each approach to sufficient depth, and then rank them from most to least promising.""",

    "Thoroughly develop your top-ranked approach to construct a complete and rigorous proof, adapting your strategy as needed.",

    "Critically examine the proof you constructed to identify and resolve any errors or logical gaps. Then, present a complete, rigorous, step-by-step proof. Clearly justify each step with sufficient detail so that an expert can verify your reasoning without needing to fill in any gaps.",
]

MODEL = "gpt-5.5-pro-2026-04-23"
REASONING_EFFORT = "xhigh"
TEXT_VERBOSITY = ["high", "high", "medium"]
STORE = True
BACKGROUND = True
POLL_INTERVAL_SECONDS = 30
DELAY_BETWEEN_ROUNDS_SECONDS = 60


# ── Helpers ────────────────────────────────────────────────────────────────────

def drop_none(value):
    """Recursively remove None values from dicts and lists."""
    if isinstance(value, dict):
        return {k: drop_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [drop_none(v) for v in value]
    return value


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def get_output_text(raw_response):
    """Extract visible output text from a raw API response dict."""
    parts = []
    for item in raw_response.get("output", []):
        for content in item.get("content", []):
            if content.get("text"):
                parts.append(content["text"])
    return "\n".join(parts).strip()


# ── Core ───────────────────────────────────────────────────────────────────────

def run_round(client, round_number, previous_response_id, run_dir):
    """Submit or resume one round, poll until complete.

    Returns (response_id, raw_dict, output_text).
    """
    checkpoint = run_dir / "_checkpoint.json"
    response = None

    # Resume an in-progress request for this round.
    if checkpoint.exists():
        state = load_json(checkpoint)
        if state.get("round") == round_number:
            print(f"Round {round_number}: resuming response {state['response_id']}.")
            response = client.responses.retrieve(state["response_id"])

    # Submit a new request.
    if response is None:
        request = drop_none({
            "model": MODEL,
            "instructions": SYSTEM_PROMPT.strip() or None,
            "input": ROUND_PROMPTS[round_number - 1],
            "previous_response_id": previous_response_id,
            "reasoning": {"effort": REASONING_EFFORT},
            "text": {"format": {"type": "text"}, "verbosity": TEXT_VERBOSITY[round_number - 1]},
            "tools": [],
            "store": STORE,
            "background": BACKGROUND,
        })
        print(f"Round {round_number}: creating response.")
        response = client.responses.create(**request)
        save_json(checkpoint, {"round": round_number, "response_id": response.id})

    # Poll until no longer active.
    while response.status in {"queued", "in_progress"}:
        time.sleep(POLL_INTERVAL_SECONDS)
        response = client.responses.retrieve(response.id)

    # Clean up checkpoint.
    if checkpoint.exists():
        checkpoint.unlink()

    raw = response.model_dump(mode="json")

    if response.status != "completed":
        print(f"Round {round_number} error: {raw.get('error')}")
        raise SystemExit(f"Round {round_number} did not complete.")

    print(f"Round {round_number}: completed.")
    return response.id, raw, get_output_text(raw)


def main():
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise SystemExit("Install the OpenAI SDK: pip install --upgrade openai") from exc

    api_key = API_KEY or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Set API_KEY in this file, or set OPENAI_API_KEY before running.")

    run_dir = Path(RUN_DIR)
    run_dir.mkdir(parents=True, exist_ok=True)
    output_path = run_dir / "raw_outputs.json"

    # Load previously completed rounds (for checkpoint/resume).
    if output_path.exists():
        data = load_json(output_path)
    else:
        data = {"model": MODEL, "system_prompt": SYSTEM_PROMPT, "rounds": []}

    client = OpenAI(api_key=api_key)

    previous_response_id = None
    for round_number in (1, 2, 3):
        idx = round_number - 1

        # Skip already completed rounds.
        if idx < len(data["rounds"]):
            entry = data["rounds"][idx]
            if entry.get("response", {}).get("status") == "completed":
                print(f"Round {round_number}: already completed, skipping.")
                previous_response_id = entry["response"]["id"]
                continue

        response_id, raw, text = run_round(
            client, round_number, previous_response_id, run_dir
        )

        round_entry = {
            "round": round_number,
            "user_prompt": ROUND_PROMPTS[idx],
            "output_text": text,
            "response": raw,
        }
        if idx < len(data["rounds"]):
            data["rounds"][idx] = round_entry
        else:
            data["rounds"].append(round_entry)

        save_json(output_path, data)
        previous_response_id = response_id

        if round_number < 3:
            time.sleep(DELAY_BETWEEN_ROUNDS_SECONDS)

    # ── Write human-readable outputs ──────────────────────────────────────────

    # proof.html — round 3 output only.
    proof_text = data["rounds"][2]["output_text"]
    (run_dir / "proof.html").write_text(md2html.make_html("Proof", proof_text + "\n"), encoding="utf-8")

    # transcript.html — full conversation with prompts.
    parts = ["# Transcript", ""]
    sys_prompt = "\n".join(f"> {line}" for line in data['system_prompt'].splitlines())
    parts += ["## System prompt", "", sys_prompt, "", "---", ""]
    for entry in data["rounds"]:
        rn = entry["round"]
        user_prompt = "\n".join(f"> {line}" for line in entry["user_prompt"].splitlines())
        parts += [f"# Round {rn}", "", "## User", "", user_prompt, ""]
        parts += ["## Assistant", "", entry["output_text"], "", "---", ""]
    
    transcript_text = "\n".join(parts).rstrip() + "\n"
    (run_dir / "transcript.html").write_text(md2html.make_html("Transcript", transcript_text), encoding="utf-8")

    print(f"\nPipeline complete. Outputs in {run_dir}/")
    print(f"  raw_outputs.json  — full API responses")
    print(f"  proof.html        — final proof (round 3)")
    print(f"  transcript.html   — full conversation")


if __name__ == "__main__":
    main()
