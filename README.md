# Wikipedia Scraper

A Python script that scrapes Wikipedia articles and saves the data to CSV files or SQLite database.

## Features
- Collect 20+ articles from Wikipedia
- Search for specific terms
- Crawl related articles
- Collect featured articles from main page
- Collect random articles
- Save data to CSV or SQLite

## Requirements
- Python 3.7+
- Selenium
- Chrome/Chromium browser
- ChromeDriver

## Usage
```bash
# Default mode - at least 20 articles
python wiki_scraper.py

# Crawl mode - 25 articles with depth 2
python wiki_scraper.py --crawl

# Random articles only
python wiki_scraper.py --random --max_articles 20
