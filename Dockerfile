FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UPI_APP_FACTORY_HOST=0.0.0.0 \
    UPI_APP_FACTORY_PORT=8036 \
    UPI_APP_FACTORY_STATE_ROOT=/app/.var/operator_portal \
    UPI_APP_FACTORY_LOG_LEVEL=INFO \
    FACTORY_LLM_ENABLED=0 \
    UPI_APP_FACTORY_LLM_ENABLED=0 \
    REAL_PAYMENT_CALLS=disabled \
    UPI_APP_FACTORY_REAL_PAYMENT_CALLS=disabled \
    MOCK_BOUNDARY=1

WORKDIR /app

RUN groupadd --system --gid 1000 appfactory \
    && useradd --system --uid 1000 --gid appfactory --home-dir /app --shell /usr/sbin/nologin appfactory \
    && mkdir -p /app/.var/operator_portal /app/.cache \
    && chown -R appfactory:appfactory /app

COPY --chown=appfactory:appfactory requirements-recipient.txt pyproject.toml ./
COPY --chown=appfactory:appfactory requirements/bootstrap-lock.txt requirements/recipient-lock.txt ./requirements/

COPY --chown=appfactory:appfactory app ./app
COPY --chown=appfactory:appfactory adapters ./adapters
COPY --chown=appfactory:appfactory factory ./factory
COPY --chown=appfactory:appfactory src ./src
RUN python -m pip install --no-cache-dir -r requirements/bootstrap-lock.txt \
    && python -m pip install --no-cache-dir -r requirements-recipient.txt

COPY --chown=appfactory:appfactory tools ./tools
COPY --chown=appfactory:appfactory scripts ./scripts
COPY --chown=appfactory:appfactory config ./config
COPY --chown=appfactory:appfactory docs/handover/ENVIRONMENT_SPEC.md ./docs/handover/ENVIRONMENT_SPEC.md
COPY --chown=appfactory:appfactory README.md ./

USER appfactory
VOLUME ["/app/.var"]
EXPOSE 8036

HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=12 \
    CMD python -c "import os, urllib.request; port=os.environ.get('UPI_APP_FACTORY_PORT','8036'); urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=2).read()"

CMD ["python", "scripts/run_docker_factory_portal.py"]
