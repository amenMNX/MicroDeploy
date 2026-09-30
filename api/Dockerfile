FROM python:3.12-slim AS builder 
WORKDIR /app
COPY requirements.txt .
RUN pip install --user -r requirements.txt 

FROM python:3.12-slim
WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY --from=builder --chown=app:app /root/.local /home/app/.local
ENV PATH=/home/app/.local/bin:$PATH
COPY --chown=app:app main.py .
EXPOSE 8080

USER app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
