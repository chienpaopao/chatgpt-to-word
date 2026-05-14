FROM python:3.11-slim

# Install pandoc
RUN apt-get update && \
    apt-get install -y --no-install-recommends pandoc && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8080
ENV PORT=8080

CMD gunicorn --bind 0.0.0.0:$PORT app:app
