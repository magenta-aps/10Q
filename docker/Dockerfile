FROM python:3.8
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY ./src /app
WORKDIR /app
CMD ["python", "-m", "unittest"]
