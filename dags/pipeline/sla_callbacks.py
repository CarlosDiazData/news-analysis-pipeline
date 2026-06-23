"""
SLA miss callback — writes structured JSON lines to a mounted log volume.

Airflow invokes this function when an SLA is missed. Each miss is serialized
as one JSON line and appended to the SLA miss log file.
"""

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SLA_MISS_LOG = "/opt/airflow/logs/sla_misses.log"


def on_sla_miss(dag, task_list, blocking_task_list, slas, blocking_tis) -> None:
    """Airflow 3.x SLA miss callback — logs one JSON line per miss.

    The ``sla_exceeded_by`` field is computed here because Airflow's
    ``SLAMiss`` model does not expose it directly.

    Args:
        dag: The DAG instance.
        task_list: List of tasks that missed the SLA.
        blocking_task_list: Tasks blocking the SLA miss resolution.
        slas: List of ``SLAMiss`` namedtuples (dag_id, task_id, logical_date).
        blocking_tis: Blocking TaskInstance objects.
    """
    now_utc = datetime.now(timezone.utc)

    for miss in slas:
        task = dag.get_task(miss.task_id)
        sla_timedelta = task.sla

        # Compute seconds the SLA was exceeded
        # Airflow 3.x renamed execution_date → logical_date
        sla_exceeded_by = int(
            (now_utc - (miss.logical_date + sla_timedelta)).total_seconds()
        )

        record = {
            "timestamp": now_utc.isoformat(),
            "dag_id": miss.dag_id,
            "task_id": miss.task_id,
            "scheduled_time": miss.logical_date.isoformat(),
            "sla_exceeded_by": sla_exceeded_by,
        }

        with open(SLA_MISS_LOG, "a") as fh:
            fh.write(json.dumps(record) + "\n")

        logger.warning(
            "SLA miss: dag=%s task=%s exceeded_by=%ds",
            miss.dag_id,
            miss.task_id,
            sla_exceeded_by,
        )
