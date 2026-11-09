# Use a modern, actively supported Python base image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# 1. Inject stable network settings to stop packet drops and disable broken caches
RUN printf "Acquire::http::No-Cache \"true\";\nAcquire::http::Pipeline-Depth \"0\";\nAcquire::BrokenProxy \"true\";\n" > /etc/apt/apt.conf.d/99fix-network

# 2. Safely swap http for https without breaking the subdomains
RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's|http://debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources; \
    fi && \
    if [ -f /etc/apt/sources.list ]; then \
        sed -i 's|http://debian.org|https://deb.debian.org|g' /etc/apt/sources.list; \
    fi

# 3. Update and install packages securely
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*


# Copy the requirements file into the container
COPY requirements.txt .

# Upgrade pip and install application dependencies
# (Trusted host flags are kept to bypass corporate network/SSL blocks)
RUN pip install --no-cache-dir --upgrade pip --trusted-host pypi.org --trusted-host files.pythonhosted.org && \
    pip install --no-cache-dir \
        --trusted-host pypi.org \
        --trusted-host files.pythonhosted.org \
        -r requirements.txt

# Copy the rest of the application code into the container
COPY . .    

# Expose the port that the application will run on
EXPOSE 8000

# Set the command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
