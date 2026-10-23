FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir 'fastapi>=0.115,<1' 'uvicorn>=0.30,<1'
COPY public_demo.py .
EXPOSE 8000
CMD ["uvicorn", "public_demo:app", "--host", "0.0.0.0", "--port", "8000"]
