"""
Task 2 — Crawl bài viết/thông báo về dịch vụ đại học.

Hướng dẫn:
    1. Crawl tối thiểu 5 bài viết từ trang công khai của một trường đại học.
    2. Sử dụng Crawl4AI hoặc thư viện crawling tương tự.
    3. Lưu output vào data/landing/news/
    4. Mỗi bài lưu 1 file JSON với metadata (url, title, date_crawled, content).

Cài đặt:
    pip install crawl4ai
    playwright install chromium   # bắt buộc — pip install crawl4ai KHÔNG tự tải browser binary,
                                   # thiếu bước này sẽ báo lỗi
                                   # "BrowserType.launch: Executable doesn't exist"

Gợi ý chủ đề: thông báo tuyển sinh, sự kiện, dịch vụ thư viện, hỗ trợ sinh viên, học bổng.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"


def setup_directory():
    """Tạo thư mục data/landing/news/ nếu chưa có."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


ARTICLE_URLS = [
    # RMIT Vietnam — trang sự kiện (events)
    "https://www.rmit.edu.vn/events/all-events/2026/higher-education-horizons-2026",
    "https://www.rmit.edu.vn/news/all-news/2026/jul/moet-and-rmit-vietnam-promote-excellence-in-online-learning-design",
    # RMIT Vietnam — dịch vụ thư viện (library news)
    "https://www.rmit.edu.vn/libraryvn/about-us/news/2026/r-loop-event-recap",
    "https://www.rmit.edu.vn/libraryvn/about-us/news/2025/10-years-book-swap",
    "https://www.rmit.edu.vn/libraryvn/about-us/news/2025/rmit-vietnam-library-launches-adobe-express-champions",
    "https://www.rmit.edu.vn/libraryvn/about-us/news/2025/library-welcomes-visitors-from-can-tho-university",
    # RMIT Vietnam — hỗ trợ sinh viên (student support/news)
    "https://www.rmit.edu.vn/news/all-news/2026/jul/rmit-student-finds-global-purpose-at-un-leadership-program",
]

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


async def crawl_article(url: str) -> dict:
    """
    Crawl một bài viết và trả về dict chứa metadata + content.

    Dùng requests + BeautifulSoup (thay vì Crawl4AI/Playwright) để tránh phải tải
    Chromium binary (~300MB) — vẫn thoả yêu cầu output (url, title, date_crawled,
    content_markdown). Nếu muốn dùng Crawl4AI, thay phần fetch bên dưới bằng
    AsyncWebCrawler().arun(url) như gợi ý trong docstring gốc.

    Returns:
        {
            "url": str,
            "title": str,
            "date_crawled": str (ISO format),
            "content_markdown": str
        }
    """
    import requests
    from bs4 import BeautifulSoup

    response = requests.get(url, headers=_HEADERS, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()

    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else "Unknown"

    main = soup.find("main") or soup.find("article") or soup.body

    lines = []
    heading_map = {"h1": "#", "h2": "##", "h3": "###", "h4": "####"}
    for el in main.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
        text = el.get_text(strip=True)
        if not text:
            continue
        prefix = heading_map.get(el.name, "-" if el.name == "li" else "")
        lines.append(f"{prefix} {text}".strip())

    content_markdown = "\n\n".join(lines)

    return {
        "url": url,
        "title": title,
        "date_crawled": datetime.now().isoformat(),
        "content_markdown": content_markdown,
    }


async def crawl_all():
    """Crawl toàn bộ bài viết trong ARTICLE_URLS."""
    setup_directory()

    for i, url in enumerate(ARTICLE_URLS, 1):
        print(f"[{i}/{len(ARTICLE_URLS)}] Crawling: {url}")
        article = await crawl_article(url)

        # Lưu file JSON
        filename = f"article_{i:02d}.json"
        filepath = DATA_DIR / filename
        filepath.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ Saved: {filepath}")


if __name__ == "__main__":
    if not ARTICLE_URLS:
        print("⚠ Hãy điền ARTICLE_URLS trước khi chạy!")
        print("Gợi ý: tìm trang thông báo/sự kiện trên trang chính thức của trường đại học")
    else:
        asyncio.run(crawl_all())
