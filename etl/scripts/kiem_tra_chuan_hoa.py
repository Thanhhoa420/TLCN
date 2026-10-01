"""
etl/scripts/kiem_tra_chuan_hoa.py
=================================
Kiểm tra chất lượng bước chuẩn hóa (KHÔNG cần DB, dùng chung hàm với load_itviec_to_oltp.py).

    python etl/scripts/kiem_tra_chuan_hoa.py          # kiểm tra tự động toàn bộ + xuất 60 tin mẫu
    python etl/scripts/kiem_tra_chuan_hoa.py --n 100  # mẫu 100 tin

Kết quả:
  1. In ra các nhóm tin "đáng ngờ" (phát hiện bằng luật, có thể báo nhầm - chỉ để đọc lướt).
  2. Ghi crawler/raw_data/_kiem_tra_mau.csv: mỗi dòng 1 tin, đặt dữ liệu gốc cạnh kết quả chuẩn hóa.
     Mở bằng Excel, điền x vào cột dung_sai_* nếu thấy sai.
"""
import argparse
import csv
import glob
import json
import random
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import load_itviec_to_oltp as L   # dùng lại đúng các hàm chuẩn hóa của script nạp

FILE_CSV = L.ROOT / "crawler" / "raw_data" / "_kiem_tra_mau.csv"

# Luật nghi vấn theo tiêu đề: (regex tiêu đề, tập chuyên môn được chấp nhận). Chỉ luật đầu tiên khớp được xét.
LUAT_TIEU_DE = [
    (r"\btester\b|\bqa\b|\bqc\b|\bsdet\b|kiểm thử", {"QA/Tester"}),
    (r"data engineer", {"Data Engineer"}),
    (r"data analyst|bi analyst", {"Data Analyst"}),
    (r"data scientist", {"Data Scientist"}),
    (r"devops|\bsre\b", {"DevOps Engineer"}),
    (r"business analyst|\bba\b", {"Business Analyst"}),
    (r"full-?stack", {"Fullstack Developer"}),
    (r"front-?end", {"Frontend Developer", "Fullstack Developer"}),
    (r"back-?end", {"Backend Developer", "Fullstack Developer"}),
    (r"android|\bios\b|mobile|flutter|react native", {"Mobile Developer"}),
    (r"security|pentest|bảo mật|an ninh", {"Security Engineer"}),
    (r"project manager|\bpmo\b|scrum master", {"Project Manager IT"}),
]


def tao_cfg():
    km = L.doc_json("ky_nang_mapping.json")
    return {
        "cm_map": L.doc_json("chuyen_mon_mapping.json"),
        "dd_map": {L.khoa_chuan(k): v for k, v in L.doc_json("dia_diem_mapping.json").items()},
        "ky_nang_alias": {"_alias": {k.lower(): v for k, v in km["alias"].items()},
                          "_bo_qua": set(km["bo_qua"])},
        "nhom_cua": {ten.lower(): nhom for nhom, ds in km["nhom"].items() for ten in ds},
    }


def doan_khop(yeu_cau):
    """Đoạn văn bản quanh chỗ script bắt được số năm - để mắt người kiểm tra nhanh."""
    if not yeu_cau:
        return "(yeu_cau rỗng)"
    m = L.RE_NAM.search(yeu_cau) or L.RE_KHONG_KN.search(yeu_cau)
    if not m:
        return "(không thấy mẫu số năm)"
    s, e = max(0, m.start() - 50), min(len(yeu_cau), m.end() + 50)
    return re.sub(r"\s+", " ", yeu_cau[s:e])


def in_nhom(ten, ds, toi_da=15):
    print(f"\n[{ten}] {len(ds)} tin")
    for tieu_de, ghi_chu in ds[:toi_da]:
        print(f"   - {tieu_de[:65]} | {ghi_chu}")
    if len(ds) > toi_da:
        print(f"   ... còn {len(ds) - toi_da} tin nữa")


def kiem_tra_tu_dong(tins, raws):
    nhom = {k: [] for k in [
        "Cấp bậc cao nhưng chỉ đòi <= 1 năm kinh nghiệm",
        "Cấp bậc thấp (Intern/Fresher/Junior) nhưng đòi >= 3 năm",
        "Lương cao bất thường (max > 150 triệu)",
        "Lương thấp bất thường (max < 5 triệu, không phải Intern)",
        "Chuỗi lương có số nhưng KHÔNG parse được",
        "Tiêu đề và chuyên môn có vẻ lệch nhau",
        "Chuyên môn 'Khác'",
    ]}
    for t in tins:
        nam, cb, cm, hi, td = t["so_nam"], t["cap_bac"], t["chuyen_mon"], t["luong_max"], t["tieu_de"]
        if cb in ("Senior", "Manager") and nam is not None and nam <= 1:
            nhom["Cấp bậc cao nhưng chỉ đòi <= 1 năm kinh nghiệm"].append((td, f"{cb}, {nam} năm"))
        if cb in ("Internship", "Fresher", "Junior") and nam is not None and nam >= 3:
            nhom["Cấp bậc thấp (Intern/Fresher/Junior) nhưng đòi >= 3 năm"].append((td, f"{cb}, {nam} năm"))
        if hi is not None and hi > 150_000_000:
            nhom["Lương cao bất thường (max > 150 triệu)"].append((td, f"{t['luong_min']}-{hi} ({t['luong_nguon']})"))
        if hi is not None and hi < 5_000_000 and cb != "Internship":
            nhom["Lương thấp bất thường (max < 5 triệu, không phải Intern)"].append((td, f"{t['luong_min']}-{hi} ({t['luong_nguon']})"))
        raw = raws[t["url_nguon"]].get("salary_placeholder_raw")
        if raw and re.search(r"\d", str(raw)) and L.parse_luong(raw) == (None, None):
            nhom["Chuỗi lương có số nhưng KHÔNG parse được"].append((td, f"raw = {raw!r}"))
        for pattern, chap_nhan in LUAT_TIEU_DE:
            if re.search(pattern, td.lower()):
                if cm not in chap_nhan:
                    nhom["Tiêu đề và chuyên môn có vẻ lệch nhau"].append(
                        (td, f"chuyên môn = {cm}; tag ITviec = {raws[t['url_nguon']].get('job_expertise')}"))
                break
        if cm == "Khác":
            nhom["Chuyên môn 'Khác'"].append((td, str(raws[t["url_nguon"]].get("job_expertise"))))

    print(f"=== KIỂM TRA TỰ ĐỘNG {len(tins)} TIN ===")
    for ten, ds in nhom.items():
        in_nhom(ten, ds)

    # Tin trùng (cùng công ty + cùng tiêu đề, khác URL do đăng nhiều thành phố)
    dem = Counter((t["cong_ty"]["ten"].lower(), re.sub(r"\s+", " ", t["tieu_de"].lower()).strip()) for t in tins)
    nhom_trung = {k: v for k, v in dem.items() if v > 1}
    print(f"\n[Tin trùng (cùng công ty + tiêu đề)] {len(nhom_trung)} nhóm, "
          f"dư ra {sum(v - 1 for v in nhom_trung.values())} tin so với số vị trí thật")

    # Mức độ thiếu dữ liệu
    n = len(tins)
    print("\n[Tỷ lệ thiếu dữ liệu]")
    for ten, truong in [("kinh nghiệm", "kinh_nghiem"), ("cấp bậc", "cap_bac"), ("lương", "luong_nguon")]:
        thieu = sum(1 for t in tins if t[truong] is None)
        print(f"   {ten}: {thieu}/{n} tin NULL ({thieu * 100 // n}%)")


def xuat_mau(tins, raws, n_mau):
    mau = random.Random(7).sample(tins, min(n_mau, len(tins)))
    cot = ["url", "tieu_de", "salary_raw", "salary_range_raw", "luong_min", "luong_max", "luong_nguon",
           "yeu_cau_doan_khop", "so_nam", "kinh_nghiem", "cap_bac", "cap_bac_nguon",
           "job_expertise_goc", "chuyen_mon", "tinh_thanh_goc", "dia_diem",
           "dung_sai_luong", "dung_sai_kinh_nghiem", "dung_sai_cap_bac", "dung_sai_chuyen_mon", "ghi_chu"]
    with open(FILE_CSV, "w", newline="", encoding="utf-8-sig") as f:   # utf-8-sig để Excel đọc đúng tiếng Việt
        w = csv.writer(f)
        w.writerow(cot)
        for t in mau:
            d = raws[t["url_nguon"]]
            w.writerow([t["url_nguon"], t["tieu_de"], d.get("salary_placeholder_raw"), d.get("salary_range_raw"),
                        t["luong_min"], t["luong_max"], t["luong_nguon"],
                        doan_khop(d.get("yeu_cau")), t["so_nam"], t["kinh_nghiem"],
                        t["cap_bac"], t["cap_bac_nguon"],
                        "; ".join(d.get("job_expertise") or []), t["chuyen_mon"],
                        d.get("tinh_thanh"), t["dia_diem"], "", "", "", "", ""])
    print(f"\nĐã ghi {len(mau)} tin mẫu -> {FILE_CSV}")


def main():
    ap = argparse.ArgumentParser(description="Kiểm tra chất lượng chuẩn hóa tin ITviec")
    ap.add_argument("--n", type=int, default=60, help="số tin mẫu xuất ra CSV (mặc định 60)")
    args = ap.parse_args()

    cfg, hom_nay = tao_cfg(), date.today()
    tins, raws = [], {}
    for path in sorted(glob.glob(str(L.JOBS_DIR / "*.json"))):
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        if not (d.get("url") and d.get("tieu_de") and d.get("ten_cong_ty")):
            continue
        t = L.chuan_hoa_tin(d, cfg, hom_nay)
        tins.append(t)
        raws[t["url_nguon"]] = d
    L.mo_phong_luong(tins)

    kiem_tra_tu_dong(tins, raws)
    xuat_mau(tins, raws, args.n)


if __name__ == "__main__":
    main()