# NBER Innovation Policy Working Paper Tracker

This project tracks new working papers published by the [Innovation Policy Group at NBER](https://www.nber.org/programs-projects/programs-working-groups#Groups/innovation-policy). It scrapes the NBER website for papers published on or after January 1, 2026, and uses Gemini to extract metadata (authors, affiliations, emails) and provide a concise summary of the abstract.

## Directory Structure

- `src/code/`: Contains the main Python crawler and scraper logic.
- `src/config/`: Contains configuration settings and constants.
- `data/`: Stores the output Markdown file with tracking results.
- `docs/`: Stores any related documentation.
- `.github/workflows/`: Contains the GitHub Actions workflow definition for daily execution.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set up your Gemini API key:
   ```bash
   export GEMINI_API_KEY="your_api_key_here"
   ```

## Usage
Run the main script to update the tracker:
```bash
python src/code/main.py
```
The results will be appended to `data/nber_papers_summary.md`.
