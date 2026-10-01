from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.user import User
from app.schemas.user_schema import UserCreate, UserResponse
from app.schemas.user_schema import UserCreate, UserResponse, UserLogin

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Hàm mở kết nối DB cho mỗi request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/register", response_model=UserResponse)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    # 1. Kiểm tra email đã tồn tại chưa
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email đã được đăng ký")
    
    # 2. Tạo user mới (Tạm thời lưu mật khẩu gốc, sau này sẽ thêm hàm hash)
    new_user = User(
        email=user.email,
        password_hash=user.password, 
        role=user.role,
        full_name=user.full_name
    )
    
    # 3. Lưu vào DB
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user

@router.post("/login")
def login_user(user: UserLogin, db: Session = Depends(get_db)):
    # 1. Tìm user theo email trong database
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Email không tồn tại")

    # 2. Kiểm tra mật khẩu (hiện tại so sánh chuỗi thô, sau này có thể nâng cấp băm mật khẩu)
    if db_user.password_hash != user.password:
        raise HTTPException(status_code=401, detail="Mật khẩu không chính xác")

    # 3. Trả về thông tin nếu đăng nhập thành công
    return {
        "message": "Đăng nhập thành công",
        "user_info": {
            "email": db_user.email,
            "role": db_user.role,
            "full_name": db_user.full_name
        }
    }