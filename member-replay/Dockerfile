FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
ARG BUILD_ID=1.0
ENV BUILD_ID=${BUILD_ID} PYTHONUNBUFFERED=1
CMD ["python", "-m", "member_replay.worker"]
