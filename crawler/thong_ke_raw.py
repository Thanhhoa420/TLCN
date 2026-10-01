# crawler/thong_ke_raw.py
# Thống kê giá trị khác nhau của các field thô, để làm file mapping
import glob, json, re
from collections import Counter

FIELDS_LIST = ["ky_nang", "job_expertise"]  # field dạng list
FIELDS_STR = ["tinh_thanh", "quan_huyen", "hinh_thuc_lam_viec",
              "loai_hinh_lam_viec", "cap_bac", "loai_hinh_cong_ty",
              "quy_mo_cong_ty", "khu_vuc_crawl"]

cnt = {f: Counter() for f in FIELDS_LIST + FIELDS_STR}
salary_patterns = Counter()   # đổi số thành 'N' để gom theo "dạng" lương
salary_examples = {}
date_formats = {"ngay_dang_raw": Counter(), "han_ung_tuyen_raw": Counter()}
date_examples = {}

files = glob.glob("crawler/raw_data/jobs/*.json")
for p in files:
    with open(p, encoding="utf-8") as fh:
        d = json.load(fh)
    for f in FIELDS_LIST:
        for v in d.get(f) or []:
            cnt[f][v] += 1
    for f in FIELDS_STR:
        cnt[f][d.get(f)] += 1
    # Dạng lương
    s = d.get("salary_placeholder_raw")
    pat = re.sub(r"\d+([.,]\d+)?", "N", str(s)) if s is not None else "None"
    salary_patterns[pat] += 1
    salary_examples.setdefault(pat, s)
    # Dạng ngày
    for f in date_formats:

        v = d.get(f)
        pat_d = re.sub(r"\d", "9", str(v)) if v is not None else "None"
        date_formats[f][pat_d] += 1
        date_examples.setdefault((f, pat_d), v)

with open("crawler/raw_data/_thong_ke.txt", "w", encoding="utf-8") as out:
    out.write(f"Tổng số file: {len(files)}\n\n")
    for f, c in cnt.items():
        out.write(f"=== {f} ({len(c)} giá trị khác nhau) ===\n")
        for v, n in c.most_common(300):
            out.write(f"{n:5d}  {v}\n")
        out.write("\n")
    out.write("=== DẠNG LƯƠNG (số -> N) ===\n")
    for pat, n in salary_patterns.most_common():
        out.write(f"{n:5d}  {pat}    | ví dụ: {salary_examples[pat]}\n")
    out.write("\n=== DẠNG NGÀY ===\n")
    for f, c in date_formats.items():
        for pat, n in c.most_common():
            out.write(f"{n:5d}  {f}: {pat}    | ví dụ: {date_examples[(f, pat)]}\n")
print("Đã ghi crawler/raw_data/_thong_ke.txt")