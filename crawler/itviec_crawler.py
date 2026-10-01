"""
crawler/itviec_crawler.py
=========================
Cào tin tuyển dụng từ ITviec theo 2 bước:

  Bước 1: duyệt các trang danh sách theo thành phố -> lấy URL từng tin
          -> lưu vào crawler/raw_data/job_urls.json
  Bước 2: vào từng URL tin -> lấy chi tiết -> lưu mỗi tin 1 file JSON
          trong crawler/raw_data/jobs/<job_id>.json

Nguồn dữ liệu chính của bước 2 là khối <script type="application/ld+json">
có @type = JobPosting (ITviec sinh sẵn cho Google Jobs, ổn định hơn nhiều so
với dò class CSS / heading trong HTML). Những thứ JSON-LD không có thì mới
đọc thêm từ HTML (loại hình công ty, logo, chuyên môn...).

Cách chạy (từ thư mục gốc project):
    python crawler/itviec_crawler.py            # cào bình thường (tin đã có file thì bỏ qua)
    python crawler/itviec_crawler.py --test     # chạy thử nhanh: 1 trang HCM, in 3 tin đầu
    python crawler/itviec_crawler.py --refresh  # xóa các file cũ thiếu field mới rồi cào bù

Lưu ý: dữ liệu lưu ở đây là DỮ LIỆU THÔ (raw). Việc chuẩn hóa lương, số năm
kinh nghiệm, cấp bậc... nên làm ở bước ETL, đừng sửa trực tiếp vào file raw.
"""
import argparse
import glob
import json
import os
import random
import re
import time

import requests
from bs4 import BeautifulSoup


# =============================================================================
# CẤU HÌNH
# =============================================================================

# Giả làm trình duyệt thật để ITviec không từ chối request
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9",
}

# {tên khu vực lưu vào file: slug trên URL của ITviec}
CITIES = {
    "ho-chi-minh": "ho-chi-minh-hcm",
    "ha-noi": "ha-noi",
    "da-nang": "da-nang",
}

MAX_PAGES_PER_CITY = 15  # số trang danh sách tối đa cho mỗi thành phố

# Nơi lưu dữ liệu
RAW_DIR = "crawler/raw_data"
JOBS_DIR = os.path.join(RAW_DIR, "jobs")            # mỗi tin 1 file .json
URLS_PATH = os.path.join(RAW_DIR, "job_urls.json")  # danh sách URL theo khu vực

# Các nhãn phân đoạn trong phần mô tả (JSON-LD "description").
# Nhãn do nhà tuyển dụng / ITviec nhập tự do nên mỗi tin một kiểu, vì vậy mỗi
# phân đoạn có nhiều cách viết (tiếng Anh + tiếng Việt).
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

# employmentType (chuẩn schema.org) -> giá trị thống nhất với TopCV.
# Đây là LOẠI HỢP ĐỒNG, khác với "hinh_thuc_lam_viec" (At office/Remote/Hybrid
# = làm việc ở đâu).
EMPLOYMENT_TYPE_MAP = {
    "FULL_TIME": "Full-time",
    "PART_TIME": "Part-time",
    "INTERN": "Internship",
    "CONTRACTOR": "Contract",
    "TEMPORARY": "Contract",
}

# Một số badge cấp bậc bị ITviec gộp lẫn vào chuỗi "skills" trong JSON-LD.
# Chúng KHÔNG phải kỹ năng thật nên tách riêng thành "cap_bac".
# (Các cấp bậc khác như Junior/Senior/Manager không có trong dữ liệu trang chi
# tiết nên để None.)
CAP_BAC_SKILL_MARKERS = {
    "internship accepted": "Internship",
    "fresher accepted": "Fresher",
}


# =============================================================================
# HÀM TIỆN ÍCH XỬ LÝ CHỮ
# =============================================================================

def clean_text(text):
    """Gộp mọi khoảng trắng / xuống dòng thừa thành 1 dấu cách và cắt hai đầu.
    Trả về None nếu chuỗi rỗng."""
    if not text:
        return None
    return re.sub(r"\s+", " ", text).strip()


def strip_html(fragment):
    """Chuyển một đoạn HTML thành chữ thường, giữ xuống dòng giữa các mục.

    Chỉ chèn xuống dòng tại thẻ BLOCK (<li>, <p>, <br>), không xuống dòng ở thẻ
    inline (<strong>, <i>, <a>...) để câu không bị vỡ giữa chừng.
    Trả về None nếu không còn chữ nào.
    """
    if not fragment:
        return None
    # Chuẩn hóa kiểu xuống dòng của Windows (\r\n) về \n
    fragment = fragment.replace("\r\n", "\n").replace("\r", "\n")
    # Thẻ mở li/p/br -> xuống dòng; thẻ đóng li/p -> bỏ
    fragment = re.sub(r"<(li|p|br)\b[^>]*/?>", "\n", fragment, flags=re.I)
    fragment = re.sub(r"</(li|p)>", "", fragment, flags=re.I)
    # Bóc toàn bộ thẻ còn lại, chỉ giữ chữ
    text = BeautifulSoup(fragment, "html.parser").get_text(separator="")
    # Dọn khoảng trắng và dòng trống thừa
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip() or None


# =============================================================================
# BƯỚC 1: LẤY URL CÁC TIN THEO THÀNH PHỐ
# =============================================================================

def get_job_urls_for_city(city_slug, max_pages=MAX_PAGES_PER_CITY):
    """Duyệt từng trang danh sách của một thành phố, trả về list URL tin.

    Dừng sớm khi: tải trang bị lỗi, hoặc trang không còn tin nào.
    """
    job_urls = set()  # dùng set để tự loại URL trùng

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
        found_this_page = set()

        for a in soup.select("a[href*='/it-jobs/']"):
            href = a.get("href")
            if not href:
                continue
            clean_href = href.split("?")[0]  # bỏ phần tham số theo dõi sau dấu ?
            # URL của một tin luôn kết thúc bằng số ID (vd ...-protonx-3903).
            # Điều kiện này loại các link danh mục / phân trang.
            if re.search(r"-\d{3,}$", clean_href):
                found_this_page.add(clean_href)

        if not found_this_page:
            print(f"  Không còn tin nào ở trang {page}, dừng lại.")
            break

        for href in found_this_page:
            job_urls.add(href if href.startswith("http") else "https://itviec.com" + href)

        print(f"  Tìm thấy {len(found_this_page)} tin ở trang {page}")
        time.sleep(random.uniform(1, 3))  # nghỉ ngẫu nhiên để tránh bị chặn

    return sorted(job_urls)


def step1_collect_urls():
    """Lấy URL của tất cả thành phố, lưu ra job_urls.json và trả về dict
    {tên khu vực: [danh sách URL]}."""
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


# =============================================================================
# BƯỚC 2: CÁC HÀM TRÍCH XUẤT TỪNG FIELD
# =============================================================================

# ---------- Nguồn dữ liệu chính: JSON-LD và data layer ----------

def extract_job_ld(soup):
    """Tìm khối JSON-LD có @type = JobPosting.

    Trang có nhiều khối ld+json khác (BreadcrumbList, WebSite...) nên phải lọc
    đúng loại. Không thấy thì trả về {}.
    """
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
    """Đọc dữ liệu dự phòng trong attribute data-jobs--save-data-layer-value
    (dùng khi JSON-LD thiếu field). Không thấy thì trả về {}."""
    container = soup.select_one("div.jd-main[data-jobs--save-data-layer-value]")
    if not container:
        container = soup.select_one("[data-jobs--save-data-layer-value]")
    if not container:
        return {}
    try:
        return json.loads(container.get("data-jobs--save-data-layer-value"))
    except (json.JSONDecodeError, TypeError):
        return {}


# ---------- Mô tả công việc ----------

def split_job_description(desc):
    """Tách phần "description" của JSON-LD thành 3 phần.

    Trả về (mo_ta_cong_viec, yeu_cau, quyen_loi).

    Cách làm: tìm vị trí các nhãn trong SECTION_MARKERS (không phân biệt hoa
    thường), rồi cắt đoạn chữ nằm giữa nhãn này và nhãn kế tiếp. Phần giới
    thiệu "Top 3 lý do..." được gộp vào quyền lợi.

    Nếu không tìm thấy nhãn nào, giữ toàn bộ nội dung ở mô tả công việc để
    không mất dữ liệu.
    """
    if not desc:
        return None, None, None

    # Với mỗi phân đoạn, lấy cách viết xuất hiện sớm nhất trong văn bản
    positions = []  # (vị trí bắt đầu, tên phân đoạn, độ dài nhãn)
    for key, candidates in SECTION_MARKERS:
        best = None
        for cand in candidates:
            match = re.search(re.escape(cand), desc, re.IGNORECASE)
            if match and (best is None or match.start() < best[0]):
                best = (match.start(), key, len(match.group(0)))
        if best:
            positions.append(best)
    positions.sort(key=lambda x: x[0])

    # Không có nhãn nào: không tách được, giữ nguyên toàn bộ làm mô tả
    if not positions:
        return strip_html(desc), None, None

    # Cắt từng phân đoạn: từ cuối nhãn hiện tại đến đầu nhãn kế tiếp
    sections = {}
    for i, (idx, key, label_len) in enumerate(positions):
        start = idx + label_len
        end = positions[i + 1][0] if i + 1 < len(positions) else len(desc)
        sections[key] = strip_html(desc[start:end])

    mo_ta = sections.get("job")
    yeu_cau = sections.get("requirements")
    quyen_loi = sections.get("benefits")

    # Gộp phần giới thiệu vào đầu quyền lợi
    if sections.get("intro"):
        quyen_loi = sections["intro"] if not quyen_loi else sections["intro"] + "\n\n" + quyen_loi

    return mo_ta, yeu_cau, quyen_loi


# ---------- Các field lấy từ JSON-LD ----------

def extract_address(ld):
    """Lấy khối địa chỉ (address) trong jobLocation.

    jobLocation có tin là list, có tin là dict -> xử lý cả hai.
    Luôn trả về dict (rỗng nếu không có)."""
    loc = ld.get("jobLocation")
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    if not isinstance(loc, dict):
        return {}
    address = loc.get("address")
    return address if isinstance(address, dict) else {}


def normalize_not_available(value):
    """ITviec ghi chuỗi "Not available" khi thiếu dữ liệu -> đổi thành None."""
    if value and value.strip().lower() == "not available":
        return None
    return value


def extract_salary_raw(ld):
    """Lấy chuỗi lương thô trong baseSalary.value.value (vd "18 - 20M").

    Chỉ lấy nguyên văn, KHÔNG phân tích. Có tin ghi lương thật, có tin chỉ ghi
    câu quảng cáo như "You'll love it". Việc tách min/max/tiền tệ để bước ETL."""
    base_salary = ld.get("baseSalary")
    if not isinstance(base_salary, dict):
        return None
    value = base_salary.get("value")
    return value.get("value") if isinstance(value, dict) else value


def extract_months_of_experience(ld):
    """Lấy số tháng kinh nghiệm trong JSON-LD (chỉ để tham khảo).

    experienceRequirements lúc là dict {'monthsOfExperience': 10}, lúc là
    string -> kiểm tra kiểu trước khi đọc.
    CẢNH BÁO: số này do ITviec tự ước lượng, KHÔNG đáng tin (vd tin yêu cầu
    "2 năm" lại ra 10 tháng). Bước ETL nên tự trích số năm từ "yeu_cau"."""
    exp = ld.get("experienceRequirements")
    if isinstance(exp, dict):
        return exp.get("monthsOfExperience")
    return None  # kiểu string hoặc không có -> không tự đoán


def extract_loai_hinh_lam_viec(ld):
    """Đổi employmentType (FULL_TIME, PART_TIME...) về nhãn thống nhất
    (Full-time, Part-time...). Giá trị lạ -> None."""
    raw = ld.get("employmentType")
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    if not raw or not isinstance(raw, str):
        return None
    return EMPLOYMENT_TYPE_MAP.get(raw.strip().upper())


def extract_cap_bac_and_clean_skills(skills_list):
    """Tách badge cấp bậc ra khỏi danh sách kỹ năng.

    Trả về (ky_nang_da_loc, cap_bac). Ví dụ:
      ["Python", "Fresher Accepted"] -> (["Python"], "Fresher")
    """
    if not skills_list:
        return skills_list, None

    cap_bac = None
    cleaned = []
    for skill in skills_list:
        key = skill.strip().lower()
        if key in CAP_BAC_SKILL_MARKERS:
            cap_bac = CAP_BAC_SKILL_MARKERS[key]
        else:
            cleaned.append(skill)
    return cleaned, cap_bac


# ---------- Các field phải đọc từ HTML ----------

def extract_hinh_thuc_lam_viec(soup):
    """Hình thức làm việc: At office / Remote / Hybrid (làm ở đâu)."""
    el = soup.find(string=re.compile(r"^(At office|Remote|Hybrid|Tại văn phòng)$"))
    return clean_text(el) if el else None


def extract_han_ung_tuyen_meta(soup):
    """Hạn nộp hồ sơ lấy từ thẻ meta googlebot (unavailable_after: ...).
    Chỉ dùng khi JSON-LD không có validThrough."""
    meta = soup.find("meta", attrs={"name": re.compile(r"^googlebot$", re.I)})
    if meta and meta.get("content"):
        m = re.search(r"unavailable_after:\s*([^\r\n]+)", meta["content"])
        if m:
            return m.group(1).strip()
    return None


def extract_label_value(soup, label_variants):
    """Tìm một nhãn (vd "Company size") rồi lấy giá trị nằm ngay sau nó.

    label_variants: các cách viết của nhãn (tiếng Anh / tiếng Việt).
    Bỏ qua các đoạn chỉ có khoảng trắng nằm giữa các thẻ."""
    for label_text in label_variants:
        label_node = soup.find(string=lambda s: s and clean_text(s) == label_text)
        if not label_node:
            continue
        next_val = label_node.find_next(string=lambda s: bool(clean_text(s)))
        if next_val:
            return clean_text(next_val)
    return None


def extract_multi_tag_field(soup, label_variants):
    """Lấy danh sách chữ trong các thẻ <a> thuộc cùng khối với nhãn.

    Dùng cho "Job Expertise:" (nhiều tag link). Chỉ đi lên tối đa 4 cấp thẻ
    cha tính từ nhãn, để không lẫn link menu hoặc link của tin khác."""
    for label_text in label_variants:
        label_node = soup.find(string=lambda s: s and clean_text(s) == label_text)
        if not label_node:
            continue
        block = label_node.find_parent()
        for _ in range(4):
            if block is None:
                break
            texts = [clean_text(a.get_text()) for a in block.find_all("a")]
            texts = [t for t in texts if t]
            if texts:
                return texts
            block = block.find_parent()
        return []
    return []


def extract_job_domain(soup):
    """Lấy "Job Domain:" (lĩnh vực công ty). Hiển thị dạng chữ thường, không
    phải link, có thể nhiều dòng.

    Đọc tối đa 15 đoạn chữ phía sau nhãn, dừng khi gặp phần mô tả."""
    label_node = soup.find(string=lambda s: s and clean_text(s) == "Job Domain:")
    if not label_node:
        return []
    container = label_node.find_parent()
    if not container:
        return []

    domains = []
    for node in container.find_all_next(string=True, limit=15):
        text = clean_text(node)
        if not text:
            continue
        if text.rstrip(":").strip().lower() == "job domain":
            continue  # bỏ chính cái nhãn
        if re.match(r"^Top 3|^Job description$", text, re.I):
            break     # đã sang phần mô tả
        domains.append(text)
    return domains


# ---------- Thông tin công ty (logo, link, giới thiệu) ----------

def extract_logo_from_img(img_tag):
    """Lấy URL logo từ thẻ <img>.

    ITviec dùng lazy-loading nên link thật thường nằm ở data-src, không phải
    src. Nếu không có thì thử data-srcset của thẻ <source> trong <picture>.
    Bỏ qua ảnh có "review-company" (ảnh review, không phải logo)."""
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
    """Lấy (logo_url, company_url, mô tả công ty).

    Dùng nhãn "Company type" làm mốc rồi nhìn NGƯỢC lên phía trên để tìm link
    công ty, logo và đoạn giới thiệu. Không thấy mốc thì trả (None, None, None)."""
    label = soup.find(string=lambda s: s and clean_text(s) == "Company type")
    if not label:
        return None, None, None

    # Link công ty sạch có dạng /companies/ten-cong-ty (không phải /companies/x/reviews...)
    clean_company_url = re.compile(r"^/companies/[a-z0-9\-]+/?$", re.I)

    # Các link /companies/ nằm phía trên mốc (limit lớn để không bị hụt)
    candidates = list(label.find_all_previous("a", href=re.compile(r"/companies/"), limit=40))

    # 1) Link công ty
    company_url = None
    for a in candidates:
        href = a.get("href", "")
        if clean_company_url.match(href.split("?")[0]):
            company_url = href.split("?")[0]
            break

    # 2) Logo: ưu tiên ảnh nằm trong các link công ty ở trên
    logo_url = None
    for a in candidates:
        logo_url = extract_logo_from_img(a.find("img"))
        if logo_url:
            break

    # 2b) Dự phòng: tìm ảnh bất kỳ có chữ "logo" trong alt hoặc class
    if not logo_url:
        for img in label.find_all_previous("img", limit=40):
            alt = (img.get("alt") or "").lower()
            cls = " ".join(img.get("class", [])).lower()
            if "logo" in alt or "logo" in cls:
                logo_url = extract_logo_from_img(img)
                if logo_url:
                    break

    # 3) Giới thiệu công ty: gộp toàn bộ chữ của thẻ cha chứa đoạn mô tả
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


# =============================================================================
# BƯỚC 2: CÀO CHI TIẾT MỘT TIN
# =============================================================================

def crawl_job_detail(url):
    """Tải một trang tin và trả về dict đầy đủ các field.

    Ưu tiên lấy từ JSON-LD, thiếu thì lấy từ data layer, rồi mới đến HTML.
    Các field có hậu tố "_raw" là dữ liệu nguyên văn, chưa chuẩn hóa."""
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    ld = extract_job_ld(soup)          # nguồn chính
    layer = extract_data_layer(soup)   # nguồn dự phòng

    data = {"url": url}

    # --- Thông tin chung ---
    data["tieu_de"] = clean_text(ld.get("title") or layer.get("job_title"))
    hiring_org = ld.get("hiringOrganization")
    org_name = hiring_org.get("name") if isinstance(hiring_org, dict) else None
    data["ten_cong_ty"] = clean_text(org_name or layer.get("job_by_company"))
    data["ngay_dang_raw"] = ld.get("datePosted")
    data["han_ung_tuyen_raw"] = ld.get("validThrough") or extract_han_ung_tuyen_meta(soup)

    # --- Kỹ năng và cấp bậc ---
    skills_raw = ld.get("skills") or layer.get("job_required_skill", "")
    if isinstance(skills_raw, list):
        ky_nang_list = [str(s).strip() for s in skills_raw if str(s).strip()]
    else:
        ky_nang_list = [s.strip() for s in skills_raw.split(",") if s.strip()]
    data["ky_nang"], data["cap_bac"] = extract_cap_bac_and_clean_skills(ky_nang_list)

    # --- Địa điểm ---
    address = extract_address(ld)
    data["dia_chi_raw"] = normalize_not_available(address.get("streetAddress"))
    data["quan_huyen"] = normalize_not_available(address.get("addressLocality"))
    data["tinh_thanh"] = normalize_not_available(address.get("addressRegion")) or layer.get("job_by_city")

    # --- Lương, kinh nghiệm, loại hợp đồng ---
    data["salary_placeholder_raw"] = extract_salary_raw(ld)
    data["salary_range_raw"] = layer.get("salary_range") or None
    data["kinh_nghiem_thang"] = extract_months_of_experience(ld)  # chỉ tham khảo
    data["loai_hinh_lam_viec"] = extract_loai_hinh_lam_viec(ld)

    # --- Nội dung: mô tả / yêu cầu / quyền lợi ---
    mo_ta, yeu_cau, quyen_loi = split_job_description(ld.get("description"))
    data["mo_ta_cong_viec"] = mo_ta
    data["yeu_cau"] = yeu_cau
    data["quyen_loi"] = quyen_loi

    # --- Dự phòng cho tiêu đề và tên công ty nếu JSON-LD thiếu ---
    if not data["tieu_de"]:
        h1 = soup.find("h1")
        data["tieu_de"] = clean_text(h1.get_text()) if h1 else None
    if not data["ten_cong_ty"]:
        el = soup.select_one(".employer-name")
        data["ten_cong_ty"] = clean_text(el.get_text()) if el else None

    # --- Các field chỉ có trong HTML ---
    data["hinh_thuc_lam_viec"] = extract_hinh_thuc_lam_viec(soup)
    data["loai_hinh_cong_ty"] = extract_label_value(soup, ["Company type", "Loại hình công ty"])
    data["quy_mo_cong_ty"] = extract_label_value(soup, ["Company size", "Quy mô công ty"])
    data["company_logo_url"], data["company_url"], data["company_mo_ta"] = extract_company_info(soup)
    data["job_expertise"] = extract_multi_tag_field(soup, ["Job Expertise:"])  # chuyên môn
    data["job_domain"] = extract_job_domain(soup)  # lĩnh vực của CÔNG TY, không phải của tin

    return data


def crawl_job_detail_with_retry(url, max_retries=2):
    """Gọi crawl_job_detail, nếu lỗi mạng thì thử lại (tối đa max_retries lần),
    mỗi lần chờ lâu hơn lần trước. Hết lượt vẫn lỗi thì ném lỗi ra ngoài."""
    for attempt in range(max_retries + 1):
        try:
            return crawl_job_detail(url)
        except requests.RequestException:
            if attempt == max_retries:
                raise
            time.sleep(random.uniform(2, 4) * (attempt + 1))


def step2_crawl_details(all_urls):
    """Cào chi tiết toàn bộ URL, mỗi tin lưu 1 file JSON.

    - Tin đã có file thì bỏ qua (chạy lại không cào trùng, có thể dừng giữa
      chừng rồi chạy tiếp).
    - 1 tin lỗi chỉ bị ghi log và bỏ qua, không làm sập cả đợt cào."""
    count = 0
    error_count = 0

    for city, urls in all_urls.items():
        for url in urls:
            job_id = url.rstrip("/").split("/")[-1]  # đoạn cuối URL làm tên file
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
                print(f"  Lỗi xử lý tin ({type(e).__name__}): {e}")
                error_count += 1

            time.sleep(random.uniform(1.5, 3.5))

    print(f"[Bước 2] Hoàn tất. Đã crawl {count} tin mới, {error_count} tin lỗi -> {JOBS_DIR}/")


# =============================================================================
# CÔNG CỤ PHỤ: DỌN FILE CŨ, CHẠY THỬ, HÀM MAIN
# =============================================================================

def find_and_remove_stale_files(jobs_dir=JOBS_DIR, required_keys=None):
    """Xóa các file JSON cũ còn THIẾU field mới, để bước 2 cào lại đúng những
    tin đó (thay vì cào lại tất cả).

    Chỉ dùng sau khi bạn THÊM field mới vào crawl_job_detail():
    điền tên field mới vào required_keys rồi chạy với --refresh.

    Chỉ kiểm tra field có TỒN TẠI trong file, không kiểm tra giá trị rỗng.
    Lý do: nhiều field hợp lệ vẫn có thể là None (vd cap_bac thường là None);
    nếu coi rỗng là thiếu thì gần như file nào cũng bị xóa."""
    if required_keys is None:
        required_keys = ["company_logo_url", "company_url", "cap_bac", "loai_hinh_lam_viec"]

    removed = 0
    for path in glob.glob(os.path.join(jobs_dir, "*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if any(key not in data for key in required_keys):
            os.remove(path)
            removed += 1
    print(f"Đã xóa {removed} file cũ (thiếu field mới) để cào lại.")


def test_quick():
    """Chạy thử nhanh: lấy 1 trang URL của HCM rồi cào 3 tin đầu, in từng field
    và đánh dấu field nào rỗng. Dùng để kiểm tra khi ITviec đổi giao diện."""
    print("=== TEST BƯỚC 1: lấy URL (1 trang, HCM) ===")
    urls = get_job_urls_for_city("ho-chi-minh-hcm", max_pages=1)
    print(f"Lấy được {len(urls)} URL")
    assert len(urls) > 0, "Không lấy được URL nào"

    fields_to_show = [
        "tieu_de", "ten_cong_ty", "tinh_thanh", "quan_huyen", "ky_nang",
        "hinh_thuc_lam_viec", "loai_hinh_lam_viec", "cap_bac",
        "loai_hinh_cong_ty", "quy_mo_cong_ty",
        "company_logo_url", "company_url", "company_mo_ta",
        "job_expertise", "job_domain",
        "ngay_dang_raw", "han_ung_tuyen_raw",
        "mo_ta_cong_viec", "yeu_cau", "quyen_loi", "kinh_nghiem_thang",
    ]

    print("\n=== TEST BƯỚC 2: crawl chi tiết 3 tin đầu ===")
    for url in urls[:3]:
        print(f"\n--- {url} ---")
        try:
            data = crawl_job_detail(url)
        except Exception as e:
            print(f"  LỖI khi crawl: {e}")
            continue

        for key in fields_to_show:
            val = data.get(key)
            preview = (val[:80] + "...") if isinstance(val, str) and len(val) > 80 else val
            flag = "  <-- RỖNG/NONE" if not val and val != 0 else ""
            print(f"  {key}: {preview}{flag}")

        time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description="Cào tin tuyển dụng ITviec")
    parser.add_argument("--test", action="store_true",
                        help="chạy thử nhanh (1 trang HCM, 3 tin đầu) rồi thoát")
    parser.add_argument("--refresh", action="store_true",
                        help="xóa các file cũ thiếu field mới trước khi cào")
    args = parser.parse_args()

    os.makedirs(JOBS_DIR, exist_ok=True)  # tạo thư mục lưu nếu chưa có

    if args.test:
        test_quick()
        return

    if args.refresh:
        find_and_remove_stale_files()

    all_urls = step1_collect_urls()
    step2_crawl_details(all_urls)


if __name__ == "__main__":
    main()