FROM python:3.12-slim
WORKDIR /app
COPY app.py /app/app.py
USER 65532:65532
ENV HOST=0.0.0.0
EXPOSE 8000
CMD ["python", "app.py"]
