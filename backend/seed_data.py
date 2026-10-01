from app.database import SessionLocal
from app.models.danh_muc import (
    DanhMucChuyenMon, DanhMucDiaDiem, DanhMucKinhNghiem,
    DanhMucHocVan, DanhMucHinhThuc, DanhMucTrangThai
)

def seed_data():
    db = SessionLocal()

    # 1. Chuyên môn IT
    if db.query(DanhMucChuyenMon).count() == 0:
        chuyen_mons = [
            "Lập trình Backend", "Lập trình Frontend", "Full-stack", 
            "Data Engineer", "Data Analyst/BI", "DevOps/System Admin"
        ]
        for cm in chuyen_mons:
            db.add(DanhMucChuyenMon(ten_chuyen_mon=cm))
    
    # 2. Địa điểm
    if db.query(DanhMucDiaDiem).count() == 0:
        dia_diems = [
            {"ten": "Hồ Chí Minh", "kv": "Miền Nam"},
            {"ten": "Hà Nội", "kv": "Miền Bắc"},
            {"ten": "Đà Nẵng", "kv": "Miền Trung"},
            {"ten": "Khác/Toàn quốc (Remote)", "kv": "-"}
        ]
        for dd in dia_diems:
            db.add(DanhMucDiaDiem(ten_tinh_thanh=dd["ten"], khu_vuc=dd["kv"]))

    # 3. Kinh nghiệm
    if db.query(DanhMucKinhNghiem).count() == 0:
        kinh_nghiems = [
            {"mt": "Không yêu cầu", "min": 0, "max": 0},
            {"mt": "Dưới 1 năm", "min": 0, "max": 1},
            {"mt": "1-2 năm", "min": 1, "max": 2},
            {"mt": "Trên 2 năm", "min": 2, "max": 99}
        ]
        for kn in kinh_nghiems:
            db.add(DanhMucKinhNghiem(mo_ta=kn["mt"], so_nam_min=kn["min"], so_nam_max=kn["max"]))

    # 4. Học vấn
    if db.query(DanhMucHocVan).count() == 0:
        hoc_vans = ["Không yêu cầu", "Trung cấp/Cao đẳng", "Đại học", "Sau đại học"]
        for hv in hoc_vans:
            db.add(DanhMucHocVan(trinh_do=hv))

    # 5. Hình thức làm việc
    if db.query(DanhMucHinhThuc).count() == 0:
        hinh_thucs = ["Full-time", "Part-time", "Remote", "Hybrid", "Internship"]
        for ht in hinh_thucs:
            db.add(DanhMucHinhThuc(ten_hinh_thuc=ht))

    # 6. Trạng thái tin
    if db.query(DanhMucTrangThai).count() == 0:
        trang_thais = ["Draft", "Pending", "Published", "Closed", "Expired"]
        for tt in trang_thais:
            db.add(DanhMucTrangThai(ten_trang_thai=tt))

    db.commit()
    db.close()
    print(" Đã nạp thành công dữ liệu danh mục (Seed data) vào PostgreSQL!")

if __name__ == "__main__":
    seed_data()