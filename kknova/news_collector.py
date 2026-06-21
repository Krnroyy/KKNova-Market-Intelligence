import datetime
import logging
import requests
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional
from kknova.config import config
from kknova.logger import logger
from kknova.database import DatabaseManager
from kknova.sentiment_preprocessor import SentimentPreprocessor

class NewsCollector:
    """
    Scrapes and stores market and sectoral news articles.
    Gathers news from Moneycontrol RSS, Economic Times Markets RSS, and NewsAPI.
    """
    
    RSS_FEEDS = {
        "Moneycontrol": "https://www.moneycontrol.com/rss/latestnews.xml",
        "Economic Times": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"
    }

    KEYWORDS = [
        "Nifty", "Banking", "Defence", "PSU", "AI", "Data Center", 
        "Renewable Energy", "Infrastructure"
    ]

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager
        self.preprocessor = SentimentPreprocessor()

    def fetch_rss_feed(self, source_name: str, feed_url: str) -> List[Dict[str, str]]:
        """Parses RSS feeds and extracts article elements."""
        logger.debug(f"Fetching RSS feed from {source_name}...")
        try:
            # Set browser user-agent to bypass basic server blocking
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(feed_url, headers=headers, timeout=10.0)
            if response.status_code != 200:
                logger.warning(f"Failed to fetch RSS from {source_name}. Status: {response.status_code}")
                return []

            root = ET.fromstring(response.content)
            articles = []
            
            for item in root.findall(".//item"):
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                pub_date = item.findtext("pubDate", "").strip()
                
                # Element fallback checks
                if not title:
                    title = item.findtext("{http://www.w3.org/2005/Atom}title", "").strip()
                if not link:
                    link = item.findtext("{http://www.w3.org/2005/Atom}link", "").strip()
                if not pub_date:
                    pub_date = item.findtext("{http://purl.org/dc/elements/1.1/}date", "").strip()
                    
                if title and link:
                    articles.append({
                        "title": title,
                        "url": link,
                        "publish_date": pub_date,
                        "source": source_name
                    })
            
            logger.debug(f"Parsed {len(articles)} articles from {source_name} RSS.")
            return articles
        except Exception as e:
            logger.error(f"Error fetching/parsing RSS feed from {source_name}: {e}")
            return []

    def fetch_news_api(self, keyword: str) -> List[Dict[str, str]]:
        """Queries NewsAPI for articles relating to the specified keyword."""
        api_key = config.NEWS_API_KEY
        if not api_key:
            return []
            
        logger.debug(f"Querying NewsAPI for keyword: '{keyword}'...")
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": keyword,
            "sortBy": "publishedAt",
            "pageSize": 15,
            "apiKey": api_key
        }
        
        try:
            response = requests.get(url, params=params, timeout=10.0)
            if response.status_code != 200:
                logger.warning(f"NewsAPI error for '{keyword}'. Status: {response.status_code}")
                return []
                
            data = response.json()
            articles = []
            for art in data.get("articles", []):
                title = art.get("title", "").strip()
                link = art.get("url", "").strip()
                pub_date = art.get("publishedAt", "").strip()
                source_name = art.get("source", {}).get("name", "NewsAPI").strip()
                
                if title and link:
                    articles.append({
                        "title": title,
                        "url": link,
                        "publish_date": pub_date,
                        "source": source_name
                    })
            return articles
        except Exception as e:
            logger.error(f"Error fetching from NewsAPI for '{keyword}': {e}")
            return []

    def collect_and_store_news(self) -> List[Dict[str, Any]]:
        """
        Gathers news from RSS and NewsAPI, runs cleaning and classification,
        and saves unique records into the database.
        """
        logger.info("Starting news intelligence collection...")
        all_articles: List[Dict[str, str]] = []

        # 1. Fetch RSS Feeds
        for source_name, url in self.RSS_FEEDS.items():
            all_articles.extend(self.fetch_rss_feed(source_name, url))

        # 2. Fetch NewsAPI if API Key is configured
        if config.NEWS_API_KEY:
            for kw in self.KEYWORDS:
                all_articles.extend(self.fetch_news_api(kw))
        else:
            logger.info("NewsAPI API key not configured. Fallback to RSS feeds only.")

        # 3. Process, classify, and insert unique articles
        processed_count = 0
        saved_records = []
        timestamp = datetime.datetime.now().isoformat()

        for art in all_articles:
            title = art["title"]
            source = art["source"]
            url = art["url"]
            pub_date = art["publish_date"]

            # Classify sector category
            category = self.preprocessor.classify_text(title)

            # Insert into database (duplicate URLs are automatically ignored due to UNIQUE constraints)
            success = self.db_manager.insert_news_article(
                timestamp=timestamp,
                title=title,
                source=source,
                url=url,
                publish_date=pub_date,
                category=category
            )

            if success:
                processed_count += 1
                saved_records.append({
                    "title": title,
                    "source": source,
                    "url": url,
                    "publish_date": pub_date,
                    "category": category
                })

        logger.info(
            f"News collection finished. Processed {len(all_articles)} total articles. "
            f"Saved {processed_count} unique articles into SQLite news_data."
        )
        return saved_records
