FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV FLASK_APP=run.py
EXPOSE 5000
CMD ["sh", "-c", "flask init-db && gunicorn --bind 0.0.0.0:5000 --workers 2 run:app"]
