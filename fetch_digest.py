#!/usr/bin/env python3
"""Daily AI Newsletter Digest — Claude searches the web for AI news."""

from datetime import datetime, timezone
import anthropic

SOURCES = [
    "TLDR AI (tldr.tech/ai)",
    "The Rundown AI (therundown.ai)",
    "Superhuman AI (superhuman.ai)",
    "Import AI by Jack Clark (importai.substack.com)",
    "Turing Post (turingpost.com)",
    "Augmented Coding Weekly (augmentedcoding.substack.com)",
]


def build_digest() -> str:
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    sources_list = "\n".join(f"- {s}" for s in SOURCES)

    client = anthropic.Anthropic()
    messages = []

    # ── Phase 1: research ─────────────────────────────────────────────────────
    # Let Claude search the web; we don't care about any text it emits here —
    # only the accumulated tool results matter for the next phase.
    messages.append({"role": "user", "content": (
        f"Today is {today}. Search the web and find the most important AI news "
        "and developments from the last 24 hours. Focus on these sources:\n"
        f"{sources_list}\n\n"
        "Also check for any other significant AI news published today."
    )})

    for _ in range(5):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            tools=[
                {"type": "web_search_20260209", "name": "web_search"},
                {"type": "web_fetch_20260209",  "name": "web_fetch"},
            ],
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "end_turn":
            break
        # pause_turn → keep going until done

    # ── Phase 2: write ────────────────────────────────────────────────────────
    # No tools — Claude must output the digest directly, no planning text.
    messages.append({"role": "user", "content": (
        "Based on your research, write the daily AI digest right now. "
        "Begin immediately with the first line below — no preamble, no explanation.\n\n"
        f"*AI Digest – {today}*\n\n"
        "Group items under whichever sections apply:\n"
        "*🛠 Dev Tools*   *🧠 Models*   *🚀 Releases*   *📰 Industry News*\n\n"
        "Rules:\n"
        "• 2–3 bullets per section, one developer-focused sentence each\n"
        "• Bold key names/terms with *asterisks*\n"
        "• 300–400 words total\n"
        f"• Last line: *💡 Today's Takeaway:* 1–2 sentences"
    )})

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=messages,          # no tools — pure writing turn
    )

    for block in response.content:
        if block.type == "text":
            return block.text

    return f"*AI Digest – {today}*\n\n📭 Could not generate digest."


def main() -> None:
    run_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"=== AI Newsletter Digest — {run_time} ===\n")

    print("Claude is searching the web for AI news...")
    digest = build_digest()

    print("\n" + "=" * 60)
    print(digest)
    print("=" * 60 + "\n")

    output = f"AI Newsletter Digest — {run_time}\n{'=' * 60}\n\n{digest}\n"
    with open("digest.txt", "w", encoding="utf-8") as f:
        f.write(output)
    print("Saved to digest.txt")


if __name__ == "__main__":
    main()