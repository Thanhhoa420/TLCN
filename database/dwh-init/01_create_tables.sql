-- ============================================
-- DATABASE: dwh_db (kho dữ liệu phân tích)
-- Star Schema: 1 fact (1 dòng = 1 tin tuyển dụng) + dimension + 1 bridge kỹ năng
-- ============================================

-- ---------- DIMENSIONS ----------
-- Khóa dimension giữ nguyên ID của OLTP để ETL ánh xạ đơn giản.
-- Mỗi dimension có thêm dòng -1 'Không xác định' (cuối file) cho dữ liệu bị thiếu.

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

-- Hình thức làm việc: LÀM VIỆC Ở ĐÂU (At office / Remote / Hybrid)
CREATE TABLE dim_hinh_thuc_lam_viec (
    hinh_thuc_id INT PRIMARY KEY,
    ten_hinh_thuc VARCHAR(100)
);

-- Loại hình làm việc: LOẠI HỢP ĐỒNG (Full-time / Part-time / Internship / Contract)
CREATE TABLE dim_loai_hinh_lam_viec (
    loai_hinh_lam_viec_id INT PRIMARY KEY,
    ten_loai_hinh VARCHAR(50)
);

-- Cấp bậc (Internship / Fresher / Junior / Middle / Senior / Manager)
CREATE TABLE dim_cap_bac (
    cap_bac_id INT PRIMARY KEY,
    ten_cap_bac VARCHAR(50)
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
    loai_hinh VARCHAR(100),
    quy_mo VARCHAR(50)
);

-- Khóa dạng YYYYMMDD (vd 20260903), do ETL tự sinh từ ngày đăng
CREATE TABLE dim_thoi_gian (
    thoi_gian_id INT PRIMARY KEY,
    ngay DATE,
    tuan INT,
    thang INT,
    quy INT,
    nam INT
);

-- ---------- FACT ----------
-- Grain: 1 dòng = 1 tin tuyển dụng. Ngày dùng cho thoi_gian_id là NGÀY ĐĂNG.
CREATE TABLE fact_tin_tuyen_dung (
    fact_id SERIAL PRIMARY KEY,
    job_id INT NOT NULL UNIQUE,   -- khóa tự nhiên từ OLTP; UNIQUE để ETL chạy lại không nhân đôi dòng
    company_id INT REFERENCES dim_cong_ty(company_id),
    chuyen_mon_id INT REFERENCES dim_chuyen_mon_it(chuyen_mon_id),
    dia_diem_id INT REFERENCES dim_dia_diem(dia_diem_id),
    kinh_nghiem_id INT REFERENCES dim_kinh_nghiem(kinh_nghiem_id),
    hoc_van_id INT REFERENCES dim_hoc_van(hoc_van_id),
    hinh_thuc_id INT REFERENCES dim_hinh_thuc_lam_viec(hinh_thuc_id),
    loai_hinh_lam_viec_id INT REFERENCES dim_loai_hinh_lam_viec(loai_hinh_lam_viec_id),
    cap_bac_id INT REFERENCES dim_cap_bac(cap_bac_id),
    trang_thai_id INT REFERENCES dim_trang_thai_tin(trang_thai_id),
    thoi_gian_id INT REFERENCES dim_thoi_gian(thoi_gian_id),
    -- Measures
    luong_min INT,
    luong_max INT,
    so_luong_tuyen INT,
    so_luot_xem INT,
    so_luot_luu INT,
    so_luot_ung_tuyen INT,
    -- Thuộc tính mô tả đi kèm (để lọc trên dashboard)
    luong_nguon VARCHAR(20),      -- 'crawl' | 'mo_phong' | 'nhap_tay' | NULL
    nguon_tin VARCHAR(20)         -- 'itviec' | 'web'
);

-- ---------- BRIDGE: quan hệ nhiều-nhiều giữa tin và kỹ năng ----------
-- ON DELETE CASCADE: xóa dòng fact thì các dòng kỹ năng của nó tự bị xóa theo
CREATE TABLE bridge_fact_ky_nang (
    fact_id INT REFERENCES fact_tin_tuyen_dung(fact_id) ON DELETE CASCADE,
    ky_nang_id INT REFERENCES dim_ky_nang(ky_nang_id),
    PRIMARY KEY (fact_id, ky_nang_id)
);

CREATE INDEX idx_bridge_ky_nang ON bridge_fact_ky_nang(ky_nang_id);

-- ---------- Thành viên "Không xác định" ----------
-- ETL gán -1 khi dữ liệu thiếu, để tin không bị mất khi JOIN
INSERT INTO dim_chuyen_mon_it      (chuyen_mon_id, ten_chuyen_mon)                       VALUES (-1, 'Không xác định');
INSERT INTO dim_dia_diem           (dia_diem_id, ten_tinh_thanh, khu_vuc)                VALUES (-1, 'Không xác định', NULL);
INSERT INTO dim_kinh_nghiem        (kinh_nghiem_id, mo_ta, so_nam_min, so_nam_max)       VALUES (-1, 'Không xác định', NULL, NULL);
INSERT INTO dim_hoc_van            (hoc_van_id, trinh_do)                                VALUES (-1, 'Không xác định');
INSERT INTO dim_hinh_thuc_lam_viec (hinh_thuc_id, ten_hinh_thuc)                         VALUES (-1, 'Không xác định');
INSERT INTO dim_loai_hinh_lam_viec (loai_hinh_lam_viec_id, ten_loai_hinh)                VALUES (-1, 'Không xác định');
INSERT INTO dim_cap_bac            (cap_bac_id, ten_cap_bac)                             VALUES (-1, 'Không xác định');
INSERT INTO dim_trang_thai_tin     (trang_thai_id, ten_trang_thai)                       VALUES (-1, 'Không xác định');
INSERT INTO dim_cong_ty            (company_id, ten_cong_ty, loai_hinh, quy_mo)          VALUES (-1, 'Không xác định', NULL, NULL);
INSERT INTO dim_thoi_gian          (thoi_gian_id, ngay, tuan, thang, quy, nam)           VALUES (-1, NULL, NULL, NULL, NULL, NULL);