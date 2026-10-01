from pydantic import BaseModel
from typing import Optional

# Dữ liệu nhà tuyển dụng gửi lên
class NhaTuyenDungCreate(BaseModel):
    user_id: int  # Tạm thời truyền ID trực tiếp để dễ test
    ten_cong_ty: str
    loai_hinh: Optional[str] = None
    quy_mo: Optional[str] = None
    dia_chi: Optional[str] = None
    website: Optional[str] = None
    mo_ta: Optional[str] = None

# Dữ liệu Backend trả về
class NhaTuyenDungResponse(BaseModel):
    company_id: int
    user_id: int
    ten_cong_ty: str
    trang_thai_duyet: str

    class Config:
        from_attributes = True