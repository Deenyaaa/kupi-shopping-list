FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SHOPPING_DB=/data/shopping.db

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py auth.py db.py manage.py ./
COPY static ./static

# /data создаём заранее и отдаём пользователю app: именованный том при первом создании унаследует эти права.
RUN useradd --system --uid 1000 app && mkdir /data && chown app /data
USER app
VOLUME /data

EXPOSE 8000
# Порт 8000 наружу не публикуется, до него дотягивается только Caddy из сети compose,
# поэтому X-Forwarded-For можно доверять от любого адреса: так ограничение входов видит настоящий IP.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--forwarded-allow-ips", "*"]
