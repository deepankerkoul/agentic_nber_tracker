import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# NBER configuration
NBER_BASE_URL = "https://www.nber.org"
NBER_API_URL = "https://www.nber.org/api/v1/working_group_search/programs-working-groups/innovation-policy?page={}&perPage=50"
START_DATE = datetime.strptime("2026-01-01", "%Y-%m-%d")

# Output configuration
OUTPUT_FILE_PATH = "data/nber_papers_summary.md"

# API Keys
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
