from sqlalchemy import Column, Integer, String, Text, ForeignKey, Enum
from app.database import Base
import enum

# Trạng thái duyệt hồ sơ công ty của Admin
class TrangThaiDuyet(str, enum.Enum):
    cho_duyet = "cho_duyet"
    da_duyet = "da_duyet"
    tu_choi = "tu_choi"

class NhaTuyenDung(Base):
    __tablename__ = "nha_tuyen_dung"

    company_id = Column(Integer, primary_key=True, index=True)
    # Khóa ngoại liên kết 1-1 với bảng users
    user_id = Column(Integer, ForeignKey("users.user_id"), unique=True) 
    
    ten_cong_ty = Column(String, nullable=False)
    logo_url = Column(String)
    loai_hinh = Column(String) # Ví dụ: Product, Outsourcing, Agency
    quy_mo = Column(String)
    dia_chi = Column(String)
    website = Column(String)
    mo_ta = Column(Text)
    trang_thai_duyet = Column(Enum(TrangThaiDuyet), default=TrangThaiDuyet.cho_duyet)