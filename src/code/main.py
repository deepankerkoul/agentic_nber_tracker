import os
import re
import sys
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
    OUTPUT_FILE_PATH,
    GEMINI_API_KEY
)

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set. Please set it via export or in a .env file.")

client = genai.Client(api_key=GEMINI_API_KEY)

def fetch_recent_papers():
    """Fetches papers from the NBER Innovation Policy search API."""
    papers_to_process = []
    page = 1
    
    while True:
        url = NBER_API_URL.format(page)
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("results", [])
        if not results:
            break
            
        for paper in results:
            date_str = paper.get("displaydate", "")
            try:
                paper_date = datetime.strptime(date_str, "%B %Y")
            except ValueError:
                print(f"Skipping paper with invalid date: {date_str}")
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
                return papers_to_process
                
        page += 1
        
    return papers_to_process

def extract_paper_details(paper_url):
    """Fetches the specific paper page to extract the full text/abstract."""
    response = requests.get(paper_url)
    response.raise_for_status()
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
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    return response.text

def update_markdown_file(markdown_content, file_path=OUTPUT_FILE_PATH):
    """Appends the newly processed markdown content to the tracker file."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    existing_urls = set()
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            urls = re.findall(r'\[.*?\]\((https://www.nber.org/papers/.*?)\)', content)
            existing_urls = set(urls)
            
    url_match = re.search(r'\[.*?\]\((https://www.nber.org/papers/.*?)\)', markdown_content)
    if url_match and url_match.group(1) in existing_urls:
        print(f"Paper {url_match.group(1)} is already tracked. Skipping.")
        return False

    with open(file_path, "a", encoding="utf-8") as f:
        if os.path.getsize(file_path) == 0:
            f.write("# NBER Innovation Policy Working Papers Tracker\n\n")
            f.write("Tracking papers published on or after Jan 1, 2026.\n\n")
        f.write(markdown_content + "\n\n")
        
    return True

def main():
    print("Fetching recent innovation policy papers...")
    papers = fetch_recent_papers()
    print(f"Found {len(papers)} papers since {START_DATE.strftime('%b %Y')}.")
    
    new_papers_added = 0
    for idx, paper in enumerate(papers):
        print(f"Processing ({idx+1}/{len(papers)}): {paper['title']}")
        paper_info = extract_paper_details(paper['url'])
        summary_md = summarize_with_gemini(paper_info, paper['url'], paper['title'], paper['date'])
        
        added = update_markdown_file(summary_md)
        if added:
            new_papers_added += 1
            
    print(f"Done! Added {new_papers_added} new papers to the tracker.")

if __name__ == "__main__":
    main()
