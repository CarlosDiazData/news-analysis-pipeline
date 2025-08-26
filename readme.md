# End-to-End News Analysis ETL Pipeline with ML and Power BI

[![alt text](https://img.shields.io/badge/License-MIT-yellow.svg)](https://www.google.com/url?sa=E&q=https%3A%2F%2Fopensource.org%2Flicenses%2FMIT)

This project implements a complete, automated ETL pipeline that extracts news articles from the NewsAPI, enriches them with full-text content via web scraping, performs Natural Language Processing (NLP) to extract sentiment and named entities, and loads the structured data into a PostgreSQL database. The entire workflow is orchestrated with Apache Airflow and containerized with Docker.

The final output is a dynamic, interactive Power BI dashboard for visualizing news trends, media sentiment, and key topics.

## Key Features

-   **Automated Daily Ingestion**: Fetches the latest top headlines from the USA every day using a scheduled Airflow DAG.
    
-   **Web Scraping Enrichment**: Follows article URLs to scrape the full text, overcoming the content limitations of the API.
    
-   **Machine Learning Analysis**:
    
    -   **Sentiment Analysis**: Determines if the tone of each article is positive, negative, or neutral.
        
    -   **Named Entity Recognition (NER)**: Identifies key entities like persons, organizations, and locations within the text.
        
-   **Robust Data Storage**: Persists all enriched data in a PostgreSQL database with a well-defined schema.
    
-   **Containerized & Reproducible**: The entire environment (Airflow, Postgres, pgAdmin) is managed with Docker Compose for easy setup and consistency.
    
-   **Interactive Visualization**: Includes a comprehensive Power BI dashboard for data exploration and insight discovery.
    

## Architecture Diagram

The data flows through the system as follows:

![](https://raw.githubusercontent.com/CarlosDiazData/news-analysis-pipeline/refs/heads/main/Docs/Graph.png)

## Tech Stack

-   **Orchestration**: Apache Airflow
    
-   **Containerization**: Docker & Docker Compose
    
-   **Database**: PostgreSQL
    
-   **Data Extraction**: Python, Requests
    
-   **Web Scraping**: Python, BeautifulSoup4
    
-   **NLP/ML**: Python, spaCy, TextBlob
    
-   **Visualization**: Power BI
    

## Project Structure


```
. 
├── dags/ 
│ └── news_etl_dag.py # The main Airflow DAG file with all ETL logic. 
├── init_db/ 
│ └── init.sql # SQL script to initialize the database schema and tables. 
├── .env.example # Example environment variables file. 
├── docker-compose.yml # Defines and configures all services. 
├── Dockerfile # Custom Airflow image with dependencies. 
├── requirements.txt # Python package dependencies. 
└── README.md
```

## Setup and Installation

### Prerequisites

-   [Docker](https://www.google.com/url?sa=E&q=https%3A%2F%2Fwww.docker.com%2Fproducts%2Fdocker-desktop%2F) and Docker Compose
    
-   Git
    
-   A [NewsAPI](https://www.google.com/url?sa=E&q=https%3A%2F%2Fnewsapi.org%2F) key
    

### 1. Clone the Repository


```
git clone https://github.com/CarlosDiazData/news-analysis-pipeline.git
cd news-analysis-pipeline
```


### 2. Configure Environment Variables

Create a .env file by copying the example. This file will store your secret keys and is ignored by Git.

```
cp .env.example .env
```

Now, open the .env file and fill in the values. It should look like this:

```
# .env
NEWS_API_KEY="YOUR_API_KEY_HERE"
AIRFLOW_FERNET_KEY="YOUR_GENERATED_FERNET_KEY_HERE"
```

#### AIRFLOW_FERNET_KEY

This is a secret key that Airflow uses to encrypt sensitive data like connection passwords and variables in its database. **You must generate one.**

Run the following command in your local terminal to generate a valid key:

codeBash

```
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Copy the long string of characters** that the command prints (it will look something like k1_I-s0d_...=) and paste it as the value for AIRFLOW_FERNET_KEY.

### 3. Build and Run the Services

Start the entire environment using Docker Compose. This will build your custom Airflow image, pull the Postgres and pgAdmin images, and start all containers in the background.

```
docker-compose up --build -d
```

### 4. Access the Services

-   **Airflow Web UI**: [http://localhost:8080](https://www.google.com/url?sa=E&q=http%3A%2F%2Flocalhost%3A8080)
    
    -   Login with username airflow and password airflow.
        
-   **pgAdmin (Database UI)**: [http://localhost:5050](https://www.google.com/url?sa=E&q=http%3A%2F%2Flocalhost%3A5050)
    
    -   Login with username admin@example.com and password admin.
        

## Usage

1.  Navigate to the Airflow UI at http://localhost:8080.
    
2.  You will see the DAG named ingestion_newsapi_postgres_with_scraping. By default, it is paused.
    
3.  Un-pause the DAG by clicking the toggle switch.
    
4.  The DAG is scheduled to run daily. To run it immediately, click the "Play" button on the right to trigger a manual run.
    
5.  You can monitor the progress of each task (extract, scrape, analyze, load) in the Grid View.
    

## The Power BI Dashboard

The final goal of this pipeline is to fuel an interactive dashboard for analyzing news data.

### Connecting Power BI to the Database

You can connect Power BI Desktop directly to the PostgreSQL database running in Docker.

1.  **Expose Port**: Ensure your docker-compose.yml has the port mapping ports: - "5432:5432" for the postgres service.
    
2.  **Get Data**: In Power BI, select Get Data -> PostgreSQL database.
    
3.  **Enter Connection Details**:
    
    -   **Server**: localhost
        
    -   **Database**: airflow_db
        
    -   **User Name**: airflow
        
    -   **Password**: airflow 
        
4.  **Load Data**: Select the news_articles table and load it into your report.
    

### Dashboard Layout

The dashboard is designed on a single page to provide a comprehensive, at-a-glance overview and allow for powerful cross-filtering.

![](https://raw.githubusercontent.com/CarlosDiazData/news-analysis-pipeline/refs/heads/main/Docs/Dashboard.png)

  

The dashboard includes:

-   **KPI Cards**: High-level metrics like total articles, average sentiment, and top mentioned organizations.
    
-   **Sentiment Over Time**: A line chart showing the daily trend of media sentiment.
    
-   **Sentiment by Source**: A bar chart comparing the average sentiment of different news outlets.
    
-   **Interactive Article Table**: A detailed table of articles that filters dynamically based on selections in other visuals.