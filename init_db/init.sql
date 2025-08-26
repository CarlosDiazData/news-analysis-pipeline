-- news_articles: Main table for storing news articles
CREATE TABLE IF NOT EXISTS news_articles (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    url VARCHAR(500) UNIQUE NOT NULL,      -- UNIQUE constraint to prevent duplicates
    image_url VARCHAR(500),
    published_at TIMESTAMP NOT NULL,
    source_name VARCHAR(255) NOT NULL,
    author VARCHAR(255),
    content TEXT,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Record when the article was ingested

    -- COLUMNS FOR ML ENRICHMENT
    sentiment_polarity FLOAT,
    sentiment_subjectivity FLOAT,
    named_entities JSONB
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_source_name ON news_articles (source_name);
CREATE INDEX IF NOT EXISTS idx_published_at ON news_articles (published_at);

-- View for recent news
CREATE OR REPLACE VIEW recent_news AS
SELECT 
    id,
    title,
    description,
    url,
    published_at,
    source_name,
    sentiment_polarity
FROM 
    news_articles
WHERE 
    published_at >= (CURRENT_DATE - INTERVAL '7 days')
ORDER BY 
    published_at DESC;

-- Database documentation
COMMENT ON TABLE news_articles IS 'Stores news articles extracted from NewsAPI and enriched with scraping and ML analysis';
COMMENT ON COLUMN news_articles.title IS 'Article title';
COMMENT ON COLUMN news_articles.description IS 'Article description/summary';
COMMENT ON COLUMN news_articles.url IS 'Article URL (unique identifier)';
COMMENT ON COLUMN news_articles.image_url IS 'URL of the article featured image';
COMMENT ON COLUMN news_articles.published_at IS 'Article publication date';
COMMENT ON COLUMN news_articles.source_name IS 'Name of the news source';
COMMENT ON COLUMN news_articles.author IS 'Article author';
COMMENT ON COLUMN news_articles.content IS 'Full article content, enriched by scraping';
COMMENT ON COLUMN news_articles.ingested_at IS 'Timestamp when the article was added to the database';
COMMENT ON COLUMN news_articles.sentiment_polarity IS 'Sentiment polarity score (-1=negative, 1=positive)';
COMMENT ON COLUMN news_articles.sentiment_subjectivity IS 'Sentiment subjectivity score (0=objective, 1=subjective)';
COMMENT ON COLUMN news_articles.named_entities IS 'JSON array of named entities found in the article content (e.g., persons, organizations)';
COMMENT ON VIEW recent_news IS 'Shows news articles published in the last 7 days';