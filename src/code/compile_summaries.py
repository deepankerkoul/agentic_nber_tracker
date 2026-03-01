import os
import sys
import sqlite3
import re
from datetime import datetime

# Add src to the path to allow absolute imports within the project if run from root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.config.settings import DB_PATH, OUTPUT_DIR

def compile_summaries():
    """Reads the tracker database and compiles all generated summaries into a single master document."""
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}. No summaries to compile.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get all successfully processed papers
    try:
        cursor.execute('SELECT title, url, published_date, markdown_file, processed_at FROM processed_papers ORDER BY processed_at DESC')
        papers = cursor.fetchall()
    except sqlite3.OperationalError:
        print("Database 'processed_papers' table not found or empty.")
        conn.close()
        return
        
    if not papers:
        print("No processed papers found in the database.")
        conn.close()
        return

    master_file = os.path.join(OUTPUT_DIR, "master_compiled_summaries.md")

    print(f"Found {len(papers)} processed papers. Compiling their summaries into {master_file}...")

    # Aggregate the contents of the unique markdown files associated with the processed papers.
    cursor.execute('SELECT DISTINCT markdown_file FROM processed_papers ORDER BY processed_at DESC')
    md_files = [row[0] for row in cursor.fetchall()]

    compiled_content = []
    compiled_content.append(f"# NBER Innovation Policy - Master Compiled Summaries\n")
    compiled_content.append(f"**Total Papers Extracted & Summarized:** {len(papers)}\n")
    compiled_content.append(f"**Compilation Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    compiled_content.append("---\n\n")

    for md_file_path in md_files:
        if os.path.exists(md_file_path):
            with open(md_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Strip out the redundant individual run headers to make the master file clean
                content = re.sub(r'# NBER Innovation Policy Working Papers Tracker - Run .*\n*', '', content)
                content = re.sub(r'Generated on: .*\n*', '', content)
                compiled_content.append(content.strip() + "\n\n---\n\n")
        else:
            print(f"Warning: Linked summary file not found: {md_file_path}")

    with open(master_file, 'w', encoding='utf-8') as f:
        f.write("".join(compiled_content))

    print(f"Successfully compiled summaries into {master_file}!")
    conn.close()

if __name__ == "__main__":
    compile_summaries()
