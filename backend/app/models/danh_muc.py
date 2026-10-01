from sqlalchemy import Column, Integer, String
from app.database import Base

class DanhMucChuyenMon(Base):
    __tablename__ = "danh_muc_chuyen_mon_it"
    chuyen_mon_id = Column(Integer, primary_key=True, index=True)
    ten_chuyen_mon = Column(String, unique=True)

class DanhMucDiaDiem(Base):
    __tablename__ = "danh_muc_dia_diem"
    dia_diem_id = Column(Integer, primary_key=True, index=True)
    ten_tinh_thanh = Column(String, unique=True)
    khu_vuc = Column(String)

class DanhMucKinhNghiem(Base):
    __tablename__ = "danh_muc_kinh_nghiem"
    kinh_nghiem_id = Column(Integer, primary_key=True, index=True)
    mo_ta = Column(String)
    so_nam_min = Column(Integer)
    so_nam_max = Column(Integer, nullable=True)

class DanhMucHocVan(Base):
    __tablename__ = "danh_muc_hoc_van"
    hoc_van_id = Column(Integer, primary_key=True, index=True)
    trinh_do = Column(String)

class DanhMucHinhThuc(Base):
    __tablename__ = "danh_muc_hinh_thuc_lam_viec"
    hinh_thuc_id = Column(Integer, primary_key=True, index=True)
    ten_hinh_thuc = Column(String)

class DanhMucTrangThai(Base):
    __tablename__ = "danh_muc_trang_thai_tin"
    trang_thai_id = Column(Integer, primary_key=True, index=True)
    ten_trang_thai = Column(String)