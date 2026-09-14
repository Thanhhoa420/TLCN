-- ============================================
-- DATABASE: oltp_db (website vận hành)
-- ============================================

-- --- Bảng danh mục (lookup tables) ---
CREATE TABLE danh_muc_chuyen_mon_it (
    chuyen_mon_id SERIAL PRIMARY KEY,
    ten_chuyen_mon VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE danh_muc_dia_diem (
    dia_diem_id SERIAL PRIMARY KEY,
    ten_tinh_thanh VARCHAR(100) UNIQUE NOT NULL,
    khu_vuc VARCHAR(100)
);

CREATE TABLE danh_muc_kinh_nghiem (
    kinh_nghiem_id SERIAL PRIMARY KEY,
    mo_ta VARCHAR(100) NOT NULL,
    so_nam_min INT,
    so_nam_max INT
);

CREATE TABLE danh_muc_hoc_van (
    hoc_van_id SERIAL PRIMARY KEY,
    trinh_do VARCHAR(100) NOT NULL
);

CREATE TABLE danh_muc_hinh_thuc_lam_viec (
    hinh_thuc_id SERIAL PRIMARY KEY,
    ten_hinh_thuc VARCHAR(100) NOT NULL
);

CREATE TABLE danh_muc_trang_thai_tin (
    trang_thai_id SERIAL PRIMARY KEY,
    ten_trang_thai VARCHAR(50) NOT NULL
);

CREATE TABLE ky_nang (
    ky_nang_id SERIAL PRIMARY KEY,
    ten_ky_nang VARCHAR(100) UNIQUE NOT NULL,
    nhom_ky_nang VARCHAR(100)
);

-- --- Bảng nghiệp vụ chính ---
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL, -- nha_tuyen_dung, ung_vien, admin
    full_name VARCHAR(255),
    phone VARCHAR(20),
    avatar_url VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE nha_tuyen_dung (
    company_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL UNIQUE REFERENCES users(user_id),
    ten_cong_ty VARCHAR(255) NOT NULL,
    logo_url VARCHAR(500),
    loai_hinh VARCHAR(50),
    quy_mo VARCHAR(50),
    dia_chi VARCHAR(500),
    dia_diem_id INT REFERENCES danh_muc_dia_diem(dia_diem_id),
    website VARCHAR(255),
    mo_ta TEXT,
    trang_thai_duyet VARCHAR(20) DEFAULT 'cho_duyet',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE ung_vien (
    candidate_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL UNIQUE REFERENCES users(user_id),
    ngay_sinh DATE,
    gioi_tinh VARCHAR(10),
    dia_diem_id INT REFERENCES danh_muc_dia_diem(dia_diem_id),
    hoc_van_id INT REFERENCES danh_muc_hoc_van(hoc_van_id),
    kinh_nghiem_id INT REFERENCES danh_muc_kinh_nghiem(kinh_nghiem_id),
    cv_url VARCHAR(500),
    gioi_thieu_ban_than TEXT,
    mong_muon_luong INT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE tin_tuyen_dung (
    job_id SERIAL PRIMARY KEY,
    company_id INT NOT NULL REFERENCES nha_tuyen_dung(company_id),
    tieu_de VARCHAR(255) NOT NULL,
    mo_ta_cong_viec TEXT,
    yeu_cau TEXT,
    quyen_loi TEXT,
    chuyen_mon_id INT REFERENCES danh_muc_chuyen_mon_it(chuyen_mon_id),
    dia_diem_id INT REFERENCES danh_muc_dia_diem(dia_diem_id),
    kinh_nghiem_id INT REFERENCES danh_muc_kinh_nghiem(kinh_nghiem_id),
    hoc_van_id INT REFERENCES danh_muc_hoc_van(hoc_van_id),
    hinh_thuc_id INT REFERENCES danh_muc_hinh_thuc_lam_viec(hinh_thuc_id),
    luong_min INT,
    luong_max INT,
    so_luong_tuyen INT DEFAULT 1,
    so_luot_xem INT DEFAULT 0,
    ngay_dang TIMESTAMP,
    han_ung_tuyen DATE,
    trang_thai_id INT REFERENCES danh_muc_trang_thai_tin(trang_thai_id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE tin_tuyen_dung_ky_nang (
    job_id INT REFERENCES tin_tuyen_dung(job_id),
    ky_nang_id INT REFERENCES ky_nang(ky_nang_id),
    PRIMARY KEY (job_id, ky_nang_id)
);

CREATE TABLE ho_so_ky_nang_ung_vien (
    candidate_id INT REFERENCES ung_vien(candidate_id),
    ky_nang_id INT REFERENCES ky_nang(ky_nang_id),
    muc_do VARCHAR(20),
    PRIMARY KEY (candidate_id, ky_nang_id)
);

CREATE TABLE luu_tin (
    candidate_id INT REFERENCES ung_vien(candidate_id),
    job_id INT REFERENCES tin_tuyen_dung(job_id),
    ngay_luu TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (candidate_id, job_id)
);

CREATE TABLE ung_tuyen (
    application_id SERIAL PRIMARY KEY,
    candidate_id INT NOT NULL REFERENCES ung_vien(candidate_id),
    job_id INT NOT NULL REFERENCES tin_tuyen_dung(job_id),
    cv_url_nop VARCHAR(500),
    thu_gioi_thieu TEXT,
    trang_thai VARCHAR(30) DEFAULT 'Da nop',
    ngay_ung_tuyen TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);