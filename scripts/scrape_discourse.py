"""Generated with Claude Code.

Scrape a Discourse forum and save posts as JSONL for LoRA training data.

Usage:
    python scrape_discourse.py --base-url https://us.forums.blizzard.com/en/wow --pages 50 --out wow_posts.jsonl
    python scrape_discourse.py --base-url https://us.forums.blizzard.com/en/wow --category general --pages 20
"""

import argparse
import json
import time
import sys
from pathlib import Path

import requests

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "ForBot-Scraper/1.0 (research)"


def get(url: str, retries: int = 3) -> dict | None:
    for attempt in range(retries):
        try:
            r = SESSION.get(url, timeout=15)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 10))
                print(f"  rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == retries - 1:
                print(f"  failed {url}: {e}")
                return None
            time.sleep(2 ** attempt)
    return None


def iter_threads(base: str, category: str | None, pages: int, start_page: int = 0):
    for page in range(start_page, start_page + pages):
        if category:
            url = f"{base}/c/{category}.json?page={page}"
        else:
            url = f"{base}/latest.json?page={page}"
        data = get(url)
        if not data:
            break
        topics = data.get("topic_list", {}).get("topics", [])
        if not topics:
            break
        yield from topics
        time.sleep(0.5)


def fetch_thread_posts(base: str, topic_id: int) -> list[dict]:
    posts = []
    data = get(f"{base}/t/{topic_id}.json")
    if not data:
        return posts

    stream = data.get("post_stream", {})
    posts.extend(stream.get("posts", []))

    # Fetch remaining post ids if thread has more than the first page
    remaining = stream.get("stream", [])[len(posts):]
    chunk_size = 20
    for i in range(0, len(remaining), chunk_size):
        ids = remaining[i : i + chunk_size]
        params = "&".join(f"post_ids[]={pid}" for pid in ids)
        more = get(f"{base}/t/{topic_id}/posts.json?{params}")
        if more:
            posts.extend(more.get("post_stream", {}).get("posts", []))
        time.sleep(0.3)

    return posts


def extract_post(post: dict, topic_title: str, topic_id: int) -> dict:
    return {
        "topic_id": topic_id,
        "topic_title": topic_title,
        "post_id": post.get("id"),
        "post_number": post.get("post_number"),
        "reply_to_post_number": post.get("reply_to_post_number"),
        "username": post.get("username"),
        "created_at": post.get("created_at"),
        "content": post.get("cooked", ""),   # HTML
        "raw": post.get("raw", ""),          # Markdown (may be empty without auth)
        "like_count": post.get("like_count", 0),
        "reads": post.get("reads", 0),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://us.forums.blizzard.com/en/wow")
    parser.add_argument("--category", default=None, help="Category slug (optional)")
    parser.add_argument("--pages", type=int, default=20, help="Pages of thread listings to fetch")
    parser.add_argument("--start-page", type=int, default=0, help="Skip listing pages before this index")
    parser.add_argument("--out", default="discourse_posts.jsonl")
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between thread requests")
    args = parser.parse_args()

    out_path = Path(args.out)
    seen_topics: set[int] = set()

    # Resume from existing file
    if out_path.exists():
        with open(out_path) as f:
            for line in f:
                try:
                    seen_topics.add(json.loads(line)["topic_id"])
                except Exception:
                    pass
        print(f"Resuming — {len(seen_topics)} topic IDs already seen")

    total_posts = 0
    with open(out_path, "a") as out:
        for topic in iter_threads(args.base_url, args.category, args.pages, args.start_page):
            tid = topic["id"]
            title = topic.get("title", "")
            if tid in seen_topics:
                continue
            seen_topics.add(tid)

            print(f"  [{tid}] {title[:72]}", end=" ... ", flush=True)
            posts = fetch_thread_posts(args.base_url, tid)
            for p in posts:
                row = extract_post(p, title, tid)
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"{len(posts)} posts")
            total_posts += len(posts)
            time.sleep(args.delay)

    print(f"\nDone. {total_posts} posts written to {out_path}")


if __name__ == "__main__":
    main()
