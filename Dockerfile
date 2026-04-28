FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app
RUN pip install --upgrade pip && pip install -e ".[mcp]"

ENV PYTHONUNBUFFERED=1
ENV OPENPASTURE_STORE=sqlite
ENV OPENPASTURE_HOSTED_DATA_DIR=/data/openpasture
ENV OPENPASTURE_BRIEF_TIME=06:00
EXPOSE 8000
CMD ["openpasture-mcp-hosted"]
