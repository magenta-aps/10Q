FROM python:3.8
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
COPY ./src/tenQ /app
WORKDIR /app
CMD ["python", "-m", "unittest"]
