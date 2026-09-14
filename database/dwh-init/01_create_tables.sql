-- ============================================
-- DATABASE: dwh_db (kho dữ liệu phân tích)
-- ============================================

CREATE TABLE dim_chuyen_mon_it (
    chuyen_mon_id INT PRIMARY KEY,
    ten_chuyen_mon VARCHAR(100)
);

CREATE TABLE dim_dia_diem (
    dia_diem_id INT PRIMARY KEY,
    ten_tinh_thanh VARCHAR(100),
    khu_vuc VARCHAR(100)
);

CREATE TABLE dim_kinh_nghiem (
    kinh_nghiem_id INT PRIMARY KEY,
    mo_ta VARCHAR(100),
    so_nam_min INT,
    so_nam_max INT
);

CREATE TABLE dim_hoc_van (
    hoc_van_id INT PRIMARY KEY,
    trinh_do VARCHAR(100)
);

CREATE TABLE dim_hinh_thuc_lam_viec (
    hinh_thuc_id INT PRIMARY KEY,
    ten_hinh_thuc VARCHAR(100)
);

CREATE TABLE dim_trang_thai_tin (
    trang_thai_id INT PRIMARY KEY,
    ten_trang_thai VARCHAR(50)
);

CREATE TABLE dim_ky_nang (
    ky_nang_id INT PRIMARY KEY,
    ten_ky_nang VARCHAR(100),
    nhom_ky_nang VARCHAR(100)
);

CREATE TABLE dim_cong_ty (
    company_id INT PRIMARY KEY,
    ten_cong_ty VARCHAR(255),
    loai_hinh VARCHAR(50),
    quy_mo VARCHAR(50)
);

CREATE TABLE dim_thoi_gian (
    thoi_gian_id SERIAL PRIMARY KEY,
    ngay DATE,
    tuan INT,
    thang INT,
    quy INT,
    nam INT
);

CREATE TABLE fact_tin_tuyen_dung (
    fact_id SERIAL PRIMARY KEY,
    job_id INT,
    company_id INT REFERENCES dim_cong_ty(company_id),
    chuyen_mon_id INT REFERENCES dim_chuyen_mon_it(chuyen_mon_id),
    dia_diem_id INT REFERENCES dim_dia_diem(dia_diem_id),
    kinh_nghiem_id INT REFERENCES dim_kinh_nghiem(kinh_nghiem_id),
    hoc_van_id INT REFERENCES dim_hoc_van(hoc_van_id),
    hinh_thuc_id INT REFERENCES dim_hinh_thuc_lam_viec(hinh_thuc_id),
    trang_thai_id INT REFERENCES dim_trang_thai_tin(trang_thai_id),
    thoi_gian_id INT REFERENCES dim_thoi_gian(thoi_gian_id),
    luong_min INT,
    luong_max INT,
    so_luong_tuyen INT,
    so_luot_xem INT,
    so_luot_luu INT,
    so_luot_ung_tuyen INT
);

-- --- Bridge table: xử lý quan hệ nhiều-nhiều giữa fact và kỹ năng ---
CREATE TABLE bridge_fact_ky_nang (
    fact_id INT REFERENCES fact_tin_tuyen_dung(fact_id),
    ky_nang_id INT REFERENCES dim_ky_nang(ky_nang_id),
    PRIMARY KEY (fact_id, ky_nang_id)
);