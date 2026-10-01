"""
etl/scripts/oltp_to_dwh.py
==========================
Trích xuất dữ liệu từ OLTP (oltp_db) và nạp vào Data Warehouse (dwh_db).
Chạy an toàn nhiều lần (Idempotent / Upsert).

Cách trích xuất: static capture (đọc toàn bộ OLTP mỗi lần) - phù hợp quy mô nhỏ.
Mọi thao tác nằm trong 1 transaction: đối soát lệch -> rollback, DWH không bị nửa vời.

Chạy từ thư mục gốc project:
    python etl/scripts/oltp_to_dwh.py
"""

import os
from datetime import datetime  # noqa: F401  (giữ lại nếu DAG import)
import psycopg2
from psycopg2.extras import execute_values


def get_oltp_conn():
    return psycopg2.connect(
        host=os.getenv("OLTP_HOST", "localhost"),
        port=os.getenv("OLTP_PORT", "5432"),
        dbname=os.getenv("OLTP_DB", "oltp_db"),
        user=os.getenv("OLTP_USER", "postgres"),
        password=os.getenv("OLTP_PASSWORD", "postgres"),
    )


def get_dwh_conn():
    return psycopg2.connect(
        host=os.getenv("DWH_HOST", "localhost"),
        port=os.getenv("DWH_PORT", "5432"),
        dbname=os.getenv("DWH_DB", "dwh_db"),
        user=os.getenv("DWH_USER", "postgres"),
        password=os.getenv("DWH_PASSWORD", "postgres"),
    )


def sync_dimensions(oltp_cur, dwh_cur):
    """Đồng bộ các bảng Dimension từ OLTP sang DWH (giữ nguyên ID của OLTP).
    Dòng -1 'Không xác định' đã được tạo sẵn trong dwh-init, không bị đụng tới."""
    print("[1/3] Đang đồng bộ các bảng Dimension...")

    # (bảng_oltp, bảng_dwh, cột id, các cột còn lại)
    simple_dims = [
        ("danh_muc_chuyen_mon_it", "dim_chuyen_mon_it", "chuyen_mon_id", ["ten_chuyen_mon"]),
        ("danh_muc_dia_diem", "dim_dia_diem", "dia_diem_id", ["ten_tinh_thanh", "khu_vuc"]),
        ("danh_muc_kinh_nghiem", "dim_kinh_nghiem", "kinh_nghiem_id", ["mo_ta", "so_nam_min", "so_nam_max"]),
        ("danh_muc_hoc_van", "dim_hoc_van", "hoc_van_id", ["trinh_do"]),
        ("danh_muc_hinh_thuc_lam_viec", "dim_hinh_thuc_lam_viec", "hinh_thuc_id", ["ten_hinh_thuc"]),
        ("danh_muc_loai_hinh_lam_viec", "dim_loai_hinh_lam_viec", "loai_hinh_lam_viec_id", ["ten_loai_hinh"]),
        ("danh_muc_cap_bac", "dim_cap_bac", "cap_bac_id", ["ten_cap_bac"]),
        ("danh_muc_trang_thai_tin", "dim_trang_thai_tin", "trang_thai_id", ["ten_trang_thai"]),
        ("ky_nang", "dim_ky_nang", "ky_nang_id", ["ten_ky_nang", "nhom_ky_nang"]),
        ("nha_tuyen_dung", "dim_cong_ty", "company_id", ["ten_cong_ty", "loai_hinh", "quy_mo"]),
    ]

    for tbl_oltp, tbl_dwh, id_col, cols in simple_dims:
        cols_str = ", ".join(cols)
        oltp_cur.execute(f"SELECT {id_col}, {cols_str} FROM {tbl_oltp}")
        rows = oltp_cur.fetchall()
        if not rows:
            continue

        placeholders = ", ".join(["%s"] * (len(cols) + 1))
        update_set = ", ".join([f"{c} = EXCLUDED.{c}" for c in cols])
        sql = f"""
            INSERT INTO {tbl_dwh} ({id_col}, {cols_str})
            VALUES ({placeholders})
            ON CONFLICT ({id_col}) DO UPDATE SET {update_set};
        """
        dwh_cur.executemany(sql, rows)


def sync_dim_thoi_gian(oltp_cur, dwh_cur):
    """Sinh dim_thoi_gian từ các ngày đăng duy nhất của OLTP (khóa YYYYMMDD)."""
    oltp_cur.execute("SELECT DISTINCT ngay_dang::date FROM tin_tuyen_dung WHERE ngay_dang IS NOT NULL")
    time_rows = []
    for (d,) in oltp_cur.fetchall():
        if not d:
            continue
        thang = d.month
        # tuan: tuần ISO (ngày cuối/đầu năm có thể thuộc tuần của năm kế bên)
        time_rows.append((int(d.strftime("%Y%m%d")), d, d.isocalendar()[1],
                          thang, (thang - 1) // 3 + 1, d.year))

    if time_rows:
        sql = """
            INSERT INTO dim_thoi_gian (thoi_gian_id, ngay, tuan, thang, quy, nam)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (thoi_gian_id) DO NOTHING;
        """
        dwh_cur.executemany(sql, time_rows)


def sync_fact_and_bridge(oltp_cur, dwh_cur):
    """Đồng bộ bảng Fact (grain = 1 tin) và bảng Bridge kỹ năng."""
    print("[2/3] Đang nạp fact_tin_tuyen_dung...")

    # Thiếu khóa dimension -> gán -1 ('Không xác định') để tin không bị mất khi JOIN
    sql_extract_jobs = """
        SELECT
            t.job_id,
            COALESCE(t.company_id, -1),
            COALESCE(t.chuyen_mon_id, -1),
            COALESCE(t.dia_diem_id, -1),
            COALESCE(t.kinh_nghiem_id, -1),
            COALESCE(t.hoc_van_id, -1),
            COALESCE(t.hinh_thuc_id, -1),
            COALESCE(t.loai_hinh_lam_viec_id, -1),
            COALESCE(t.cap_bac_id, -1),
            COALESCE(t.trang_thai_id, -1),
            CASE WHEN t.ngay_dang IS NOT NULL
                 THEN TO_CHAR(t.ngay_dang, 'YYYYMMDD')::INT ELSE -1 END AS thoi_gian_id,
            t.luong_min,
            t.luong_max,
            t.so_luong_tuyen,
            t.so_luot_xem,
            COALESCE(l.so_luot_luu, 0),
            COALESCE(u.so_luot_ung_tuyen, 0),
            t.luong_nguon,
            t.nguon_tin
        FROM tin_tuyen_dung t
        LEFT JOIN (SELECT job_id, COUNT(*) AS so_luot_luu FROM luu_tin GROUP BY job_id) l
               ON t.job_id = l.job_id
        LEFT JOIN (SELECT job_id, COUNT(*) AS so_luot_ung_tuyen FROM ung_tuyen GROUP BY job_id) u
               ON t.job_id = u.job_id;
    """
    oltp_cur.execute(sql_extract_jobs)
    jobs = oltp_cur.fetchall()

    sql_upsert_fact = """
        INSERT INTO fact_tin_tuyen_dung (
            job_id, company_id, chuyen_mon_id, dia_diem_id, kinh_nghiem_id,
            hoc_van_id, hinh_thuc_id, loai_hinh_lam_viec_id, cap_bac_id, trang_thai_id,
            thoi_gian_id, luong_min, luong_max, so_luong_tuyen, so_luot_xem,
            so_luot_luu, so_luot_ung_tuyen, luong_nguon, nguon_tin
        ) VALUES %s
        ON CONFLICT (job_id) DO UPDATE SET
            company_id = EXCLUDED.company_id,
            chuyen_mon_id = EXCLUDED.chuyen_mon_id,
            dia_diem_id = EXCLUDED.dia_diem_id,
            kinh_nghiem_id = EXCLUDED.kinh_nghiem_id,
            hoc_van_id = EXCLUDED.hoc_van_id,
            hinh_thuc_id = EXCLUDED.hinh_thuc_id,
            loai_hinh_lam_viec_id = EXCLUDED.loai_hinh_lam_viec_id,
            cap_bac_id = EXCLUDED.cap_bac_id,
            trang_thai_id = EXCLUDED.trang_thai_id,
            thoi_gian_id = EXCLUDED.thoi_gian_id,
            luong_min = EXCLUDED.luong_min,
            luong_max = EXCLUDED.luong_max,
            so_luong_tuyen = EXCLUDED.so_luong_tuyen,
            so_luot_xem = EXCLUDED.so_luot_xem,
            so_luot_luu = EXCLUDED.so_luot_luu,
            so_luot_ung_tuyen = EXCLUDED.so_luot_ung_tuyen,
            luong_nguon = EXCLUDED.luong_nguon,
            nguon_tin = EXCLUDED.nguon_tin;
    """
    if jobs:
        execute_values(dwh_cur, sql_upsert_fact, jobs)

    # Tin đã bị xóa khỏi OLTP -> xóa fact tương ứng (bridge tự xóa nhờ ON DELETE CASCADE)
    job_ids_oltp = [j[0] for j in jobs]
    dwh_cur.execute("DELETE FROM fact_tin_tuyen_dung WHERE job_id <> ALL(%s)", (job_ids_oltp,))

    print("[3/3] Đang nạp bridge_fact_ky_nang...")
    dwh_cur.execute("SELECT job_id, fact_id FROM fact_tin_tuyen_dung")
    job_to_fact = dict(dwh_cur.fetchall())

    oltp_cur.execute("SELECT job_id, ky_nang_id FROM tin_tuyen_dung_ky_nang")
    bridge_data = [(job_to_fact[j], k) for j, k in oltp_cur.fetchall() if j in job_to_fact]

    # Xóa toàn bộ bridge rồi nạp lại: tin bị gỡ hết kỹ năng cũng được dọn sạch
    dwh_cur.execute("DELETE FROM bridge_fact_ky_nang")
    if bridge_data:
        execute_values(
            dwh_cur,
            "INSERT INTO bridge_fact_ky_nang (fact_id, ky_nang_id) VALUES %s ON CONFLICT DO NOTHING",
            bridge_data,
        )


def doi_soat(oltp_cur, dwh_cur):
    """Đối soát số dòng OLTP vs DWH (audit count). Lệch ở fact/bridge -> ném lỗi để rollback."""
    print("[Đối soát] Số dòng OLTP vs DWH:")
    # (tên, SQL OLTP, SQL DWH, bắt buộc khớp?)
    kiem_tra = [
        ("tin tuyển dụng", "SELECT COUNT(*) FROM tin_tuyen_dung",
         "SELECT COUNT(*) FROM fact_tin_tuyen_dung", True),
        ("tin - kỹ năng", "SELECT COUNT(*) FROM tin_tuyen_dung_ky_nang",
         "SELECT COUNT(*) FROM bridge_fact_ky_nang", True),
        ("công ty", "SELECT COUNT(*) FROM nha_tuyen_dung",
         "SELECT COUNT(*) - 1 FROM dim_cong_ty", False),   # trừ dòng -1
        ("kỹ năng", "SELECT COUNT(*) FROM ky_nang",
         "SELECT COUNT(*) FROM dim_ky_nang", False),
    ]
    loi = []
    for ten, sql_oltp, sql_dwh, bat_buoc in kiem_tra:
        oltp_cur.execute(sql_oltp)
        n_oltp = oltp_cur.fetchone()[0]
        dwh_cur.execute(sql_dwh)
        n_dwh = dwh_cur.fetchone()[0]
        ok = n_oltp == n_dwh
        print(f"  {ten}: OLTP={n_oltp} | DWH={n_dwh} -> {'OK' if ok else 'LỆCH'}")
        if bat_buoc and not ok:
            loi.append(ten)
    if loi:
        raise RuntimeError("Đối soát lệch: " + ", ".join(loi))

    # Chất lượng dữ liệu: bao nhiêu tin phải gán 'Không xác định' (-1) ở từng dimension
    cot_fk = ["company_id", "chuyen_mon_id", "dia_diem_id", "kinh_nghiem_id", "hoc_van_id",
              "hinh_thuc_id", "loai_hinh_lam_viec_id", "cap_bac_id", "trang_thai_id", "thoi_gian_id"]
    dwh_cur.execute("SELECT COUNT(*), " +
                    ", ".join(f"COUNT(*) FILTER (WHERE {c} = -1)" for c in cot_fk) +
                    " FROM fact_tin_tuyen_dung")
    tong, *so_thieu = dwh_cur.fetchone()
    print(f"  Số tin gán 'Không xác định' (-1) trên tổng {tong}:")
    for c, n in zip(cot_fk, so_thieu):
        print(f"    {c}: {n}")


def main():
    print("=== BẮT ĐẦU ETL TỪ OLTP SANG DWH ===")
    oltp_conn = get_oltp_conn()
    dwh_conn = get_dwh_conn()

    try:
        with oltp_conn.cursor() as oltp_cur, dwh_conn.cursor() as dwh_cur:
            sync_dimensions(oltp_cur, dwh_cur)
            sync_dim_thoi_gian(oltp_cur, dwh_cur)
            sync_fact_and_bridge(oltp_cur, dwh_cur)
            doi_soat(oltp_cur, dwh_cur)   # lệch -> nhảy xuống except, rollback

        dwh_conn.commit()
        print("=== CHUYỂN DỮ LIỆU TỪ OLTP SANG DWH THÀNH CÔNG! ===")
    except Exception as e:
        dwh_conn.rollback()
        print(f"LỖI ETL: {e}")
        raise
    finally:
        oltp_conn.close()
        dwh_conn.close()


if __name__ == "__main__":
    main()