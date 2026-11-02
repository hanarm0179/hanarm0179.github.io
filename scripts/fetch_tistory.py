"""티스토리 RSS를 읽어 posts.json으로 저장하는 스크립트.

GitHub Actions에서 주기적으로 실행됩니다. 외부 패키지 없이 파이썬 기본 기능만 씁니다.
"""

import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

BLOG_URL = "https://hanarm-fanfic.tistory.com"
RSS_URL = f"{BLOG_URL}/rss"
OUTPUT = Path(__file__).resolve().parent.parent / "posts.json"
MAX_POSTS = 12          # 페이지에 보여줄 최대 글 수
SUMMARY_LEN = 110       # 요약 글자 수


def fetch_rss(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (github-pages-feed-bot)"},
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read()


def clean_text(raw_html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw_html or "", flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > SUMMARY_LEN:
        text = text[:SUMMARY_LEN].rstrip() + "…"
    return text


def first_image(raw_html: str) -> str | None:
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', raw_html or "", flags=re.I)
    return html.unescape(m.group(1)) if m else None


def parse(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    posts = []
    for item in root.iter("item"):
        desc = item.findtext("description") or ""
        date_raw = item.findtext("pubDate") or ""
        try:
            date = parsedate_to_datetime(date_raw).astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError):
            date = None
        posts.append(
            {
                "title": html.unescape((item.findtext("title") or "").strip()),
                "link": (item.findtext("link") or "").strip(),
                "date": date,
                "category": (item.findtext("category") or "").strip(),
                "summary": clean_text(desc),
                "thumbnail": first_image(desc),
            }
        )
    posts.sort(key=lambda p: p["date"] or "", reverse=True)
    return posts[:MAX_POSTS]


def main() -> int:
    try:
        posts = parse(fetch_rss(RSS_URL))
    except Exception as e:  # 실패하면 기존 파일을 그대로 둡니다
        print(f"RSS를 가져오지 못했습니다: {e}", file=sys.stderr)
        return 1

    if not posts:
        print("RSS에 글이 없어 기존 파일을 유지합니다.", file=sys.stderr)
        return 1

    data = {"blog": BLOG_URL, "posts": posts}
    new = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    old = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
    if new != old:
        OUTPUT.write_text(new, encoding="utf-8")
        print(f"posts.json 갱신: {len(posts)}개")
    else:
        print("변경 사항 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
