FROM python:3.11-slim

WORKDIR /app

# 先装依赖，利用 Docker 层缓存
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY backend ./backend
COPY frontend ./frontend
COPY data ./data
COPY scripts ./scripts
COPY connections.example.json ./

EXPOSE 8000

# 数据目录用 volume 挂载后可持久化 SQLite 数据库
VOLUME ["/app/data"]

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
