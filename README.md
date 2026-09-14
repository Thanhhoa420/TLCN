## Cách chạy

1. Mở terminal tại thư mục `TLCN/`
2. Chạy lệnh:
   ```
   docker compose up -d
   ```
3. Kiểm tra 2 container đã chạy:
   ```
   docker ps
   ```
   Sẽ thấy `tlcn_oltp_db` và `tlcn_dwh_db` đang chạy (status "Up").

4. Các file SQL trong `oltp-init/` và `dwh-init/` sẽ **tự động chạy 1 lần duy nhất**
   khi container được tạo lần đầu (nhờ cơ chế `docker-entrypoint-initdb.d` của
   image Postgres chính thức). Nếu muốn chạy lại từ đầu (xóa hết dữ liệu cũ),
   xem phần "Reset dữ liệu" bên dưới.

## Thông tin kết nối

| | OLTP DB | DWH DB |
|---|---|---|
| Host | localhost | localhost |
| Port | 5432 | 5433 |
| Database | oltp_db | dwh_db |
| User | oltp_user | dwh_user |
| Password | oltp_pass | dwh_pass |

Dùng thông tin này để kết nối bằng DBeaver/pgAdmin, hoặc từ code Python
(SQLAlchemy/psycopg2), hoặc từ Airflow/Superset sau này.

Connection string mẫu:
```
postgresql://oltp_user:oltp_pass@localhost:5432/oltp_db
postgresql://dwh_user:dwh_pass@localhost:5433/dwh_db
```

> Lưu ý: 2 container dùng chung network `tlcn_network` — nếu sau này chạy
> Airflow/backend cũng trong Docker (cùng network này), phải dùng tên
> service (`oltp_db`, `dwh_db`) thay vì `localhost` để kết nối.

## Các lệnh thường dùng

```bash
# Xem log của 1 container (debug khi lỗi)
docker logs tlcn_oltp_db
docker logs tlcn_dwh_db

# Vào thẳng psql trong container để gõ lệnh SQL kiểm tra
docker exec -it tlcn_oltp_db psql -U oltp_user -d oltp_db
docker exec -it tlcn_dwh_db psql -U dwh_user -d dwh_db

# Trong psql, gõ \dt để xem danh sách bảng đã tạo, \q để thoát

# Dừng container (giữ nguyên dữ liệu)
docker compose stop

# Chạy lại sau khi đã stop
docker compose start
```

## Reset dữ liệu (xóa sạch, chạy lại DDL từ đầu)

File SQL trong `*-init/` chỉ chạy khi **volume dữ liệu chưa tồn tại**. Nếu bạn
sửa file DDL và muốn nó chạy lại, phải xóa luôn volume:

```bash
docker compose down -v
docker compose up -d
```

⚠️ Lệnh này xóa **toàn bộ dữ liệu** đã insert trong cả 2 database — chỉ dùng khi
muốn làm lại từ đầu.

## Bước tiếp theo
1. Kiểm tra 2 database đã lên đủ bảng (`\dt` trong psql, hoặc mở bằng DBeaver).
2. Insert seed data cho 7 bảng danh mục + `ky_nang` bên OLTP.
3. Viết backend FastAPI kết nối tới `oltp_db`.
4. Viết crawler thu thập seed data từ TopCV/VietnamWorks/ITviec.
5. Viết pipeline ETL (Airflow) đồng bộ từ `oltp_db` sang `dwh_db`.