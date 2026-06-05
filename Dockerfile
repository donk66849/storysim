# 备选:容器化部署。注意单 worker(会话在进程内存)。
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# LLM_* 与 STORYSIM_* 通过 -e 或 --env-file 注入
CMD ["python", "-m", "uvicorn", "web.server:app", "--host", "0.0.0.0", "--port", "8000"]
