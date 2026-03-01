import os
import re
import sys
import sqlite3
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from google import genai

# Add src to the path to allow absolute imports within the project if run from root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.config.settings import (
    NBER_BASE_URL, 
    NBER_API_URL, 
    START_DATE, 
    OUTPUT_DIR,
    DB_PATH,
    LOGS_DIR,
    GEMINI_API_KEY
)

# Setup Logging
os.makedirs(LOGS_DIR, exist_ok=True)
date_str = datetime.now().strftime('%Y%m%d')
exec_log_filename = os.path.join(LOGS_DIR, f"tracker_{date_str}_execution.log")
error_log_filename = os.path.join(LOGS_DIR, f"tracker_{date_str}_error.log")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Clear existing handlers if any
if logger.hasHandlers():
    logger.handlers.clear()

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# Execution Log Handler (Appends to daily file)
exec_handler = logging.FileHandler(exec_log_filename, mode='a')
exec_handler.setLevel(logging.INFO)
exec_handler.setFormatter(formatter)

# Error Log Handler (Appends to daily error file)
err_handler = logging.FileHandler(error_log_filename, mode='a')
err_handler.setLevel(logging.ERROR)
err_handler.setFormatter(formatter)

# Console Handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

logger.addHandler(exec_handler)
logger.addHandler(err_handler)
logger.addHandler(console_handler)

if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY environment variable not set.")
    raise ValueError("GEMINI_API_KEY environment variable not set. Please set it via export or in a .env file.")

client = genai.Client(api_key=GEMINI_API_KEY)

def init_db():
    """Initializes the SQLite database and creates the necessary tables."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_papers (
            url TEXT PRIMARY KEY,
            title TEXT,
            published_date TEXT,
            markdown_file TEXT,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return conn

def is_paper_processed(conn, url):
    """Checks if a paper URL already exists in the database."""
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM processed_papers WHERE url = ?', (url,))
    return cursor.fetchone() is not None

def record_paper_processed(conn, url, title, date, md_file):
    """Records a processed paper in the database."""
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO processed_papers (url, title, published_date, markdown_file)
        VALUES (?, ?, ?, ?)
    ''', (url, title, date, md_file))
    conn.commit()

def fetch_recent_papers():
    """Fetches papers from the NBER working paper search API."""
    logger.info("Fetching recent innovation policy papers from NBER API...")
    papers_to_process = []
    page = 1
    
    while True:
        url = NBER_API_URL.format(page)
        logger.info(f"Navigating to page {page}: {url}")
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"Failed to fetch NBER API page {page}: {e}", exc_info=True)
            break
            
        results = data.get("results", [])
        if not results:
            logger.info("No articles found on this page. Reached the end of pagination.")
            break
            
        for paper in results:
            date_str = paper.get("displaydate", "")
            try:
                # E.g. "January 2026" or "Jan 2026".
                paper_date = datetime.strptime(date_str, "%B %Y")
            except ValueError:
                logger.warning(f"Skipping paper with invalid date format: '{date_str}'")
                continue
            
            if paper_date >= START_DATE:
                paper_url = NBER_BASE_URL + paper.get("url", "")
                title = paper.get("title", "")
                
                papers_to_process.append({
                    "title": title,
                    "url": paper_url,
                    "date": date_str
                })
            else:
                logger.info(f"Encountered a paper published before {START_DATE.strftime('%B %Y')}. Halting search.")
                return papers_to_process
                
        page += 1
        
    return papers_to_process

def extract_paper_details(paper_url):
    """Fetches the specific paper page to extract the full text/abstract."""
    logger.info(f"Extracting details for: {paper_url}")
    try:
        response = requests.get(paper_url)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch paper page {paper_url}: {e}", exc_info=True)
        return None

    soup = BeautifulSoup(response.content, "html.parser")
    
    abstract_div = soup.find("div", class_="page-header__intro-inner")
    if abstract_div:
        abstract = abstract_div.get_text(separator=' ', strip=True)
    else:
        paragraphs = soup.find_all("p")
        abstract = " ".join([p.get_text(strip=True) for p in paragraphs[:3]])
        
    author_section = soup.find("div", class_="page-header__authors")
    author_text = author_section.get_text(separator=' ', strip=True) if author_section else "Authors not found"
    
    return f"Abstract: {abstract}\n\nAuthor Info: {author_text}"

def summarize_with_gemini(paper_info, url, title, date):
    """Uses Gemini to summarize the paper and extract metadata."""
    logger.info(f"Summarizing paper with Gemini: {title}")
    prompt = f"""
You are an expert academic assistant. A user wants to track working papers. I am providing you with the text extracted from a working paper's webpage.

Paper Title: {title}
Paper URL: {url}
Date: {date}

Extracted Text:
{paper_info}

Please extract the following information and output it EXACTLY in Markdown format as provided below:

### [{title}]({url})
- **Date**: {date}
- **Authors**: [Comma-separated list of authors]
- **Affiliations**: [Any affiliations mentioned]
- **Emails**: [Any emails mentioned, if none write "Not provided"]
- **Summary**: [A high-level 2-3 sentence summary of the abstract discussing the paper's contribution]

Ensure the output is valid Markdown.
"""
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        logger.error(f"Failed to summarize paper using Gemini: {e}", exc_info=True)
        return None

def main():
    logger.info("Starting NBER Tracker script execution.")
    conn = init_db()
    
    papers = fetch_recent_papers()
    logger.info(f"Found {len(papers)} papers since {START_DATE.strftime('%B %Y')}.")
    
    if not papers:
        logger.info("No new papers to process. Exiting.")
        return
        
    # Generate a timestamp for this run's markdown file
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = os.path.join(OUTPUT_DIR, f"summary_{run_timestamp}.md")
    
    new_papers_added = 0
    markdown_buffer = []

    for idx, paper in enumerate(papers):
        logger.info(f"Processing ({idx+1}/{len(papers)}): {paper['title']}")
        
        if is_paper_processed(conn, paper['url']):
            logger.info(f"Paper already processed, skipping: {paper['url']}")
            continue
            
        paper_info = extract_paper_details(paper['url'])
        if not paper_info:
            continue
            
        summary_md = summarize_with_gemini(paper_info, paper['url'], paper['title'], paper['date'])
        if not summary_md:
            continue
            
        markdown_buffer.append(summary_md)
        record_paper_processed(conn, paper['url'], paper['title'], paper['date'], output_filename)
        new_papers_added += 1

    if markdown_buffer:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(f"# NBER Innovation Policy Working Papers Tracker - Run {run_timestamp}\n\n")
            f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("\n\n".join(markdown_buffer) + "\n\n")
        logger.info(f"Saved {new_papers_added} summaries to {output_filename}")
    else:
        logger.info("No new summaries were generated during this run.")
        
    logger.info(f"Done! Processed {new_papers_added} new papers.")
    conn.close()

if __name__ == "__main__":
    main()
