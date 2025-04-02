from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import pandas as pd
import time
import os
import logging
import datetime
import argparse
import sqlite3
import random

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("wiki_scraper.log"),
        logging.StreamHandler()
    ]
)

class WikipediaScraper:
    def __init__(self, base_url="https://en.wikipedia.org/wiki/Main_Page", headless=False, db_store=False, search_term=None):
        """Initialize the Wikipedia scraper with configuration options."""
        self.base_url = base_url
        self.headless = headless
        self.db_store = db_store
        self.search_term = search_term
        self.articles_data = []
        self.setup_driver()
        
        # Setup database if needed
        if self.db_store:
            self.setup_database()
    
    def setup_driver(self):
        """Configure and initialize the Chrome WebDriver."""
        options = Options()
        if self.headless:
            options.add_argument("--headless")
        
        # Add user agent to appear more like a regular browser
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36 Edg/93.0.961.52"
        ]
        options.add_argument(f"user-agent={random.choice(user_agents)}")
        
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        # Use the Service class for newer selenium versions
        service = Service()
        self.driver = webdriver.Chrome(service=service, options=options)
        
        # Wait time for elements
        self.wait = WebDriverWait(self.driver, 10)
        logging.info("WebDriver initialized successfully")
    
    def setup_database(self):
        """Set up SQLite database for storing Wikipedia article data."""
        self.conn = sqlite3.connect('wikipedia_data.db')
        self.cursor = self.conn.cursor()
        
        # Create table if it doesn't exist
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT,
            summary TEXT,
            categories TEXT,
            image_url TEXT,
            date_scraped TEXT
        )
        ''')
        self.conn.commit()
        logging.info("Database initialized successfully")
    
    def navigate_to_url(self, url=None):
        """Navigate to the target URL."""
        target_url = url if url else self.base_url
        try:
            self.driver.get(target_url)
            time.sleep(2)  # Short wait for page to load
            logging.info(f"Navigated to {target_url}")
            return True
        except Exception as e:
            logging.error(f"Failed to navigate to {target_url}: {str(e)}")
            return False
    
    def search_wikipedia(self, search_term=None):
        """Search Wikipedia for a specific term."""
        term = search_term if search_term else self.search_term
        if not term:
            logging.warning("No search term provided")
            return False
        
        try:
            # Navigate to Wikipedia main page if not already there
            if "wikipedia.org" not in self.driver.current_url:
                self.navigate_to_url()
            
            # Find the search box and enter the search term
            search_box = self.wait.until(
                EC.presence_of_element_located((By.ID, "searchInput"))
            )
            search_box.clear()
            search_box.send_keys(term)
            
            # Submit the search form
            search_button = self.driver.find_element(By.ID, "searchButton")
            search_button.click()
            
            # Wait for search results or article page to load
            time.sleep(3)
            
            logging.info(f"Searched for term: {term}")
            return True
        except Exception as e:
            logging.error(f"Error searching Wikipedia: {str(e)}")
            return False
    
    def extract_article_data(self):
        """Extract data from a Wikipedia article page."""
        try:
            # Get article title
            title = self.wait.until(
                EC.presence_of_element_located((By.ID, "firstHeading"))
            ).text
            
            # Get article URL
            url = self.driver.current_url
            
            # Get article summary (first paragraph)
            try:
                summary = self.driver.find_element(By.CSS_SELECTOR, "#mw-content-text p:not(.mw-empty-elt)").text
            except NoSuchElementException:
                summary = "Summary not found"
            
            # Get categories
            try:
                category_elements = self.driver.find_elements(By.CSS_SELECTOR, "#mw-normal-catlinks ul li a")
                categories = [cat.text for cat in category_elements]
            except:
                categories = []
            
            # Get main image if available
            try:
                image_url = self.driver.find_element(By.CSS_SELECTOR, ".infobox img, .thumb img").get_attribute("src")
            except:
                image_url = ""
            
            # Store the extracted article data
            article_data = {
                'title': title,
                'url': url,
                'summary': summary,
                'categories': "|".join(categories),
                'image_url': image_url,
                'date_scraped': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            self.articles_data.append(article_data)
            logging.info(f"Extracted data from article: {title}")
            return article_data
        except Exception as e:
            logging.error(f"Error extracting article data: {str(e)}")
            return None
    
    def extract_links_from_article(self, max_links=20):
        """Extract links from a Wikipedia article."""
        links = []
        try:
            # Find all link elements in the article content
            link_elements = self.driver.find_elements(By.CSS_SELECTOR, "#mw-content-text a[href^='/wiki/']:not([href*=':'])") 
            
            # Filter out non-article links
            article_links = []
            for link in link_elements:
                href = link.get_attribute("href")
                # Skip special pages, categories, etc.
                if (href and 
                    "Special:" not in href and 
                    "Category:" not in href and 
                    "File:" not in href and 
                    "Help:" not in href and 
                    "Wikipedia:" not in href and 
                    "Talk:" not in href):
                    article_links.append({
                        'text': link.text,
                        'href': href
                    })
                    
                    # Stop once we have enough links
                    if len(article_links) >= max_links:
                        break
            
            return article_links
        except Exception as e:
            logging.error(f"Error extracting links from article: {str(e)}")
            return []
    
    def crawl_related_articles(self, depth=2, max_articles=25):
        """Crawl Wikipedia articles starting from current page."""
        if not self.driver.current_url.startswith("https://en.wikipedia.org/wiki/"):
            logging.warning("Not on a Wikipedia article page, can't crawl related articles")
            return False
        
        visited_urls = set()
        visited_urls.add(self.driver.current_url)
        
        # Extract data from the starting article
        start_article = self.extract_article_data()
        articles_crawled = 1
        
        # BFS crawling up to specified depth
        current_depth = 0
        queue = [(self.driver.current_url, 0)]  # (url, depth)
        
        while queue and articles_crawled < max_articles:
            if not queue:
                break
                
            current_url, url_depth = queue.pop(0)
            
            # Skip if we've already processed this URL
            if current_url in visited_urls:
                continue
            
            # Navigate to the article
            self.navigate_to_url(current_url)
            visited_urls.add(current_url)
            
            # Extract article data
            self.extract_article_data()
            articles_crawled += 1
            
            # Stop if we've reached max articles
            if articles_crawled >= max_articles:
                break
            
            # Get links from this article for next depth level
            if url_depth < depth:
                links = self.extract_links_from_article(max_links=10)
                for link in links:
                    if link['href'] not in visited_urls:
                        queue.append((link['href'], url_depth + 1))
        
        logging.info(f"Crawled {articles_crawled} articles to depth {depth}")
        return True
    
    def extract_featured_articles(self, count=20):
        """Extract featured articles from Wikipedia main page and follow some links."""
        try:
            # Navigate to main page
            self.navigate_to_url("https://en.wikipedia.org/wiki/Main_Page")
            
            # Find featured article
            featured_article = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#mp-tfa"))
            )
            
            # Extract title and URL
            title_element = featured_article.find_element(By.CSS_SELECTOR, "p > b > a")
            title = title_element.text
            url = title_element.get_attribute("href")
            
            # Extract summary
            summary = featured_article.find_element(By.CSS_SELECTOR, "p").text
            
            # Add featured article to data
            self.articles_data.append({
                'title': title,
                'url': url,
                'summary': summary,
                'categories': "Featured",
                'image_url': "",
                'date_scraped': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
            # Extract "In the news" articles
            news_items = self.driver.find_elements(By.CSS_SELECTOR, "#mp-itn ul li")
            for item in news_items[:5]:  # Get 5 news articles
                try:
                    link = item.find_element(By.TAG_NAME, "a")
                    news_title = link.text
                    news_url = link.get_attribute("href")
                    news_summary = item.text
                    
                    self.articles_data.append({
                        'title': news_title,
                        'url': news_url,
                        'summary': news_summary,
                        'categories': "In the news",
                        'image_url': "",
                        'date_scraped': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                except:
                    continue
            
            # Extract "Did you know" articles
            dyk_items = self.driver.find_elements(By.CSS_SELECTOR, "#mp-dyk ul li")
            for item in dyk_items[:5]:  # Get 5 DYK articles
                try:
                    link = item.find_element(By.TAG_NAME, "a")
                    dyk_title = link.text
                    dyk_url = link.get_attribute("href")
                    dyk_summary = item.text
                    
                    self.articles_data.append({
                        'title': dyk_title,
                        'url': dyk_url,
                        'summary': dyk_summary,
                        'categories': "Did you know",
                        'image_url': "",
                        'date_scraped': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                except:
                    continue
                    
            # Extract "On this day" articles
            otd_items = self.driver.find_elements(By.CSS_SELECTOR, "#mp-otd ul li")
            for item in otd_items[:5]:  # Get 5 OTD articles
                try:
                    link = item.find_element(By.TAG_NAME, "a")
                    otd_title = link.text
                    otd_url = link.get_attribute("href")
                    otd_summary = item.text
                    
                    self.articles_data.append({
                        'title': otd_title,
                        'url': otd_url,
                        'summary': otd_summary,
                        'categories': "On this day",
                        'image_url': "",
                        'date_scraped': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                except:
                    continue
            
            # If we still need more articles, navigate to Today's Featured Article archive
            if len(self.articles_data) < count:
                self.navigate_to_url("https://en.wikipedia.org/wiki/Wikipedia:Today%27s_featured_article/Archives")
                archive_links = self.driver.find_elements(By.CSS_SELECTOR, "#mw-content-text ul li a")[:10]
                
                for link in archive_links:
                    if len(self.articles_data) >= count:
                        break
                        
                    try:
                        archive_title = link.text
                        archive_url = link.get_attribute("href")
                        
                        self.articles_data.append({
                            'title': archive_title,
                            'url': archive_url,
                            'summary': f"Featured article archive: {archive_title}",
                            'categories': "Featured archive",
                            'image_url': "",
                            'date_scraped': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                    except:
                        continue
                
            logging.info(f"Extracted {len(self.articles_data)} featured and main page articles")
            return True
        except Exception as e:
            logging.error(f"Error extracting featured articles: {str(e)}")
            return False
            
    def collect_random_articles(self, count=20):
        """Collect random articles from Wikipedia."""
        try:
            articles_collected = 0
            
            while articles_collected < count:
                # Navigate to random article
                self.navigate_to_url("https://en.wikipedia.org/wiki/Special:Random")
                
                # Extract data from the random article
                article_data = self.extract_article_data()
                if article_data:
                    articles_collected += 1
                
                time.sleep(1)  # Prevent too many requests
                
            logging.info(f"Collected {articles_collected} random articles")
            return True
        except Exception as e:
            logging.error(f"Error collecting random articles: {str(e)}")
            return False
    
    def save_to_csv(self):
        """Save extracted article data to a CSV file."""
        if not self.articles_data:
            logging.warning("No data to save to CSV")
            return False
        
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"wikipedia_articles_{timestamp}.csv"
            
            df = pd.DataFrame(self.articles_data)
            df.to_csv(filename, index=False)
            logging.info(f"Data saved to {filename}")
            return True
        except Exception as e:
            logging.error(f"Error saving to CSV: {str(e)}")
            return False
    
    def save_to_database(self):
        """Save extracted article data to SQLite database."""
        if not self.db_store or not self.articles_data:
            return False
        
        try:
            for article in self.articles_data:
                self.cursor.execute('''
                INSERT INTO articles (title, url, summary, categories, image_url, date_scraped)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    article['title'],
                    article['url'],
                    article['summary'],
                    article['categories'],
                    article['image_url'],
                    article['date_scraped']
                ))
            
            self.conn.commit()
            logging.info(f"Saved {len(self.articles_data)} articles to the database")
            return True
        except Exception as e:
            logging.error(f"Error saving to database: {str(e)}")
            return False
    
    def close(self):
        """Clean up resources."""
        if hasattr(self, 'driver'):
            self.driver.quit()
            logging.info("WebDriver closed")
        
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
            logging.info("Database connection closed")

def main():
    """Main function to run the scraper."""
    parser = argparse.ArgumentParser(description="Wikipedia scraping script")
    parser.add_argument("--search", type=str, help="Search term for Wikipedia article")
    parser.add_argument("--url", type=str, default="https://en.wikipedia.org/wiki/Main_Page",
                        help="URL to scrape (default: Wikipedia main page)")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--db", action="store_true", help="Store data in SQLite database")
    parser.add_argument("--featured", action="store_true", help="Scrape featured articles from main page")
    parser.add_argument("--crawl", action="store_true", help="Crawl related articles")
    parser.add_argument("--random", action="store_true", help="Collect random articles")
    parser.add_argument("--depth", type=int, default=2, help="Crawl depth (default: 2)")
    parser.add_argument("--max_articles", type=int, default=25, help="Maximum number of articles to scrape (default: 25)")
    
    args = parser.parse_args()
    
    # Initialize the scraper
    scraper = WikipediaScraper(
        base_url=args.url, 
        headless=args.headless, 
        db_store=args.db,
        search_term=args.search
    )
    
    try:
        # Navigate to the URL
        if not scraper.navigate_to_url():
            return
        
        # Search for a term if provided
        if args.search:
            if not scraper.search_wikipedia():
                return
            # After search, crawl related articles to get more
            scraper.crawl_related_articles(depth=args.depth, max_articles=args.max_articles)
        elif args.featured:
            # Extract featured articles from main page
            scraper.extract_featured_articles(count=args.max_articles)
        elif args.random:
            # Collect random articles
            scraper.collect_random_articles(count=args.max_articles)
        elif args.crawl:
            # Extract current article and crawl related ones
            scraper.crawl_related_articles(depth=args.depth, max_articles=args.max_articles)
        else:
            # Default: extract featured articles and some random ones to ensure we get enough
            scraper.extract_featured_articles(count=10)
            # If we didn't get enough articles, collect some random ones
            if len(scraper.articles_data) < 20:
                scraper.collect_random_articles(count=20 - len(scraper.articles_data))
        
        # Save the data
        scraper.save_to_csv()
        if args.db:
            scraper.save_to_database()
        
    finally:
        # Always close the scraper properly
        scraper.close()

if __name__ == "__main__":
    main()