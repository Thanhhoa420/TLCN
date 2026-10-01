from pydantic import BaseModel, EmailStr
from app.models.user import UserRole
from datetime import datetime

# Dữ liệu yêu cầu khi người dùng gửi API đăng ký
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: UserRole
    full_name: str

# Dữ liệu Backend trả về sau khi tạo thành công (ẩn password)
class UserResponse(BaseModel):
    user_id: int
    email: EmailStr
    role: UserRole
    full_name: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

    # Dữ liệu yêu cầu khi người dùng gửi API đăng nhập
class UserLogin(BaseModel):
    email: EmailStr
    password: str