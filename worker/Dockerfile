FROM python:3.12-slim AS builder 
WORKDIR /app
COPY requirements.txt .
RUN pip install --user -r requirements.txt

FROM python:3.12-slim 
WORKDIR /app

# Patch known-vulnerable OS packages ahead of the base image's own rebuild cadence
RUN apt-get update && apt-get upgrade -y libssl3t64 openssl && rm -rf /var/lib/apt/lists/*

RUN addgroup --system app && adduser --system --ingroup app --home /home/app app
ENV HOME=/home/app

COPY --from=builder --chown=app:app /root/.local /home/app/.local
ENV PATH=/home/app/.local/bin:$PATH
COPY --chown=app:app main.py .

USER app

CMD ["python", "main.py"]
