from pydantic import BaseModel
from typing import Optional
from datetime import date

# Dữ liệu nhà tuyển dụng gửi lên khi đăng tin
class TinTuyenDungCreate(BaseModel):
    company_id: int
    tieu_de: str
    mo_ta_cong_viec: Optional[str] = None
    yeu_cau: Optional[str] = None
    quyen_loi: Optional[str] = None
    
    # ID trỏ tới các bảng danh mục
    chuyen_mon_id: int
    dia_diem_id: int
    kinh_nghiem_id: int
    hoc_van_id: int
    hinh_thuc_id: int
    
    luong_min: Optional[int] = None
    luong_max: Optional[int] = None
    so_luong_tuyen: Optional[int] = 1
    han_ung_tuyen: Optional[date] = None

# Dữ liệu API trả về sau khi tạo thành công
class TinTuyenDungResponse(TinTuyenDungCreate):
    job_id: int
    trang_thai_id: int
    so_luot_xem: int

    class Config:
        from_attributes = True