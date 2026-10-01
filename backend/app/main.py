from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.models import user, nha_tuyen_dung, danh_muc, tin_tuyen_dung
from app.routers import auth, nha_tuyen_dung as router_nha_tuyen_dung, tin_tuyen_dung as router_tin_tuyen_dung 

Base.metadata.create_all(bind=engine)

app = FastAPI(title="IT Jobs Platform API")

# Cấu hình CORS cho phép Frontend gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cho phép mọi nguồn truy cập (hoặc điền cụ thể "http://localhost:5173")
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(router_nha_tuyen_dung.router)
app.include_router(router_tin_tuyen_dung.router)

@app.get("/")
def read_root():
    return {"message": "Hệ thống Backend đã chạy và sẵn sàng kết nối DB!"}