from __future__ import annotations

import json
import logging
import os

_configured = False


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "service": os.getenv("SERVICE_NAME", "api"),
        }
        for key in ("replication_id", "claim_id", "attempt_id", "event_id", "trace_id"):
            value = getattr(record, key, None)
            if value:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


def configure_telemetry() -> None:
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    if os.getenv("K_SERVICE"):
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            provider = TracerProvider(
                resource=Resource.create(
                    {"service.name": os.getenv("SERVICE_NAME", "replicator-api")}
                )
            )
            provider.add_span_processor(BatchSpanProcessor(CloudTraceSpanExporter()))
            trace.set_tracer_provider(provider)
        except ModuleNotFoundError:
            logging.getLogger(__name__).warning("Cloud Trace exporter unavailable")
    _configured = True
