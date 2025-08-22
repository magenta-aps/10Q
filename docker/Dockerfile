# SPDX-FileCopyrightText: 2024 Magenta ApS <info@magenta.dk>
#
# SPDX-License-Identifier: MPL-2.0

FROM python:3.12
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY ./docker/entrypoint.sh /entrypoint.sh
COPY ./src /app
ENTRYPOINT ["/entrypoint.sh"]
WORKDIR /app
