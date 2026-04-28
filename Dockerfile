FROM node:20-alpine AS frontend-builder

WORKDIR /build/frontend

# 先拷贝依赖清单以利用 Docker 层缓存
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund --loglevel=error

# 构建前端静态资源到 app/static
COPY frontend/ ./
RUN npm run build


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

# 复制后端代码
COPY app/ /app/app/

# 复制前端构建产物（由 vite 输出到 ../app/static）
COPY --from=frontend-builder /build/app/static /app/app/static

EXPOSE 8000

# 生产启动：不使用 --reload
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

