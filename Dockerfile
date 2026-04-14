FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# System dependencies required to build some Python packages (dedupe, scikit-learn, etc.)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       gfortran \
       libopenblas-dev \
       liblapack-dev \
       libffi-dev \
       git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first so layer can be cached
COPY requirements.txt ./
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Add the entrypoint and ensure it's executable
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8501

# Use entrypoint to prepare directories and run the app
ENTRYPOINT ["/app/entrypoint.sh"]
