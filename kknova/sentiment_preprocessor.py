import re
import html
from typing import List, Set

class SentimentPreprocessor:
    """
    Cleans news article headlines and classifies them into sector categories
    based on predefined keywords.
    """
    
    # Categorization keywords mapped to their sector categories
    CATEGORY_KEYWORDS = {
        "Banking": {
            "bank", "banking", "sbi", "pnb", "hdfc", "icici", "axis", "kotak", 
            "rbi", "npa", "lending", "loan", "finance"
        },
        "IT": {
            "it", "tcs", "infosys", "wipro", "tech", "software", "hcl", 
            "cognizant", "layoff", "cybersecurity", "digital"
        },
        "Auto": {
            "auto", "automobile", "car", "tata motors", "mahindra", "maruti", 
            "ev", "vehicle", "electric vehicle", "hyundai", "bajaj"
        },
        "Pharma": {
            "pharma", "pharmaceutical", "drug", "healthcare", "fda", "vaccine", 
            "sun pharma", "cipla", "dr reddy", "biotech", "hospital"
        },
        "Defence": {
            "defence", "defense", "military", "hal", "bel", "weapon", "arms", 
            "missile", "fighter jet", "navy", "army", "air force", "war"
        },
        "PSU": {
            "psu", "public sector", "bhel", "ntpc", "coal india", "lic", "sail", 
            "gail", "iocl", "bpcl", "ongc"
        },
        "AI": {
            "ai", "artificial intelligence", "machine learning", "deep learning", 
            "data center", "datacenter", "nvidia", "llm", "generative ai"
        },
        "Renewable Energy": {
            "solar", "wind", "renewable", "green energy", "hydrogen", "clean energy", 
            "biofuel", "ev charging", "solar panel", "wind turbine"
        },
        "Infrastructure": {
            "infra", "infrastructure", "road", "highway", "bridge", "cement", 
            "port", "railway", "airport", "construction", "real estate"
        },
        "Nifty": {
            "nifty", "sensex", "market", "indices", "index", "bull", "bear", 
            "stock market", "nse", "bse"
        }
    }

    @staticmethod
    def clean_text(text: str) -> str:
        """
        Cleans HTML entities, removes special characters, reduces whitespace,
        and converts text to lowercase.
        """
        if not text:
            return ""
        # Unescape HTML entities
        text = html.unescape(text)
        # Convert to lowercase
        text = text.lower()
        # Remove HTML tags if any
        text = re.sub(r"<[^>]+>", "", text)
        # Replace special characters and extra whitespaces
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def classify_text(self, text: str) -> str:
        """
        Classifies a text string (headline or description) into a sector category.
        Returns the category name with the highest keyword match count.
        If no keywords match, returns 'General'.
        """
        cleaned = self.clean_text(text)
        # Use regex to find whole words to prevent partial matching (e.g. 'it' matching 'hit')
        words = set(re.findall(r"\b[a-z0-9\-]+\b", cleaned))

        matches = {}
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            # Count overlap between text words and category keywords
            match_count = len(words.intersection(keywords))
            # Also check for exact multi-word substring matches (e.g. "green energy")
            for kw in keywords:
                if " " in kw and kw in cleaned:
                    match_count += 1
            if match_count > 0:
                matches[category] = match_count

        if not matches:
            return "General"

        # Return category with the maximum matches
        return max(matches, key=matches.get)
