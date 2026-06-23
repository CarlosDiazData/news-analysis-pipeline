"""
Deadline alert callback — writes structured JSON lines to a mounted log volume.

Airflow 3.x+ invokes this function when a DeadlineAlert fires. Each miss is
serialized as one JSON line and appended to the SLA miss log file.
"""

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SLA_MISS_LOG = "/opt/airflow/logs/sla_misses.log"


def on_sla_miss(**context) -> None:
    """Airflow 3.x DeadlineAlert callback — logs one JSON line per miss.

    Called by SyncCallback when a DeadlineAlert fires. Receives the
    standard Airflow context as kwargs.

    The ``deadline`` key in context contains the DeadlineAlert metadata.
    """
    now_utc = datetime.now(timezone.utc)

    dag_id = context.get("dag", "unknown")
    task_id = context.get("task", "unknown")
    logical_date = context.get("logical_date", now_utc)

    # The deadline interval is defined on the DAG's DeadlineAlert
    # We compute exceeded_by from logical_date + 9h (our configured deadline)
    from datetime import timedelta

    deadline_interval = timedelta(hours=9)
    sla_exceeded_by = int(
        (now_utc - (logical_date + deadline_interval)).total_seconds()
    )

    record = {
        "timestamp": now_utc.isoformat(),
        "dag_id": str(dag_id),
        "task_id": str(task_id),
        "scheduled_time": logical_date.isoformat() if hasattr(logical_date, "isoformat") else str(logical_date),
        "sla_exceeded_by": sla_exceeded_by,
    }

    with open(SLA_MISS_LOG, "a") as fh:
        fh.write(json.dumps(record) + "\n")

    logger.warning(
        "Deadline miss: dag=%s task=%s exceeded_by=%ds",
        dag_id,
        task_id,
        sla_exceeded_by,
    )
