# Dockerfile

FROM apache/airflow:2.7.1-python3.9

USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config && \
    apt-get clean && \
    rm -r /var/lib/apt/lists/*

# Switch to airflow user to install packages
USER airflow
COPY requirements.txt /opt/airflow/requirements.txt
RUN pip install --no-cache-dir -r /opt/airflow/requirements.txt

#Download the spaCy language model
RUN python -m spacy download en_core_web_sm

# Disable loading of example DAGs
ENV AIRFLOW__CORE__LOAD_EXAMPLES=False

USER root
RUN ls -ld /opt/airflow
RUN mkdir -p /opt/airflow/data
RUN chown -R airflow:root /opt/airflow/data

USER airflow