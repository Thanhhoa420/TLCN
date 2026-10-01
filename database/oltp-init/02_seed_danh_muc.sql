-- ============================================
-- SEED DATA: các bảng danh mục (lookup tables)
-- ============================================

-- Chuyên môn IT
-- ('Game Developer', 'Software/Solution Architect', 'Embedded/IoT Engineer' và 'Khác' là mới:
--  'Khác' chứa các tin không map được vào chuyên môn nào)
INSERT INTO danh_muc_chuyen_mon_it (ten_chuyen_mon) VALUES
('Backend Developer'),
('Frontend Developer'),
('Fullstack Developer'),
('Mobile Developer'),
('Data Engineer'),
('Data Analyst'),
('Data Scientist'),
('DevOps Engineer'),
('QA/Tester'),
('System Admin/Network'),
('Business Analyst'),
('UI/UX Designer'),
('AI/Machine Learning Engineer'),
('Project Manager IT'),
('Security Engineer'),
('Game Developer'),
('Software/Solution Architect'),
('Embedded/IoT Engineer'),
('Khác');

-- Địa điểm (tỉnh/thành)
-- Đã bỏ 'Remote': làm remote thuộc "hình thức làm việc", không phải địa điểm
INSERT INTO danh_muc_dia_diem (ten_tinh_thanh, khu_vuc) VALUES
('TP. Hồ Chí Minh', 'Miền Nam'),
('Hà Nội', 'Miền Bắc'),
('Đà Nẵng', 'Miền Trung'),
('Cần Thơ', 'Miền Nam'),
('Bình Dương', 'Miền Nam'),
('Đồng Nai', 'Miền Nam'),
('Hải Phòng', 'Miền Bắc'),
('Huế', 'Miền Trung'),
('Khánh Hòa', 'Miền Trung');

-- Kinh nghiệm
INSERT INTO danh_muc_kinh_nghiem (mo_ta, so_nam_min, so_nam_max) VALUES
('Chưa có kinh nghiệm', 0, 0),
('Dưới 1 năm', 0, 1),
('1-2 năm', 1, 2),
('2-3 năm', 2, 3),
('3-5 năm', 3, 5),
('5-10 năm', 5, 10),
('Trên 10 năm', 10, NULL);

-- Học vấn
INSERT INTO danh_muc_hoc_van (trinh_do) VALUES
('Không yêu cầu'),
('Trung cấp'),
('Cao đẳng'),
('Đại học'),
('Sau đại học');

-- Hình thức làm việc (LÀM VIỆC Ở ĐÂU: tại văn phòng/từ xa/kết hợp)
INSERT INTO danh_muc_hinh_thuc_lam_viec (ten_hinh_thuc) VALUES
('At office'),
('Remote'),
('Hybrid');

-- Loại hình làm việc (LOẠI HỢP ĐỒNG: khác với hình thức làm việc ở trên)
-- Nguồn: employmentType (JSON-LD, ITviec)
INSERT INTO danh_muc_loai_hinh_lam_viec (ten_loai_hinh) VALUES
('Full-time'),
('Part-time'),
('Internship'),
('Contract');

-- Cấp bậc / seniority level ('Middle' là mới)
INSERT INTO danh_muc_cap_bac (ten_cap_bac) VALUES
('Internship'),
('Fresher'),
('Junior'),
('Middle'),
('Senior'),
('Manager');

-- Trạng thái tin tuyển dụng
INSERT INTO danh_muc_trang_thai_tin (ten_trang_thai) VALUES
('Draft'),
('Pending'),
('Published'),
('Closed'),
('Expired'),
('Rejected');

-- Kỹ năng
INSERT INTO ky_nang (ten_ky_nang, nhom_ky_nang) VALUES
('Python', 'Ngôn ngữ lập trình'),
('Java', 'Ngôn ngữ lập trình'),
('JavaScript', 'Ngôn ngữ lập trình'),
('TypeScript', 'Ngôn ngữ lập trình'),
('C#', 'Ngôn ngữ lập trình'),
('PHP', 'Ngôn ngữ lập trình'),
('Go', 'Ngôn ngữ lập trình'),
('React', 'Frontend'),
('Vue.js', 'Frontend'),
('Angular', 'Frontend'),
('Node.js', 'Backend'),
('Spring Boot', 'Backend'),
('Django', 'Backend'),
('FastAPI', 'Backend'),
('.NET', 'Backend'),
('PostgreSQL', 'Database'),
('MySQL', 'Database'),
('MongoDB', 'Database'),
('Redis', 'Database'),
('Docker', 'DevOps'),
('Kubernetes', 'DevOps'),
('AWS', 'Cloud'),
('Azure', 'Cloud'),
('Google Cloud', 'Cloud'),
('Git', 'Công cụ'),
('CI/CD', 'DevOps'),
('Airflow', 'Data Engineering'),
('Spark', 'Data Engineering'),
('Pandas', 'Data'),
('Machine Learning', 'AI/ML'),
('React Native', 'Mobile'),
('Flutter', 'Mobile'),
('Swift', 'Mobile'),
('Kotlin', 'Mobile'),
('Figma', 'Design'),
('Selenium', 'Testing');