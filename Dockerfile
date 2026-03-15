FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py messages.py advertisement_repository.py ./

RUN mkdir -p /app/logs

CMD ["python3", "main.py"]
