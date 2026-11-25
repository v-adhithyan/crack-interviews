FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jdk-headless time \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
USER 65534:65534
