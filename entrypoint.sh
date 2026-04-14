#!/usr/bin/env sh
set -e

# If a .env file exists in mounted volume, load it for docker-compose
if [ -f .env ]; then
  set -a
  . .env
  set +a
fi

# Run the Streamlit app
exec streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
