# 备选:容器化部署。注意单 worker(会话在进程内存)。
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# 非 root 运行:建普通用户并交出 /app 属主(运行时需写 runs/)
RUN useradd -m -u 10001 appuser && chown -R appuser /app
USER appuser
EXPOSE 8000
# LLM_* 与 STORYSIM_* 通过 -e 或 --env-file 注入
# --proxy-headers + --forwarded-allow-ips:容器内代理 IP 不固定,信任转发头才能拿到真实客户端 IP
CMD ["python", "-m", "uvicorn", "web.server:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
