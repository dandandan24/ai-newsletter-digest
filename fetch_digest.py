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

    prompt = (
        f"Today is {today}. You are creating a daily AI newsletter digest for software developers.\n\n"
        "Search the web for the latest AI news and developments from the last 24 hours. "
        f"Prioritise content from these newsletters, but also include other major AI news:\n{sources_list}\n\n"
        "After searching, write a WhatsApp-ready digest following these rules:\n"
        f"- First line: *AI Digest – {today}*\n"
        "- Group into sections (only include if you found relevant items):\n"
        "    *🛠 Dev Tools*  *🧠 Models*  *🚀 Releases*  *📰 Industry News*\n"
        "- 2–3 bullet points per section, one sentence each, developer-focused\n"
        "- Bold key terms with *asterisks* (WhatsApp bold)\n"
        "- Plain text only — no ## markdown headers\n"
        "- Total length: 300–400 words\n"
        "- Final line: *💡 Today's Takeaway:* one or two sentences for developers"
    )

    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": prompt}]

    # Server-side web_search runs internally; pause_turn means Claude needs another turn.
    for _ in range(5):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            tools=[
                {"type": "web_search_20260209", "name": "web_search"},
                {"type": "web_fetch_20260209",  "name": "web_fetch"},
            ],
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if block.type == "text":
                    return block.text
            break

        if response.stop_reason == "pause_turn":
            messages = [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response.content},
            ]
            continue

        break

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