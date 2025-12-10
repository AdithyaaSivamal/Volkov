# 1. Base Image (Official Python)
FROM python:3.11-slim-bookworm

# 2. System Dependencies (Rclone + Security tools)
RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    smbclient \
    && rm -rf /var/lib/apt/lists/*

# 3. Install Rclone (The Official Script)
RUN curl https://rclone.org/install.sh | bash

# 4. Set Work Directory
WORKDIR /app

# 5. Install Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy Application Code
COPY scraper.py .
COPY onion_lib.py .
COPY vetter.py .
COPY rss_lib.py .
COPY c2_lib.py .

# 7. Create Non-Root User (OpSec Best Practice)
RUN useradd -m volkov_op
RUN chown -R volkov_op:volkov_op /app
USER volkov_op

# 8. Command
# We use 'python -u' to force unbuffered stdout so logs show up immediately
CMD ["python", "-u", "scraper.py"]
