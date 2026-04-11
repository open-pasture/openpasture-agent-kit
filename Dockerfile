FROM python:3.11-slim

WORKDIR /app
COPY . /app
RUN pip install --upgrade pip && pip install -e .

ENV OPENPASTURE_STORE=sqlite
CMD ["hermes"]
