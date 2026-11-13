FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install .

# The payment schema lives outside generator/, so compose passes it in as a second context.
COPY --from=schemas payment.avsc /app/schemas/payment.avsc
# Readable by everyone, writable by no one (Windows files arrive with every permission set).
RUN chmod 755 /app/schemas && chmod 444 /app/schemas/payment.avsc
ENV PAYMENT_SCHEMA_PATH=/app/schemas/payment.avsc

# Do not run as root inside the container.
RUN useradd --system --no-create-home appuser
USER appuser

ENTRYPOINT ["fraudpulse-gen"]
CMD ["run", "--sink", "kafka"]
