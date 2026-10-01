import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Đọc file .env
load_dotenv()

# Lấy URL kết nối
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# Đảm bảo dòng khởi tạo engine này phải có mặt trong file
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Khởi tạo phiên làm việc (session) với DB
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class để các file Models kế thừa
Base = declarative_base()