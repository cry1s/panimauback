FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py .
COPY panimau_bot ./panimau_bot
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser
CMD ["python", "-u", "bot.py"]
