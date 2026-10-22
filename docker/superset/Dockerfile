# Extend a specific Superset release.
FROM apache/superset:6.1.0

# Package installation requires elevated permissions inside the image.
USER root

COPY requirements.txt /tmp/superset-requirements.txt

# Install drivers into Superset's existing Python environment.
RUN uv pip install \
    --python /app/.venv/bin/python \
    -r /tmp/superset-requirements.txt


COPY --chown=superset:superset superset_config.py gold_connection.py /app/

ENV SUPERSET_CONFIG_PATH=/app/superset_config.py \
    PYTHONPATH=/app:/app/pythonpath

# Run the application as its existing non-root user.
USER superset