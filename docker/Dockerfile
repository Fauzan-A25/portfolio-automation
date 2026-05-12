FROM python:3.11-slim

WORKDIR /app

# Copy project
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Buat folder logs
RUN mkdir -p logs secrets

# Script utama
CMD ["python", "scripts/github_to_sheets.py"]
