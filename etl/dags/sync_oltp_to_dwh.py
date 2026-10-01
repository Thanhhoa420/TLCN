"""
etl/dags/sync_oltp_to_dwh.py
============================
Airflow DAG thực hiện đồng bộ dữ liệu định kỳ từ OLTP (oltp_db) sang DWH (dwh_db).
Lịch chạy: Hàng ngày lúc 02:00 AM (UTC).
"""

from datetime import datetime, timedelta
import sys
import os
from airflow import DAG
from airflow.operators.python import PythonOperator

# Thêm đường dẫn gốc dự án vào PYTHONPATH để import module etl.scripts
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from etl.scripts.oltp_to_dwh import main as run_oltp_to_dwh

default_args = {
    "owner": "data_engineering_team",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="sync_oltp_to_dwh_dag",
    default_args=default_args,
    description="Chuyển dữ liệu từ oltp_db sang dwh_db (Star Schema)",
    schedule_interval="0 2 * * *",  # Chạy 02:00 AM mỗi ngày
    start_date=datetime(2026, 10, 1),
    catchup=False,
    tags=["etl", "dwh", "itviec"],
) as dag:

    task_sync_dwh = PythonOperator(
        task_id="run_sync_oltp_to_dwh",
        python_callable=run_oltp_to_dwh,
    )

    task_sync_dwh