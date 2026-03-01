import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# NBER configuration
NBER_BASE_URL = "https://www.nber.org"
NBER_API_URL = "https://www.nber.org/api/v1/working_page_listing/contentType/working_paper/_/_/search?page={}&perPage=50&sortBy=public_date"



START_DATE = datetime.strptime("2026-01-01", "%Y-%m-%d")

# Output configuration
OUTPUT_DIR = "data"
DB_PATH = os.path.join(OUTPUT_DIR, "tracker.db")

# Logging configuration
LOGS_DIR = "logs"

# API Keys
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
