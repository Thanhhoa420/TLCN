"""
crawler/itviec_crawler.py (ĐÃ SỬA sau khi kiểm tra HTML thật qua DevTools)
Cào ITviec theo 2 bước: (1) lấy URL tin theo khu vực, (2) crawl chi tiết từng tin.

THAY ĐỔI QUAN TRỌNG so với bản trước:
- Dùng attribute data-layer-value (JSON có sẵn) để lấy tieu_de, ky_nang,
  ten_cong_ty, dia_diem thay vì tự suy đoán selector -> đáng tin cậy hơn nhiều.
- Sửa lại tên heading mô tả công việc theo tiếng Việt ("Mô tả công việc",
  "Yêu cầu ứng viên"...) vì trang hiển thị mặc định theo html lang="vi-VN".
"""
import requests
from bs4 import BeautifulSoup
import time
import json
import random
import os
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9",  # ép ngôn ngữ Việt để nhất quán khi crawl
}

CITIES = {
    "ho-chi-minh": "ho-chi-minh-hcm",
    "ha-noi": "ha-noi",
    "da-nang": "da-nang",
}

MAX_PAGES_PER_CITY = 15
RAW_DIR = "crawler/raw_data"
JOBS_DIR = os.path.join(RAW_DIR, "jobs")
URLS_PATH = os.path.join(RAW_DIR, "job_urls.json")

os.makedirs(JOBS_DIR, exist_ok=True)


def clean_text(text):
    if not text:
        return None
    return re.sub(r"\s+", " ", text).strip()


# ---------- BƯỚC 1: LẤY URL TIN THEO KHU VỰC (giữ nguyên, đã verify đúng) ----------

def get_job_urls_for_city(city_slug, max_pages=MAX_PAGES_PER_CITY):
    job_urls = set()
    for page in range(1, max_pages + 1):
        url = f"https://itviec.com/it-jobs/{city_slug}?page={page}"
        print(f"[{city_slug}] Đang lấy trang {page}: {url}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  Lỗi khi tải trang: {e}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")

        # Tin chi tiết luôn có URL dạng /it-jobs/{ten-tin}-{4-chu-so}
        # (ví dụ: /it-jobs/lead-backend-engineer-java-...-3506), khác với các
        # link menu/filter như /it-jobs/java, /it-jobs/backend-developer
        job_links = soup.select("a[href*='/it-jobs/']")
        found_this_page = set()

        for a in job_links:
            href = a.get("href")
            if not href:
                continue
            clean_href = href.split("?")[0]
            # Chỉ nhận URL kết thúc bằng dấu gạch ngang + 4 chữ số (mã tin)
            if re.search(r"-\d{4}$", clean_href):
                found_this_page.add(clean_href)

        if not found_this_page:
            print(f"  Không còn tin nào ở trang {page}, dừng lại.")
            break

        for href in found_this_page:
            job_urls.add("https://itviec.com" + href)

        print(f"  Tìm thấy {len(found_this_page)} tin ở trang {page}")

        time.sleep(random.uniform(1, 3))

    return list(job_urls)


def step1_collect_urls():
    all_urls = {}
    for city_key, city_slug in CITIES.items():
        urls = get_job_urls_for_city(city_slug)
        all_urls[city_key] = urls
        print(f"=> {city_key}: thu được {len(urls)} URL tin tuyển dụng\n")

    with open(URLS_PATH, "w", encoding="utf-8") as f:
        json.dump(all_urls, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in all_urls.values())
    print(f"[Bước 1] Hoàn tất. Tổng {total} URL đã lưu vào {URLS_PATH}")
    return all_urls


# ---------- BƯỚC 2: CRAWL CHI TIẾT — ĐÃ SỬA DÙNG data-layer-value ----------

# Các heading có thể gặp cho phần mô tả/yêu cầu/quyền lợi, cả tiếng Việt lẫn Anh
# (site đổi ngôn ngữ tùy theo Accept-Language / cookie người dùng)
HEADING_MO_TA = ["Mô tả công việc", "Job description"]
HEADING_YEU_CAU = ["Yêu cầu ứng viên", "Kỹ năng của bạn", "Your skills and experience"]
HEADING_QUYEN_LOI = [
    "Tại sao bạn sẽ thích làm việc tại đây", "Why you'll love working here",
    "Top 3 lý do để gia nhập chúng tôi", "Top 3 reasons to join us",
]


def extract_data_layer(soup):
    """Lấy JSON từ attribute data-layer-value trên div.jd-main — nguồn dữ liệu
    đáng tin cậy nhất vì do chính ITviec render sẵn cho mục đích tracking."""
    container = soup.select_one("[data-layer-value]")
    if not container:
        return {}
    raw = container.get("data-layer-value")
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def extract_section_by_headings(soup, heading_candidates):
    """Tìm h2 có text khớp 1 trong các heading_candidates (không phân biệt hoa/thường),
    lấy toàn bộ nội dung cho tới h2 tiếp theo."""
    for h2 in soup.find_all("h2"):
        heading = clean_text(h2.get_text())
        if not heading:
            continue
        if any(cand.lower() in heading.lower() for cand in heading_candidates):
            content_parts = []
            for sib in h2.find_next_siblings():
                if sib.name == "h2":
                    break
                text = clean_text(sib.get_text())
                if text:
                    content_parts.append(text)
            return "\n".join(content_parts)
    return None


def crawl_job_detail(url):
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    data = {"url": url}
    layer = extract_data_layer(soup)

    # --- Ưu tiên lấy từ data-layer-value (đáng tin cậy) ---
    data["tieu_de"] = layer.get("job_title")
    data["ten_cong_ty"] = layer.get("job_by_company")
    data["dia_diem_raw"] = layer.get("job_by_city")
    data["salary_range_raw"] = layer.get("salary_range") or None  # thường rỗng do bị ẩn

    ky_nang_raw = layer.get("job_required_skill", "")
    data["ky_nang"] = [s.strip() for s in ky_nang_raw.split(",") if s.strip()] if ky_nang_raw else []

    # --- Fallback bằng h1 nếu data-layer-value không có (phòng trường hợp thay đổi) ---
    if not data["tieu_de"]:
        h1 = soup.find("h1")
        data["tieu_de"] = clean_text(h1.get_text()) if h1 else None

    # --- Hình thức làm việc (At office / Remote / Hybrid — vẫn thường giữ tiếng Anh) ---
    hinh_thuc_el = soup.find(string=re.compile(r"^(At office|Remote|Hybrid|Tại văn phòng)$"))
    data["hinh_thuc_lam_viec"] = clean_text(hinh_thuc_el) if hinh_thuc_el else None

    # --- Mô tả / yêu cầu / quyền lợi — dò theo heading tiếng Việt lẫn tiếng Anh ---
    data["mo_ta_cong_viec"] = extract_section_by_headings(soup, HEADING_MO_TA)
    data["yeu_cau"] = extract_section_by_headings(soup, HEADING_YEU_CAU)
    data["quyen_loi"] = extract_section_by_headings(soup, HEADING_QUYEN_LOI)

    # --- Hạn ứng tuyển (meta unavailable_after vẫn giữ nguyên bất kể ngôn ngữ) ---
    meta_expire = soup.find("meta", attrs={"name": re.compile("unavailable_after", re.I)})
    data["han_ung_tuyen_raw"] = meta_expire["content"] if meta_expire else None

    # --- Thông tin công ty ---
    data["loai_hinh_cong_ty"] = None
    data["quy_mo_cong_ty"] = None
    for label_text in ["Company type", "Loại hình công ty"]:
        label = soup.find(string=re.compile(f"^{re.escape(label_text)}$"))
        if label:
            data["loai_hinh_cong_ty"] = clean_text(label.find_next(string=True))
            break
    for label_text in ["Company size", "Quy mô công ty"]:
        label = soup.find(string=re.compile(f"^{re.escape(label_text)}$"))
        if label:
            data["quy_mo_cong_ty"] = clean_text(label.find_next(string=True))
            break

    return data


def step2_crawl_details(all_urls):
    count = 0
    for city, urls in all_urls.items():
        for url in urls:
            job_id = url.rstrip("/").split("/")[-1]
            out_path = os.path.join(JOBS_DIR, f"{job_id}.json")

            if os.path.exists(out_path):
                continue

            print(f"[{city}] Crawling: {url}")
            try:
                data = crawl_job_detail(url)
                data["khu_vuc_crawl"] = city
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                count += 1
            except requests.RequestException as e:
                print(f"  Lỗi: {e}")

            time.sleep(random.uniform(1.5, 3.5))

    print(f"[Bước 2] Hoàn tất. Đã crawl {count} tin mới -> {JOBS_DIR}/")


def main():
    all_urls = step1_collect_urls()
    step2_crawl_details(all_urls)


if __name__ == "__main__":
    main()