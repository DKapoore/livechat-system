FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p instance app/static/uploads

EXPOSE 5000

ENV FLASK_DEBUG=0
ENV PORT=5000

# Initialize the database on first run, then start the server
CMD ["sh", "-c", "python seed.py && python run.py"]
