"""Minimal CloudWatch Embedded Metric Format (EMF) emitter.

Printing this JSON shape to stdout lets CloudWatch Logs extract custom
metrics automatically, with no extra dependency or API call.
"""

import json
import time


def emit_count(namespace: str, metric_name: str, dimensions: dict[str, str], value: int = 1) -> None:
    dimension_names = list(dimensions.keys())
    payload = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [{
                "Namespace": namespace,
                "Dimensions": [dimension_names],
                "Metrics": [{"Name": metric_name, "Unit": "Count"}],
            }],
        },
        metric_name: value,
        **dimensions,
    }
    print(json.dumps(payload))
