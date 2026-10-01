from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Date
from sqlalchemy.sql import func
from app.database import Base

class TinTuyenDung(Base):
    __tablename__ = "tin_tuyen_dung"

    job_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("nha_tuyen_dung.company_id"))
    
    tieu_de = Column(String, nullable=False)
    mo_ta_cong_viec = Column(Text)
    yeu_cau = Column(Text)
    quyen_loi = Column(Text)
    
    # Các khóa ngoại liên kết tới bảng danh mục
    chuyen_mon_id = Column(Integer, ForeignKey("danh_muc_chuyen_mon_it.chuyen_mon_id"))
    dia_diem_id = Column(Integer, ForeignKey("danh_muc_dia_diem.dia_diem_id"))
    kinh_nghiem_id = Column(Integer, ForeignKey("danh_muc_kinh_nghiem.kinh_nghiem_id"))
    hoc_van_id = Column(Integer, ForeignKey("danh_muc_hoc_van.hoc_van_id"))
    hinh_thuc_id = Column(Integer, ForeignKey("danh_muc_hinh_thuc_lam_viec.hinh_thuc_id"))
    trang_thai_id = Column(Integer, ForeignKey("danh_muc_trang_thai_tin.trang_thai_id"))
    
    luong_min = Column(Integer)
    luong_max = Column(Integer, nullable=True) # null nếu thỏa thuận
    so_luong_tuyen = Column(Integer)
    so_luot_xem = Column(Integer, default=0) # Tự tăng khi xem, quan trọng cho DWH
    
    ngay_dang = Column(DateTime(timezone=True), server_default=func.now())
    han_ung_tuyen = Column(Date)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())