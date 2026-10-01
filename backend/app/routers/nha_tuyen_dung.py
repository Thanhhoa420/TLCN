from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.nha_tuyen_dung import NhaTuyenDung
from app.schemas.nha_tuyen_dung_schema import NhaTuyenDungCreate, NhaTuyenDungResponse
from app.models.user import User

router = APIRouter(prefix="/nha-tuyen-dung", tags=["Nhà Tuyển Dụng"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/ho-so", response_model=NhaTuyenDungResponse)
def create_company_profile(profile: NhaTuyenDungCreate, db: Session = Depends(get_db)):
    # 1. Kiểm tra xem user này có tồn tại không
    user = db.query(User).filter(User.user_id == profile.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
    
    # 2. Đảm bảo mỗi user chỉ tạo 1 hồ sơ công ty
    existing_company = db.query(NhaTuyenDung).filter(NhaTuyenDung.user_id == profile.user_id).first()
    if existing_company:
        raise HTTPException(status_code=400, detail="Người dùng này đã tạo hồ sơ công ty rồi")

    # 3. Lưu vào DB
    new_company = NhaTuyenDung(
        user_id=profile.user_id,
        ten_cong_ty=profile.ten_cong_ty,
        loai_hinh=profile.loai_hinh,
        quy_mo=profile.quy_mo,
        dia_chi=profile.dia_chi,
        website=profile.website,
        mo_ta=profile.mo_ta
    )
    
    db.add(new_company)
    db.commit()
    db.refresh(new_company)
    
    return new_company