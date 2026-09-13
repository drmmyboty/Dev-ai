FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8080 DEV_AI_SECURE_COOKIES=1
CMD ["sh","-c","gunicorn --bind 0.0.0.0:$PORT app:app"]
