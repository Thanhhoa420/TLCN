"""
crawler/itviec_crawler.py
Cào ITviec theo 2 bước: (1) lấy URL tin theo khu vực, (2) crawl chi tiết từng tin.

Nguồn dữ liệu chính cho bước 2: khối <script type="application/ld+json"> có
@type=JobPosting — do ITviec tự sinh cho Google Jobs, cấu trúc ổn định hơn
nhiều so với dò heading trong DOM (vốn đổi tùy layout/gói tài khoản NTD).
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
    "Accept-Language": "vi-VN,vi;q=0.9",
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


def strip_html(fragment):
    """Chỉ chèn xuống dòng tại thẻ BLOCK (li/p/br) trước khi bóc tag —
    tránh vỡ dòng giữa câu do thẻ inline (<strong>, <i>, <a>...).
    Cũng chuẩn hóa \\r\\n có sẵn trong phần text thô (trước khi có HTML)."""
    if not fragment:
        return None
    fragment = fragment.replace("\r\n", "\n").replace("\r", "\n")
    fragment = re.sub(r"<(li|p|br)\b[^>]*/?>", "\n", fragment, flags=re.I)
    fragment = re.sub(r"</(li|p)>", "", fragment, flags=re.I)
    text = BeautifulSoup(fragment, "html.parser").get_text(separator="")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip() or None


# ---------- BƯỚC 1: LẤY URL TIN THEO KHU VỰC ----------

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
        job_links = soup.select("a[href*='/it-jobs/']")
        found_this_page = set()

        for a in job_links:
            href = a.get("href")
            if not href:
                continue
            clean_href = href.split("?")[0]
            if re.search(r"-\d{3,}$", clean_href):
                found_this_page.add(clean_href)

        if not found_this_page:
            print(f"  Không còn tin nào ở trang {page}, dừng lại.")
            break

        for href in found_this_page:
            job_urls.add(href if href.startswith("http") else "https://itviec.com" + href)

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


# ---------- BƯỚC 2: CRAWL CHI TIẾT (JSON-LD làm nguồn chính) ----------

SECTION_MARKERS = [
    ("intro", ["Top 3 Reasons To Join Us", "Top 3 lý do để gia nhập chúng tôi",
               "Top 3 reasons to join us"]),
    ("job", ["The Job", "Job Description", "Job description",
             "Mô tả công việc", "Job Responsibilities", "Your Job Responsibilities"]),
    ("requirements", ["Your Skills and Experience", "Your skills and experience",
                       "Yêu cầu ứng viên", "Kỹ năng của bạn"]),
    ("benefits", ["Why You'll Love Working Here", "Why you'll love working here",
                  "Tại sao bạn sẽ thích làm việc tại đây"]),
]

# ITviec dùng chuẩn schema.org cho employmentType -> chuẩn hóa về tập giá trị
# thống nhất với TopCV (danh_muc_loai_hinh_lam_viec). Đây là LOẠI HỢP ĐỒNG,
# khác hoàn toàn với hinh_thuc_lam_viec (At office/Remote/Hybrid = làm ở đâu).
EMPLOYMENT_TYPE_MAP = {
    "FULL_TIME": "Full-time",
    "PART_TIME": "Part-time",
    "INTERN": "Internship",
    "CONTRACTOR": "Contract",
    "TEMPORARY": "Contract",
}

# Nhãn cấp bậc (seniority level) mà ITviec có thể gộp lẫn vào chuỗi "skills"
# trong JSON-LD (badge riêng, không phải kỹ năng thật). Hiện chỉ phát hiện
# được case "Internship Accepted" qua cách này; Fresher/Junior/Senior/Manager
# là filter phía client-side của ITviec, không thấy trong dữ liệu trang chi
# tiết -> các case đó để None (TopCV sẽ là nguồn chính bổ sung cấp bậc).
CAP_BAC_SKILL_MARKERS = {
    "internship accepted": "Internship",
}


def split_job_description(desc):
    """So khớp không phân biệt hoa/thường vì nhãn section do nhà tuyển dụng/ITviec
    nhập tự do, KHÔNG đồng nhất giữa các tin. Không tìm thấy marker -> để None."""
    if not desc:
        return None, None, None

    positions = []
    for key, candidates in SECTION_MARKERS:
        best = None
        for cand in candidates:
            match = re.search(re.escape(cand), desc, re.IGNORECASE)
            if match and (best is None or match.start() < best[0]):
                best = (match.start(), key, len(match.group(0)))
        if best:
            positions.append(best)
    positions.sort(key=lambda x: x[0])

    sections = {}
    for i, (idx, key, label_len) in enumerate(positions):
        start = idx + label_len
        end = positions[i + 1][0] if i + 1 < len(positions) else len(desc)
        sections[key] = strip_html(desc[start:end])

    mo_ta = sections.get("job")
    yeu_cau = sections.get("requirements")
    quyen_loi = sections.get("benefits")

    if sections.get("intro"):
        quyen_loi = sections["intro"] if not quyen_loi else sections["intro"] + "\n\n" + quyen_loi

    return mo_ta, yeu_cau, quyen_loi


def extract_job_ld(soup):
    """Tìm khối JSON-LD có @type=JobPosting (trang có nhiều khối ld+json khác
    nhau: BreadcrumbList, WebSite... nên phải lọc đúng loại)."""
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and data.get("@type") == "JobPosting":
            return data
    return {}


def extract_data_layer(soup):
    """Backup/đối chiếu: attribute Stimulus data-jobs--save-data-layer-value."""
    container = soup.select_one("div.jd-main[data-jobs--save-data-layer-value]")
    if not container:
        container = soup.select_one("[data-jobs--save-data-layer-value]")
    if not container:
        return {}
    try:
        return json.loads(container.get("data-jobs--save-data-layer-value"))
    except (json.JSONDecodeError, TypeError):
        return {}


def extract_hinh_thuc_lam_viec(soup):
    """At office / Remote / Hybrid — LÀM VIỆC Ở ĐÂU, không phải loại hợp đồng."""
    el = soup.find(string=re.compile(r"^(At office|Remote|Hybrid|Tại văn phòng)$"))
    return clean_text(el) if el else None


def extract_han_ung_tuyen_meta(soup):
    meta = soup.find("meta", attrs={"name": re.compile(r"^googlebot$", re.I)})
    if meta and meta.get("content"):
        m = re.search(r"unavailable_after:\s*([^\r\n]+)", meta["content"])
        if m:
            return m.group(1).strip()
    return None


def normalize_not_available(value):
    if value and value.strip().lower() == "not available":
        return None
    return value


def extract_label_value(soup, label_variants):
    """So khớp label sau khi clean_text (bỏ khoảng trắng/xuống dòng thừa),
    rồi lấy text node KHÔNG rỗng gần nhất phía sau — bỏ qua text node
    whitespace-only nằm giữa các thẻ."""
    for label_text in label_variants:
        label_node = soup.find(string=lambda s: s and clean_text(s) == label_text)
        if not label_node:
            continue
        next_val = label_node.find_next(string=lambda s: bool(clean_text(s)))
        if next_val:
            return clean_text(next_val)
    return None


def extract_months_of_experience(ld):
    """experienceRequirements trong JSON-LD KHÔNG đồng nhất kiểu dữ liệu:
    có tin trả về dict {'@type':..., 'monthsOfExperience': 10}, có tin trả
    thẳng string (vd '10+ years') -> phải kiểm tra type trước khi .get().
    LƯU Ý: field này do ITviec tự ước lượng, không đáng tin để map trực tiếp
    kinh_nghiem_id (đã kiểm chứng: có tin ghi rõ "6+ years" nhưng field này
    lại ra 37 tháng/~3 năm) -> chỉ giữ tham khảo, ETL sẽ tự trích xuất từ
    yeu_cau bằng regex thay vì dùng field này."""
    exp = ld.get("experienceRequirements")
    if isinstance(exp, dict):
        return exp.get("monthsOfExperience")
    if isinstance(exp, str):
        return None  # để NULL, không tự suy đoán số tháng từ text tự do
    return None


def extract_loai_hinh_lam_viec(ld):
    """employmentType trong JSON-LD theo chuẩn schema.org -> chuẩn hóa về
    tập giá trị thống nhất với TopCV. Giá trị lạ/không map được -> None."""
    raw = ld.get("employmentType")
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    if not raw or not isinstance(raw, str):
        return None
    return EMPLOYMENT_TYPE_MAP.get(raw.strip().upper())


def extract_cap_bac_and_clean_skills(skills_list):
    """Một số badge cấp bậc (vd 'Internship Accepted') bị ITviec gộp lẫn vào
    chuỗi skills trong JSON-LD, KHÔNG phải kỹ năng thật -> tách riêng thành
    cap_bac, loại khỏi ky_nang. Trả về (ky_nang_da_loc, cap_bac)."""
    if not skills_list:
        return skills_list, None

    cap_bac = None
    cleaned = []
    for s in skills_list:
        key = s.strip().lower()
        if key in CAP_BAC_SKILL_MARKERS:
            cap_bac = CAP_BAC_SKILL_MARKERS[key]
        else:
            cleaned.append(s)
    return cleaned, cap_bac


def extract_multi_tag_field(soup, label_variants):
    """Tìm các thẻ <a> trong khối cha nhỏ nhất chứa label, không quét
    xuôi toàn bộ document để tránh lẫn link của navigation hoặc job khác."""
    for label_text in label_variants:
        label_node = soup.find(string=lambda s: s and clean_text(s) == label_text)
        if not label_node:
            continue
        block = label_node.find_parent()
        for _ in range(4):
            if block is None:
                break
            texts = [clean_text(a.get_text()) for a in block.find_all("a")]
            texts = [text for text in texts if text]
            if texts:
                return texts
            block = block.find_parent()
        return []
    return []

def extract_logo_from_img(img_tag):
    """Ảnh công ty trên ITviec dùng lazy-loading với thuộc tính data-src
    (KHÔNG phải src — đã xác nhận qua DevTools trên trang /companies/*),
    thường nằm trong <picture> có <source data-srcset> làm dự phòng."""
    if not img_tag:
        return None
    for attr in ["src", "data-src", "data-lazy-src", "data-original"]:
        val = img_tag.get(attr)
        if val and "review-company" not in val:
            return val
    picture = img_tag.find_parent("picture")
    if picture:
        source = picture.find("source")
        if source and source.get("data-srcset"):
            return source["data-srcset"].split(",")[0].strip().split(" ")[0]
    return None


def extract_company_info(soup):
    label = soup.find(string=lambda s: s and clean_text(s) == "Company type")
    if not label:
        return None, None, None

    CLEAN_COMPANY_URL = re.compile(r"^/companies/[a-z0-9\-]+/?$", re.I)

    # tăng limit để đỡ hụt khi DOM phía trước label dài hơn dự kiến
    candidates = list(label.find_all_previous("a", href=re.compile(r"/companies/"), limit=40))

    company_url = None
    for a in candidates:
        href = a.get("href", "")
        if CLEAN_COMPANY_URL.match(href.split("?")[0]):
            company_url = href.split("?")[0]
            break

    logo_url = None
    for a in candidates:
        logo_url = extract_logo_from_img(a.find("img"))
        if logo_url:
            break

    if not logo_url:
        for img in label.find_all_previous("img", limit=40):
            alt = (img.get("alt") or "").lower()
            cls = " ".join(img.get("class", [])).lower()
            if "logo" in alt or "logo" in cls:
                logo_url = extract_logo_from_img(img)
                if logo_url:
                    break

    # --- mo_ta: gộp toàn bộ text của thẻ cha chứa đoạn mô tả, thay vì 1 text node ---
    mo_ta = None
    prev_node = label.find_previous(
        string=lambda s: bool(clean_text(s)) and clean_text(s) != "Company type"
    )
    if prev_node:
        container = prev_node.find_parent()
        if container:
            full_text = clean_text(container.get_text(separator=" "))
            mo_ta = full_text if full_text else clean_text(prev_node)
        else:
            mo_ta = clean_text(prev_node)

    return logo_url, company_url, mo_ta

def extract_job_domain(soup):
    """Job Domain hiển thị dạng text thường (không phải link), có thể nhiều
    dòng. Lọc bỏ chính label 'Job Domain:' khỏi kết quả (bị lẫn vào do cách
    duyệt find_all_next)."""
    label_node = soup.find(string=lambda s: s and clean_text(s) == "Job Domain:")
    if not label_node:
        return []
    container = label_node.find_parent()
    if not container:
        return []
    domains = []
    for sib in container.find_all_next(string=True, limit=15):
        text = clean_text(sib)
        if not text:
            continue
        if text.rstrip(":").strip().lower() == "job domain":
            continue  # bỏ chính label, chỉ giữ các giá trị domain thật
        if re.match(r"^Top 3|^Job description$", text, re.I):
            break
        domains.append(text)
    return domains


def crawl_job_detail(url):
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    ld = extract_job_ld(soup)
    layer = extract_data_layer(soup)

    data = {"url": url}

    data["tieu_de"] = ld.get("title") or layer.get("job_title")
    data["ten_cong_ty"] = (ld.get("hiringOrganization") or {}).get("name") or layer.get("job_by_company")
    data["ngay_dang_raw"] = ld.get("datePosted")
    data["han_ung_tuyen_raw"] = ld.get("validThrough") or extract_han_ung_tuyen_meta(soup)

    skills_raw = ld.get("skills") or layer.get("job_required_skill", "")
    ky_nang_list = [s.strip() for s in skills_raw.split(",") if s.strip()] if skills_raw else []
    data["ky_nang"], data["cap_bac"] = extract_cap_bac_and_clean_skills(ky_nang_list)

    loc = (ld.get("jobLocation") or [{}])[0].get("address", {}) if ld.get("jobLocation") else {}
    data["dia_chi_raw"] = normalize_not_available(loc.get("streetAddress"))
    data["quan_huyen"] = normalize_not_available(loc.get("addressLocality"))
    data["tinh_thanh"] = normalize_not_available(loc.get("addressRegion")) or layer.get("job_by_city")

    base_salary = ld.get("baseSalary") or {}
    salary_value = base_salary.get("value")
    salary_val = salary_value.get("value") if isinstance(salary_value, dict) else salary_value
    data["salary_placeholder_raw"] = salary_val
    data["salary_range_raw"] = layer.get("salary_range") or None

    data["kinh_nghiem_thang"] = extract_months_of_experience(ld)
    data["loai_hinh_lam_viec"] = extract_loai_hinh_lam_viec(ld)

    mo_ta, yeu_cau, quyen_loi = split_job_description(ld.get("description"))
    data["mo_ta_cong_viec"] = mo_ta
    data["yeu_cau"] = yeu_cau
    data["quyen_loi"] = quyen_loi

    if not data["tieu_de"]:
        h1 = soup.find("h1")
        data["tieu_de"] = clean_text(h1.get_text()) if h1 else None
    if not data["ten_cong_ty"]:
        el = soup.select_one(".employer-name")
        data["ten_cong_ty"] = clean_text(el.get_text()) if el else None

    data["hinh_thuc_lam_viec"] = extract_hinh_thuc_lam_viec(soup)

    data["loai_hinh_cong_ty"] = extract_label_value(soup, ["Company type", "Loại hình công ty"])
    data["quy_mo_cong_ty"] = extract_label_value(soup, ["Company size", "Quy mô công ty"])

    data["company_logo_url"], data["company_url"], data["company_mo_ta"] = extract_company_info(soup)

    data["job_expertise"] = extract_multi_tag_field(soup, ["Job Expertise:"])
    data["job_domain"] = extract_job_domain(soup)

    return data


def crawl_job_detail_with_retry(url, max_retries=2):
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            return crawl_job_detail(url)
        except requests.RequestException as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(random.uniform(2, 4) * (attempt + 1))
                continue
            raise
    raise last_err


def step2_crawl_details(all_urls):
    count = 0
    error_count = 0
    for city, urls in all_urls.items():
        for url in urls:
            job_id = url.rstrip("/").split("/")[-1]
            out_path = os.path.join(JOBS_DIR, f"{job_id}.json")

            if os.path.exists(out_path):
                continue

            print(f"[{city}] Crawling: {url}")
            try:
                data = crawl_job_detail_with_retry(url)
                data["khu_vuc_crawl"] = city
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                count += 1
            except requests.RequestException as e:
                print(f"  Lỗi mạng: {e}")
                error_count += 1
            except Exception as e:
                # KHÔNG để 1 tin lỗi bất thường (parse, key thiếu...) làm sập
                # toàn bộ crawl các tin còn lại — log lại và crawl tiếp.
                print(f"  Lỗi xử lý tin ({type(e).__name__}): {e}")
                error_count += 1

            time.sleep(random.uniform(1.5, 3.5))

    print(f"[Bước 2] Hoàn tất. Đã crawl {count} tin mới, {error_count} tin lỗi -> {JOBS_DIR}/")


def find_and_remove_stale_files(jobs_dir=JOBS_DIR, required_keys=None):
    """Xóa các file JSON cũ được crawl bằng bản code trước đó (thiếu field mới
    thêm sau này) để step2_crawl_details() crawl lại đúng những tin đó, KHÔNG
    phải xóa/crawl lại toàn bộ. Chạy hàm này 1 lần trước khi crawl lại sau khi
    thêm field mới vào crawl_job_detail()."""
    if required_keys is None:
        required_keys = ["company_logo_url", "company_url", "cap_bac", "loai_hinh_lam_viec"]

    import glob
    removed = 0
    for path in glob.glob(f"{jobs_dir}/*.json"):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if any(key not in data or data[key] in (None, "", []) for key in required_keys):
            os.remove(path)
            removed += 1
    print(f"Đã xóa {removed} file cũ (thiếu field mới) để crawl lại.")


def test_quick():
    print("=== TEST BƯỚC 1: lấy URL (1 trang, HCM) ===")
    urls = get_job_urls_for_city("ho-chi-minh-hcm", max_pages=1)
    print(f"Lấy được {len(urls)} URL")
    assert len(urls) > 0, "Không lấy được URL nào"

    print("\n=== TEST BƯỚC 2: crawl chi tiết 3 tin đầu ===")
    for url in urls[:3]:
        print(f"\n--- {url} ---")
        try:
            data = crawl_job_detail(url)
        except Exception as e:
            print(f"  LỖI khi crawl: {e}")
            continue

        for key in ["tieu_de", "ten_cong_ty", "tinh_thanh", "quan_huyen", "ky_nang",
                    "hinh_thuc_lam_viec", "loai_hinh_lam_viec", "cap_bac",
                    "loai_hinh_cong_ty", "quy_mo_cong_ty",
                    "company_logo_url", "company_url", "company_mo_ta",
                    "job_expertise", "job_domain",
                    "ngay_dang_raw", "han_ung_tuyen_raw",
                    "mo_ta_cong_viec", "yeu_cau", "quyen_loi", "kinh_nghiem_thang"]:
            val = data.get(key)
            preview = (val[:80] + "...") if isinstance(val, str) and len(val) > 80 else val
            flag = "  <-- RỖNG/NONE" if not val and val != 0 else ""
            print(f"  {key}: {preview}{flag}")

        time.sleep(1)


def main():
    all_urls = step1_collect_urls()
    step2_crawl_details(all_urls)


if __name__ == "__main__":
    # test_quick()
    find_and_remove_stale_files()  # <- bật dòng này 1 lần để xóa file cũ thiếu field mới
    main()