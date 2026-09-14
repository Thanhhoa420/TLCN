"""
crawler/topcv_crawler.py
Cào TRANG DANH SÁCH của TopCV (không vào trang chi tiết) để lấy lương công khai.
Dùng bổ sung trường lương cho seed data (ITviec ẩn lương sau đăng nhập).
"""
import requests
from bs4 import BeautifulSoup
import time
import random
import json
import re
import os

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

LISTING_URL = "https://www.topcv.vn/tim-viec-lam-cong-nghe-thong-tin-cr257?category_ids=257&page={page}"
MAX_PAGES = 15
RAW_PATH = "crawler/raw_data/topcv_salary_listing.json"


def parse_salary(text):
    if not text:
        return None, None
    text = text.strip()
    if "thoả thuận" in text.lower() or "thỏa thuận" in text.lower():
        return None, None

    m = re.search(r"([\d.,]+)\s*-\s*([\d.,]+)\s*triệu", text, re.I)
    if m:
        lo = float(m.group(1).replace(",", "."))
        hi = float(m.group(2).replace(",", "."))
        return int(lo * 1_000_000), int(hi * 1_000_000)

    m = re.search(r"(Từ|Tới)\s*([\d.,]+)\s*triệu", text, re.I)
    if m:
        val = int(float(m.group(2).replace(",", ".")) * 1_000_000)
        return (val, None) if m.group(1).lower() == "từ" else (None, val)

    return None, None


def crawl_listing_page(url):
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    jobs = []
    job_links = soup.select("a[href*='/viec-lam/']")
    seen_urls = set()

    for a in job_links:
        href = a.get("href")
        if not href or href in seen_urls:
            continue
        seen_urls.add(href)

        card = a.find_parent(["div", "li"])
        if not card:
            continue
        card_text = card.get_text(separator="|", strip=True)

        title = a.get_text(strip=True)
        if not title:
            continue

        salary_match = re.search(
            r"([\d.,]+\s*-\s*[\d.,]+\s*triệu|Từ\s*[\d.,]+\s*triệu|Tới\s*[\d.,]+\s*triệu|Th[oỏ]a?\s*thu[aậ]n)",
            card_text, re.I
        )
        salary_raw = salary_match.group(1) if salary_match else None

        exp_match = re.search(r"(Không yêu cầu|Dưới 1 năm|\d+\s*năm)", card_text)
        kinh_nghiem_raw = exp_match.group(1) if exp_match else None

        jobs.append({
            "url": "https://www.topcv.vn" + href if href.startswith("/") else href,
            "tieu_de": title,
            "luong_raw": salary_raw,
            "kinh_nghiem_raw": kinh_nghiem_raw,
        })

    return jobs


def main():
    os.makedirs(os.path.dirname(RAW_PATH), exist_ok=True)
    all_jobs = []

    for page in range(1, MAX_PAGES + 1):
        url = LISTING_URL.format(page=page)
        print(f"Đang lấy trang {page}: {url}")
        try:
            jobs = crawl_listing_page(url)
        except requests.RequestException as e:
            print(f"  Lỗi: {e}")
            break

        if not jobs:
            print("  Không còn tin, dừng lại.")
            break

        for j in jobs:
            lo, hi = parse_salary(j["luong_raw"])
            j["luong_min"] = lo
            j["luong_max"] = hi

        all_jobs.extend(jobs)
        time.sleep(random.uniform(1.5, 3))

    with open(RAW_PATH, "w", encoding="utf-8") as f:
        json.dump(all_jobs, f, ensure_ascii=False, indent=2)

    print(f"Hoàn tất. Thu được {len(all_jobs)} tin (kèm lương) -> {RAW_PATH}")


if __name__ == "__main__":
    main()