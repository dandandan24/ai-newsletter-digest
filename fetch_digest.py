#!/usr/bin/env python3
"""Daily AI Newsletter Digest — fetches RSS feeds and summarizes with Claude."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import anthropic
import requests
from bs4 import BeautifulSoup

FEEDS = [
    ("TLDR AI",                 "https://tldr.tech/ai/rss",                 None),
    ("The Rundown AI",          "https://www.therundown.ai/feed",            None),
    ("Superhuman AI",           "https://www.superhuman.ai/feed",            None),
    ("Import AI",               "https://importai.substack.com/feed",        None),
    ("Turing Post",             "https://www.turingpost.com/feed",           "https://turingpost.substack.com/feed"),
    ("Augmented Coding Weekly", "https://augmentedcoding.substack.com/feed", None),
]

ATOM_NS = "http://www.w3.org/2005/Atom"
HEADERS = {"User-Agent": "AINewsDigest/1.0 (github.com/ai-digest)"}


# ── helpers ──────────────────────────────────────────────────────────────────

def parse_pub_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    s = date_str.strip()
    try:
        return parsedate_to_datetime(s)          # RFC 2822 (most RSS feeds)
    except Exception:
        pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))  # ISO 8601
    except Exception:
        return None


def strip_html(html: str, max_chars: int = 400) -> str:
    if not html:
        return ""
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    return text[:max_chars] if len(text) > max_chars else text


def _el_text(parent: ET.Element, tag: str) -> str:
    el = parent.find(tag)
    return (el.text or "").strip() if el is not None else ""


# ── feed parsing ──────────────────────────────────────────────────────────────

def parse_feed(name: str, xml_bytes: bytes, cutoff: datetime) -> list[dict]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        print(f"  [{name}] XML parse error: {exc}", file=sys.stderr)
        return []

    items: list[dict] = []
    is_atom = root.tag == f"{{{ATOM_NS}}}feed"

    if is_atom:
        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
            pub_date = parse_pub_date(
                _el_text(entry, f"{{{ATOM_NS}}}published")
                or _el_text(entry, f"{{{ATOM_NS}}}updated")
            )
            if not (pub_date and pub_date > cutoff):
                continue

            link_el = entry.find(f"{{{ATOM_NS}}}link[@rel='alternate']")
            if link_el is None:
                link_el = entry.find(f"{{{ATOM_NS}}}link")
            link = link_el.get("href", "") if link_el is not None else ""

            summary = strip_html(
                _el_text(entry, f"{{{ATOM_NS}}}summary")
                or _el_text(entry, f"{{{ATOM_NS}}}content")
            )
            items.append({
                "source": name,
                "title": _el_text(entry, f"{{{ATOM_NS}}}title"),
                "link": link,
                "summary": summary,
            })
    else:
        for item in root.findall(".//item"):
            pub_date = parse_pub_date(_el_text(item, "pubDate"))
            if not (pub_date and pub_date > cutoff):
                continue
            items.append({
                "source": name,
                "title": _el_text(item, "title"),
                "link": _el_text(item, "link"),
                "summary": strip_html(_el_text(item, "description")),
            })

    return items


def fetch_feed(name: str, url: str, fallback: str | None, cutoff: datetime) -> list[dict]:
    urls = [url] + ([fallback] if fallback else [])
    for feed_url in urls:
        try:
            resp = requests.get(feed_url, timeout=15, headers=HEADERS)
            resp.raise_for_status()
            items = parse_feed(name, resp.content, cutoff)
            print(f"  [{name}] {len(items)} items in last 24h")
            return items
        except Exception as exc:
            print(f"  [{name}] {feed_url} — {exc}", file=sys.stderr)
    return []


def collect_items() -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    all_items: list[dict] = []
    for name, url, fallback in FEEDS:
        all_items.extend(fetch_feed(name, url, fallback, cutoff))
    return all_items


# ── Claude summarisation ──────────────────────────────────────────────────────

def build_digest(items: list[dict]) -> str:
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")

    if not items:
        return f"*AI Digest – {today}*\n\n📭 No new items found in the last 24 hours."

    items_block = ""
    for it in items:
        items_block += f"\n[{it['source']}] {it['title']}\n"
        if it["summary"]:
            items_block += f"  {it['summary']}\n"

    prompt = (
        f"You are an AI newsletter curator for software developers. "
        f"Below are AI news items from the last 24 hours (as of {today}). "
        "Create a WhatsApp-ready daily digest.\n\n"
        "Format rules:\n"
        "- Start with: *AI Digest – {today}*\n"
        "- Group items under bold headers: *🛠 Dev Tools*, *🧠 Models*, *🚀 Releases*, *📰 Industry News*\n"
        "- Only include a section if there are relevant items for it\n"
        "- 2–3 bullet points per section, one sentence each, developer-focused\n"
        "- Use *asterisks* for bold on key terms (WhatsApp bold)\n"
        "- Plain text only — no markdown headers (# or ##), no bullet dashes for top-level sections\n"
        "- Total length: 300–400 words\n"
        "- End with: *💡 Today's Takeaway:* (1–2 sentences from a developer perspective)\n\n"
        f"News items:\n{items_block}\n\n"
        "Write the digest:"
    )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    run_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"=== AI Newsletter Digest — {run_time} ===\n")

    print("Fetching RSS feeds...")
    items = collect_items()
    print(f"Total items collected: {len(items)}\n")

    print("Summarising with Claude...")
    digest = build_digest(items)

    print("\n" + "=" * 60)
    print(digest)
    print("=" * 60 + "\n")

    output = f"AI Newsletter Digest — {run_time}\n{'=' * 60}\n\n{digest}\n"
    with open("digest.txt", "w", encoding="utf-8") as f:
        f.write(output)
    print("Saved to digest.txt")


if __name__ == "__main__":
    main()