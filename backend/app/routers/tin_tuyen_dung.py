from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.tin_tuyen_dung import TinTuyenDung
from app.models.nha_tuyen_dung import NhaTuyenDung
from app.models.danh_muc import DanhMucDiaDiem
from app.schemas.tin_tuyen_dung_schema import TinTuyenDungCreate, TinTuyenDungResponse

router = APIRouter(prefix="/tin-tuyen-dung", tags=["Tin Tuyển Dụng"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 1. API Đăng tin tuyển dụng
@router.post("/dang-tin", response_model=TinTuyenDungResponse)
def create_job_post(job: TinTuyenDungCreate, db: Session = Depends(get_db)):
    new_job = TinTuyenDung(
        company_id=job.company_id,
        tieu_de=job.tieu_de,
        mo_ta_cong_viec=job.mo_ta_cong_viec,
        yeu_cau=job.yeu_cau,
        quyen_loi=job.quyen_loi,
        chuyen_mon_id=job.chuyen_mon_id,
        dia_diem_id=job.dia_diem_id,
        kinh_nghiem_id=job.kinh_nghiem_id,
        hoc_van_id=job.hoc_van_id,
        hinh_thuc_id=job.hinh_thuc_id,
        luong_min=job.luong_min,
        luong_max=job.luong_max,
        so_luong_tuyen=job.so_luong_tuyen,
        han_ung_tuyen=job.han_ung_tuyen,
        trang_thai_id=1 
    )
    
    try:
        db.add(new_job)
        db.commit()
        db.refresh(new_job)
        return new_job
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Lỗi tạo tin: {str(e)}")

# 2. API Lấy danh sách tin tuyển dụng cho Frontend
@router.get("/danh-sach")
def get_all_jobs(db: Session = Depends(get_db)):
    jobs = db.query(TinTuyenDung).all()
    
    result = []
    for job in jobs:
        company = db.query(NhaTuyenDung).filter(NhaTuyenDung.company_id == job.company_id).first()
        diadiem = db.query(DanhMucDiaDiem).filter(DanhMucDiaDiem.dia_diem_id == job.dia_diem_id).first()
        
        result.append({
            "id": job.job_id,
            "tieu_de": job.tieu_de,
            "mo_ta_cong_viec": job.mo_ta_cong_viec,
            "ten_cong_ty": company.ten_cong_ty if company else "Đang cập nhật",
            "dia_chi": diadiem.ten_tinh_thanh if diadiem else "Toàn quốc",
            "luong_min": job.luong_min,
            "luong_max": job.luong_max
        })
    return result

@router.get("/{job_id}")
def get_job_detail(job_id: int, db: Session = Depends(get_db)):
    job = db.query(TinTuyenDung).filter(TinTuyenDung.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy tin tuyển dụng")
    
    company = db.query(NhaTuyenDung).filter(NhaTuyenDung.company_id == job.company_id).first()
    diadiem = db.query(DanhMucDiaDiem).filter(DanhMucDiaDiem.dia_diem_id == job.dia_diem_id).first()
    
    return {
        "id": job.job_id,
        "tieu_de": job.tieu_de,
        "mo_ta_cong_viec": job.mo_ta_cong_viec,
        "yeu_cau": job.yeu_cau,
        "quyen_loi": job.quyen_loi,
        "ten_cong_ty": company.ten_cong_ty if company else "Đang cập nhật",
        "dia_chi": diadiem.ten_tinh_thanh if diadiem else "Toàn quốc",
        "luong_min": job.luong_min,
        "luong_max": job.luong_max,
        "so_luong_tuyen": job.so_luong_tuyen,
        "han_ung_tuyen": str(job.han_ung_tuyen) if job.han_ung_tuyen else "Không giới hạn"
    }
    return result