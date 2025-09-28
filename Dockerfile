FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py .
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser
CMD ["python", "-u", "bot.py"]