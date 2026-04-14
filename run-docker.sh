#!/usr/bin/env sh
set -e

# Simple wrapper to build and run the app via Docker Compose.
# Run with: sh run-docker.sh

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed. Please install Docker: https://docs.docker.com/get-docker/"
  exit 1
fi

# Prefer the new docker compose plugin if available
if docker compose version >/dev/null 2>&1; then
  docker compose up --build
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose up --build
else
  echo "Neither 'docker compose' nor 'docker-compose' was found. Please install Docker Compose."
  exit 1
fi
