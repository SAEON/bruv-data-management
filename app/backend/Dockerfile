# use Python 3.11 slim as the base image
FROM python:3.11-slim

# set the working directory in the container
WORKDIR /app

# copy the requirements file into the container
COPY requirements.txt .

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*
    
RUN pip install --upgrade pip

# install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# copy the rest of the application code into the container
COPY . .    

# expose the port that the application will run on
EXPOSE 8000

# set the command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]