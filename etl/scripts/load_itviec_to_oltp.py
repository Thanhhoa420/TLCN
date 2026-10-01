"""
etl/scripts/load_itviec_to_oltp.py
==================================
Nạp crawler/raw_data/jobs/*.json vào oltp_db.

Chạy từ thư mục gốc project:
    python etl/scripts/load_itviec_to_oltp.py --dry-run   # chỉ chuẩn hóa + in thống kê, KHÔNG đụng DB
    python etl/scripts/load_itviec_to_oltp.py             # nạp thật

Kết nối DB qua biến môi trường (có mặc định):
    OLTP_HOST=localhost OLTP_PORT=5432 OLTP_DB=oltp_db OLTP_USER=postgres OLTP_PASSWORD=postgres

Chạy lại nhiều lần an toàn: công ty / user / tin đều upsert theo khóa (email, url_nguon).
Cần: pip install psycopg2-binary
"""
import argparse
import glob
import json
import os
import random
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

# =============================================================================
# CẤU HÌNH (các giả định - sửa ở đây nếu muốn đổi)
# =============================================================================
ROOT = Path(__file__).resolve().parents[2]
JOBS_DIR = ROOT / "crawler" / "raw_data" / "jobs"
MAPPING_DIR = ROOT / "crawler" / "mapping"

TY_GIA_USD_VND = 25_000      # quy đổi USD -> VND (cố định để kết quả lặp lại được)
SEED = 42                    # seed mô phỏng lương
MIN_MAU = 5                  # nhóm (chuyên môn, nhóm kinh nghiệm) ít hơn số này -> không mô phỏng, để NULL
CAP_BAC_CHO_LEAD = "Senior"  # danh mục không có 'Lead' -> gộp vào cấp này
TRANG_THAI_DUYET_CONG_TY = "da_duyet"  # CHƯA CHẮC: đổi cho khớp giá trị backend dùng
PASSWORD_HASH_GIA = "!seed-account-khong-dang-nhap"

HINH_THUC = {"at office": "At office", "tại văn phòng": "At office",
             "remote": "Remote", "hybrid": "Hybrid"}


# =============================================================================
# TIỆN ÍCH
# =============================================================================
def bo_dau(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D")


def khoa_chuan(s):
    """'Hồ Chí Minh' / 'ho-chi-minh' -> 'ho chi minh'"""
    return re.sub(r"[\s\-_]+", " ", bo_dau(s).lower()).strip()


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", bo_dau(s).lower()).strip("-") or "unknown"


def doc_json(ten_file):
    with open(MAPPING_DIR / ten_file, encoding="utf-8") as f:
        return json.load(f)


# =============================================================================
# CHUẨN HÓA LƯƠNG
# =============================================================================
def _so(tok):
    """Đổi '3.000.000' / '30,000,000' / '1800' / '2.5' thành số."""
    t = tok.strip(".,")
    seps = re.findall(r"[.,]", t)
    if not seps:
        return float(t)
    if len(seps) >= 2:                      # nhiều dấu -> dấu phân cách nghìn
        return float(re.sub(r"[.,]", "", t))
    sau = re.split(r"[.,]", t)[1]
    if len(sau) == 3:                       # '3.000' -> nghìn
        return float(re.sub(r"[.,]", "", t))
    return float(t.replace(",", "."))       # '2,5' -> thập phân


def parse_luong(raw):
    """Chuỗi lương thô -> (luong_min, luong_max) tính bằng VND/tháng.
    Không phải lương (You'll love it...), lương theo giờ/ngày, hoặc không chắc -> (None, None).
    'Up to X' -> (None, X)."""
    if not raw:
        return None, None
    t = str(raw).strip().lower()
    if re.search(r"giờ|hour|ngày|/\s*day|per day", t):
        return None, None
    toks = re.findall(r"\d[\d.,]*", t)
    if not toks:
        return None, None
    try:
        so = [_so(x) for x in toks]
    except ValueError:
        return None, None

    usd = "$" in t or "usd" in t
    trieu = bool(re.search(r"\d\s*(?:m|mil|million|tr|triệu)\b", t))
    he_so = TY_GIA_USD_VND if usd else (1_000_000 if trieu else 1)
    gia = [int(x * he_so) for x in so]
    if not usd and not trieu and max(gia) < 1_000_000:
        return None, None                   # số nhỏ, không rõ đơn vị -> bỏ

    if len(gia) >= 2:
        lo, hi = sorted(gia[:2])
    elif re.search(r"up\s*to|upto|tối đa", t):
        lo, hi = None, gia[0]
    else:
        lo, hi = gia[0], gia[0]
    if hi is None or hi <= 0 or hi > 500_000_000:
        return None, None
    return lo, hi


# =============================================================================
# KINH NGHIỆM / CẤP BẬC
# =============================================================================
RE_NAM = re.compile(r"(\d{1,2}(?:[.,]\d)?)\s*(?:\+|-|–|—|to|đến)?\s*(\d{1,2})?\s*\+?\s*(?:years?|yrs?|năm)\b", re.I)
RE_KHONG_KN = re.compile(r"không\s+(?:yêu cầu|cần)\s+(?:có\s+)?kinh nghiệm|no experience (?:is )?(?:required|needed)", re.I)


def tim_so_nam(yeu_cau):
    """Trích số năm kinh nghiệm TỐI THIỂU từ trường yêu cầu (lấy kết quả đầu tiên). Không thấy -> None."""
    if not yeu_cau:
        return None
    m = RE_NAM.search(yeu_cau)
    if m:
        v = float(m.group(1).replace(",", "."))
        return v if v <= 20 else None
    if RE_KHONG_KN.search(yeu_cau):
        return 0.0
    return None


def ten_khoang_kinh_nghiem(nam):
    """Quy tắc: so_nam_min <= x < so_nam_max."""
    if nam is None:
        return None
    if nam <= 0:
        return "Chưa có kinh nghiệm"
    if nam < 1:
        return "Dưới 1 năm"
    if nam < 2:
        return "1-2 năm"
    if nam < 3:
        return "2-3 năm"
    if nam < 5:
        return "3-5 năm"
    if nam < 10:
        return "5-10 năm"
    return "Trên 10 năm"


def nhom_kinh_nghiem(nam):
    """Nhóm thô để mô phỏng lương."""
    if nam is None:
        return None
    return 0 if nam < 1 else 1 if nam < 3 else 2 if nam < 5 else 3


# Thứ tự ưu tiên: dòng trên thắng dòng dưới
CAP_BAC_TIEU_DE = [
    ("Internship", r"\bintern(ship)?\b|thực tập"),
    ("Fresher", r"\bfresher\b"),
    ("Manager", r"\bmanager\b|\bdirector\b|\bhead of\b|giám đốc|trưởng phòng|\bvp\b|\bcto\b|\bcio\b"),
    (CAP_BAC_CHO_LEAD, r"\blead\b|\bleader\b|\bprincipal\b|\bstaff\b"),
    ("Senior", r"\bsenior\b|\bsr\b"),
    ("Middle", r"\bmiddle\b|\bmid\b|\bmid-level\b"),
    ("Junior", r"\bjunior\b|\bjr\b"),
]


def suy_cap_bac(tieu_de, cap_bac_raw, so_nam=None):
    """Trả về (cap_bac, nguon). Ưu tiên tiêu đề; không có thì dùng badge của crawler.
    Badge 'Internship/Fresher Accepted' chỉ có nghĩa là NHẬN intern/fresher, không phải cấp bậc của tin,
    nên chỉ dùng khi tin không đòi quá 1 năm kinh nghiệm.
    nguon: 'tieu_de' (SUY RA) | 'badge' | None."""
    t = (tieu_de or "").lower()
    for ten, pattern in CAP_BAC_TIEU_DE:
        if re.search(pattern, t):
            return ten, "tieu_de"
    if cap_bac_raw and (so_nam is None or so_nam <= 1):
        return cap_bac_raw, "badge"
    return None, None


# =============================================================================
# CHUẨN HÓA MỘT TIN
# =============================================================================
def tim_dia_diem(d, dd_map):
    ung_vien = [p for p in reversed((d.get("tinh_thanh") or "").split(","))]
    ung_vien.append(d.get("khu_vuc_crawl") or "")
    for p in ung_vien:
        ten = dd_map.get(khoa_chuan(p))
        if ten:
            return ten
    return None


def chon_chuyen_mon(ds, cm_map):
    for e in ds or []:
        ten = cm_map.get(e)
        if ten and ten != "Khác":
            return ten
    return "Khác"


# Tag chuyên môn của ITviec đôi khi gắn sai (vd tin "DevOps Engineer" bị gắn tag Database Engineer).
# Với 2 nhóm có từ khóa rõ ràng trong tiêu đề, TIÊU ĐỀ được ưu tiên hơn tag.
# Chỉ xét 5 từ đầu của tiêu đề để tránh bắt nhầm (vd "Backend Developer ... DevOps experience").
LUAT_GHI_DE_TIEU_DE = [
    (r"\btester\b|\bqa\b|\bqc\b|\bsdet\b|kiểm thử", "QA/Tester"),
    (r"devops|\bsre\b", "DevOps Engineer"),
]


def sua_chuyen_mon_theo_tieu_de(tieu_de, cm):
    dau = " ".join((tieu_de or "").lower().split()[:5])
    for pattern, ten in LUAT_GHI_DE_TIEU_DE:
        if re.search(pattern, dau):
            return ten
    return cm


def chuan_hoa_ky_nang(ds, alias, nhom_cua):
    """Trả list [(tên_chuẩn, nhóm)], bỏ trùng, bỏ badge cấp bậc."""
    ket_qua, da_co = [], set()
    for raw in ds or []:
        ten = (raw or "").strip()
        if not ten or ten.lower() in alias["_bo_qua"]:
            continue
        ten = alias["_alias"].get(ten.lower(), ten)
        if ten.lower() in da_co:
            continue
        da_co.add(ten.lower())
        ket_qua.append((ten, nhom_cua.get(ten.lower(), "Khác")))
    return ket_qua


def parse_ngay(s):
    try:
        return date.fromisoformat(s[:10]) if s else None
    except ValueError:
        return None


def chuan_hoa_tin(d, cfg, hom_nay):
    nam = tim_so_nam(d.get("yeu_cau"))
    cap_bac, cap_bac_nguon = suy_cap_bac(d.get("tieu_de"), d.get("cap_bac"), nam)
    if nam is None and cap_bac == "Internship":
        nam = 0
    lo, hi = parse_luong(d.get("salary_placeholder_raw"))
    if hi is None:                                  # dự phòng: trường lương từ data layer
        lo, hi = parse_luong(d.get("salary_range_raw"))
    han = parse_ngay(d.get("han_ung_tuyen_raw"))
    cm = chon_chuyen_mon(d.get("job_expertise"), cfg["cm_map"])
    cm = sua_chuyen_mon_theo_tieu_de(d["tieu_de"], cm)

    cong_ty_url = d.get("company_url") or f"/companies/{slugify(d['ten_cong_ty'])}"
    dia_diem = tim_dia_diem(d, cfg["dd_map"])
    return {
        "url_nguon": d["url"],
        "tieu_de": d["tieu_de"][:255],
        "mo_ta_cong_viec": d.get("mo_ta_cong_viec"),
        "yeu_cau": d.get("yeu_cau"),
        "quyen_loi": d.get("quyen_loi"),
        "chuyen_mon": cm,
        "dia_diem": dia_diem,
        "so_nam": nam,
        "kinh_nghiem": ten_khoang_kinh_nghiem(nam),
        "hinh_thuc": HINH_THUC.get((d.get("hinh_thuc_lam_viec") or "").lower()),
        "loai_hinh": d.get("loai_hinh_lam_viec"),
        "cap_bac": cap_bac,
        "cap_bac_nguon": cap_bac_nguon,
        "luong_min": lo,
        "luong_max": hi,
        "luong_nguon": "crawl" if hi is not None else None,
        "ngay_dang": parse_ngay(d.get("ngay_dang_raw")),
        "han_ung_tuyen": han,
        "trang_thai": "Expired" if (han and han < hom_nay) else "Published",
        "ky_nang": chuan_hoa_ky_nang(d.get("ky_nang"), cfg["ky_nang_alias"], cfg["nhom_cua"]),
        "cong_ty": {
            "url_nguon": cong_ty_url,
            "ten": d["ten_cong_ty"],
            "logo_url": d.get("company_logo_url"),
            "loai_hinh": d.get("loai_hinh_cong_ty"),
            "quy_mo": d.get("quy_mo_cong_ty"),
            "mo_ta": d.get("company_mo_ta"),
            "dia_diem": dia_diem,
        },
    }


# =============================================================================
# MÔ PHỎNG LƯƠNG (chỉ cho tin thiếu lương) - seed cố định, ghi luong_nguon='mo_phong'
# =============================================================================
def mo_phong_luong(tins):
    ho = defaultdict(list)   # (chuyên môn, nhóm kn) -> [(min, max)] từ lương THẬT có đủ min & max
    for t in tins:
        if t["luong_nguon"] == "crawl" and t["luong_min"] is not None:
            ho[(t["chuyen_mon"], nhom_kinh_nghiem(t["so_nam"]))].append((t["luong_min"], t["luong_max"]))

    rng = random.Random(SEED)
    for t in sorted(tins, key=lambda x: x["url_nguon"]):    # sắp xếp để kết quả lặp lại được
        if t["luong_nguon"] is not None or t["chuyen_mon"] == "Khác":
            continue
        nhom = nhom_kinh_nghiem(t["so_nam"])
        if nhom is None:
            continue
        mau = ho.get((t["chuyen_mon"], nhom), [])
        if len(mau) < MIN_MAU:
            continue
        t["luong_min"], t["luong_max"] = rng.choice(mau)
        t["luong_nguon"] = "mo_phong"


def in_thong_ke(tins, bo_qua):
    n = len(tins)
    print(f"\n=== THỐNG KÊ CHUẨN HÓA ({n} tin, bỏ qua {bo_qua} file thiếu url/tiêu đề/công ty) ===")
    for ten, truong in [("Nguồn lương", "luong_nguon"), ("Trạng thái", "trang_thai"),
                        ("Nguồn cấp bậc", "cap_bac_nguon"), ("Cấp bậc", "cap_bac"),
                        ("Khoảng kinh nghiệm", "kinh_nghiem"), ("Địa điểm", "dia_diem"),
                        ("Hình thức làm việc", "hinh_thuc"), ("Chuyên môn", "chuyen_mon")]:
        c = Counter(t[truong] for t in tins)
        print(f"\n{ten}:")
        for k, v in c.most_common():
            print(f"  {v:5d}  {k}")
    print(f"\nSố công ty: {len({t['cong_ty']['url_nguon'] for t in tins})}")
    print(f"Số kỹ năng khác nhau: {len({k.lower() for t in tins for k, _ in t['ky_nang']})}")


# =============================================================================
# NẠP VÀO DB
# =============================================================================
def ket_noi():
    import psycopg2
    return psycopg2.connect(
        host=os.getenv("OLTP_HOST", "localhost"), port=os.getenv("OLTP_PORT", "5432"),
        dbname=os.getenv("OLTP_DB", "oltp_db"), user=os.getenv("OLTP_USER", "postgres"),
        password=os.getenv("OLTP_PASSWORD", "postgres"))


def tai_tu_dien(cur, bang, cot_ten, cot_id):
    """Tra ID danh mục theo TÊN (không gán cứng số)."""
    cur.execute(f"SELECT {cot_ten}, {cot_id} FROM {bang}")
    return {ten: i for ten, i in cur.fetchall()}


def tra(tu_dien, ten, bang):
    if ten is None:
        return None
    if ten not in tu_dien:
        raise RuntimeError(f"Không thấy '{ten}' trong {bang}. Đã chạy 02_seed_danh_muc.sql chưa?")
    return tu_dien[ten]


COT_TIN = ["company_id", "tieu_de", "mo_ta_cong_viec", "yeu_cau", "quyen_loi", "chuyen_mon_id",
           "dia_diem_id", "kinh_nghiem_id", "hoc_van_id", "hinh_thuc_id", "loai_hinh_lam_viec_id",
           "cap_bac_id", "luong_min", "luong_max", "luong_nguon", "ngay_dang", "han_ung_tuyen",
           "trang_thai_id", "nguon_tin", "url_nguon"]
_cot_values = ", ".join("%(" + c + ")s" for c in COT_TIN)
_cot_update = ", ".join(c + "=EXCLUDED." + c for c in COT_TIN if c != "url_nguon")
SQL_UPSERT_TIN = (f"INSERT INTO tin_tuyen_dung ({', '.join(COT_TIN)}) VALUES ({_cot_values}) "
                  f"ON CONFLICT (url_nguon) DO UPDATE SET {_cot_update}, updated_at = NOW() "
                  f"RETURNING job_id, (xmax = 0) AS la_moi")


def upsert_cong_ty(cur, ct, dd_id):
    slug = slugify(ct["url_nguon"].rstrip("/").split("/")[-1])
    cur.execute(
        """INSERT INTO users (email, password_hash, role, full_name, is_active)
           VALUES (%s, %s, 'nha_tuyen_dung', %s, FALSE)
           ON CONFLICT (email) DO UPDATE SET full_name = EXCLUDED.full_name, updated_at = NOW()
           RETURNING user_id""",
        (f"{slug}@seed.local", PASSWORD_HASH_GIA, ct["ten"]))
    user_id = cur.fetchone()[0]
    cur.execute(
        """INSERT INTO nha_tuyen_dung
               (user_id, ten_cong_ty, logo_url, loai_hinh, quy_mo, dia_diem_id, mo_ta, trang_thai_duyet, url_nguon)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (url_nguon) DO UPDATE SET
               ten_cong_ty = EXCLUDED.ten_cong_ty, logo_url = EXCLUDED.logo_url,
               loai_hinh = EXCLUDED.loai_hinh, quy_mo = EXCLUDED.quy_mo, mo_ta = EXCLUDED.mo_ta
           RETURNING company_id""",
        (user_id, ct["ten"], ct["logo_url"], ct["loai_hinh"], ct["quy_mo"],
         tra(dd_id, ct["dia_diem"], "danh_muc_dia_diem"), ct["mo_ta"],
         TRANG_THAI_DUYET_CONG_TY, ct["url_nguon"]))
    return cur.fetchone()[0]


def nap_vao_db(tins):
    conn = ket_noi()
    try:
        with conn.cursor() as cur:
            cm = tai_tu_dien(cur, "danh_muc_chuyen_mon_it", "ten_chuyen_mon", "chuyen_mon_id")
            dd = tai_tu_dien(cur, "danh_muc_dia_diem", "ten_tinh_thanh", "dia_diem_id")
            kn = tai_tu_dien(cur, "danh_muc_kinh_nghiem", "mo_ta", "kinh_nghiem_id")
            ht = tai_tu_dien(cur, "danh_muc_hinh_thuc_lam_viec", "ten_hinh_thuc", "hinh_thuc_id")
            lh = tai_tu_dien(cur, "danh_muc_loai_hinh_lam_viec", "ten_loai_hinh", "loai_hinh_lam_viec_id")
            cb = tai_tu_dien(cur, "danh_muc_cap_bac", "ten_cap_bac", "cap_bac_id")
            tt = tai_tu_dien(cur, "danh_muc_trang_thai_tin", "ten_trang_thai", "trang_thai_id")
            cur.execute("SELECT ten_ky_nang, ky_nang_id FROM ky_nang")
            ky_nang_id = {ten.lower(): i for ten, i in cur.fetchall()}

            def id_ky_nang(ten, nhom):
                if ten.lower() not in ky_nang_id:       # kỹ năng mới -> thêm vào bảng
                    cur.execute(
                        """INSERT INTO ky_nang (ten_ky_nang, nhom_ky_nang) VALUES (%s, %s)
                           ON CONFLICT (ten_ky_nang) DO UPDATE SET ten_ky_nang = EXCLUDED.ten_ky_nang
                           RETURNING ky_nang_id""", (ten, nhom))
                    ky_nang_id[ten.lower()] = cur.fetchone()[0]
                return ky_nang_id[ten.lower()]

            company_id, moi, cap_nhat = {}, 0, 0
            batch_size = 100
            for idx, t in enumerate(tins, start=1):
                ct = t["cong_ty"]
                if ct["url_nguon"] not in company_id:
                    company_id[ct["url_nguon"]] = upsert_cong_ty(cur, ct, dd)

                params = {
                    "company_id": company_id[ct["url_nguon"]],
                    "tieu_de": t["tieu_de"], "mo_ta_cong_viec": t["mo_ta_cong_viec"],
                    "yeu_cau": t["yeu_cau"], "quyen_loi": t["quyen_loi"],
                    "chuyen_mon_id": tra(cm, t["chuyen_mon"], "danh_muc_chuyen_mon_it"),
                    "dia_diem_id": tra(dd, t["dia_diem"], "danh_muc_dia_diem"),
                    "kinh_nghiem_id": tra(kn, t["kinh_nghiem"], "danh_muc_kinh_nghiem"),
                    "hoc_van_id": None,                  # ITviec không có học vấn
                    "hinh_thuc_id": tra(ht, t["hinh_thuc"], "danh_muc_hinh_thuc_lam_viec"),
                    "loai_hinh_lam_viec_id": tra(lh, t["loai_hinh"], "danh_muc_loai_hinh_lam_viec"),
                    "cap_bac_id": tra(cb, t["cap_bac"], "danh_muc_cap_bac"),
                    "luong_min": t["luong_min"], "luong_max": t["luong_max"],
                    "luong_nguon": t["luong_nguon"],
                    "ngay_dang": t["ngay_dang"], "han_ung_tuyen": t["han_ung_tuyen"],
                    "trang_thai_id": tra(tt, t["trang_thai"], "danh_muc_trang_thai_tin"),
                    "nguon_tin": "itviec", "url_nguon": t["url_nguon"],
                }
                cur.execute(SQL_UPSERT_TIN, params)
                job_id, la_moi = cur.fetchone()
                moi += la_moi
                cap_nhat += (not la_moi)

                # Kỹ năng: xóa cũ, ghi lại theo dữ liệu mới nhất
                cur.execute("DELETE FROM tin_tuyen_dung_ky_nang WHERE job_id = %s", (job_id,))
                for ten, nhom in t["ky_nang"]:
                    cur.execute(
                        "INSERT INTO tin_tuyen_dung_ky_nang (job_id, ky_nang_id) VALUES (%s, %s) "
                        "ON CONFLICT DO NOTHING", (job_id, id_ky_nang(ten, nhom)))

                if idx % batch_size == 0:
                    conn.commit()
        conn.commit()
        print(f"\nĐã nạp xong: {moi} tin mới, {cap_nhat} tin cập nhật, {len(company_id)} công ty.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# =============================================================================
# MAIN
# =============================================================================
def main():
    ap = argparse.ArgumentParser(description="Nạp tin ITviec (JSON thô) vào OLTP")
    ap.add_argument("--dry-run", action="store_true", help="chỉ chuẩn hóa và in thống kê, không ghi DB")
    args = ap.parse_args()

    ky_nang_map = doc_json("ky_nang_mapping.json")
    cfg = {
        "cm_map": doc_json("chuyen_mon_mapping.json"),
        "dd_map": {khoa_chuan(k): v for k, v in doc_json("dia_diem_mapping.json").items()},
        "ky_nang_alias": {"_alias": {k.lower(): v for k, v in ky_nang_map["alias"].items()},
                          "_bo_qua": set(ky_nang_map["bo_qua"])},
        "nhom_cua": {ten.lower(): nhom for nhom, ds in ky_nang_map["nhom"].items() for ten in ds},
    }

    # Cố định Ngày Tham Chiếu cào dữ liệu (02/10/2026) để giữ phân loại Published/Expired ổn định
    NGAY_THAM_CHIEU = date.fromisoformat(os.getenv("NGAY_THAM_CHIEU", "2026-10-02"))
    hom_nay = NGAY_THAM_CHIEU
    tins, bo_qua = [], 0
    for path in sorted(glob.glob(str(JOBS_DIR / "*.json"))):
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        if not (d.get("url") and d.get("tieu_de") and d.get("ten_cong_ty")):
            bo_qua += 1
            continue
        tins.append(chuan_hoa_tin(d, cfg, hom_nay))

    mo_phong_luong(tins)
    in_thong_ke(tins, bo_qua)

    if args.dry_run:
        print("\n[dry-run] Không ghi vào DB.")
        return
    nap_vao_db(tins)


if __name__ == "__main__":
    main()