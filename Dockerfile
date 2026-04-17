FROM python:3.11-slim

WORKDIR /app

# Upgrade pip and install curl
RUN apt-get update && apt-get install -y --no-install-recommends curl gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose Streamlit port
EXPOSE 8501

CMD ["streamlit", "run", "src/main.py"]
