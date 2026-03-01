# NBER Paper Tracker Code Walkthrough

This document explains the core components and logic flow of the NBER Innovation Policy Working Paper Tracker.

## Directory Structure

*   `src/config/settings.py`: Contains global configuration variables such as the NBER API URL, the date to start tracking from (`START_DATE`), and file paths for the SQLite database and logs.
*   `src/code/main.py`: The core operational script. It coordinates fetching data, extracting details, summarizing with Gemini, and persisting the results.
*   `data/`: The storage directory for the SQLite database (`tracker.db`) and the generated markdown summaries.
*   `logs/`: Contains execution and error logs generated during each run.
*   `.github/workflows/schedule.yml`: The GitHub Actions workflow definition for daily automated runs.

## Core Logic Flow (`src/code/main.py`)

The script follows a linear pipeline execution when `main()` is called.

### 1. Initialization and Setup
*   **Logging**: The script first initializes structured logging. It creates two files per day: one for general execution info (`tracker_YYYYMMDD_execution.log`) and one specifically for errors (`tracker_YYYYMMDD_error.log`), capturing full tracebacks for easy debugging.
*   **Database**: It connects to `data/tracker.db` via `init_db()`. This SQLite database uses a `processed_papers` table to track the `url`, `title`, and associated output `markdown_file` of every paper processed. This ensures the script is idempotent and handles checkpointing.

### 2. Fetching the Paper List (`fetch_recent_papers`)
*   The script queries NBER's internal JSON API (undocumented, reverse-engineered for stability).
*   It iterates through pagination (`page=1`, `page=2`, etc.) until it encounters a paper published *before* our configured `START_DATE`.
*   It extracts the paper title, URL, and publication date, returning a list of dictionaries for papers that need processing.

### 3. Processing Papers Loop
The script iterates over the list of recent papers:

*   **Checkpoint Check**: It calls `is_paper_processed(conn, url)`. If the paper is already in the database, it skips it.
*   **Detail Extraction (`extract_paper_details`)**: It fetches the individual paper's HTML page and uses BeautifulSoup to extract the abstract and author information.
*   **Summarization (`summarize_with_gemini`)**: It constructs a prompt containing the paper details and sends it to the `gemini-2.5-flash` model. The prompt instructs the model to return a structured Markdown snippet containing metadata and a high-level 2-3 sentence summary.
    *   *Rate Limit Handling*: This function includes retry logic with exponential backoff to gracefully handle `429 RESOURCE_EXHAUSTED` errors from the Gemini free tier.
*   **Database Update (`record_paper_processed`)**: If successful, the paper is logged in the SQLite database alongside the name of the markdown file it will be written to.

### 4. Persistence
*   All generated markdown snippets from the current run are batched together.
*   If new summaries exist, they are written to a uniquely timestamped Markdown file (e.g., `data/summary_YYYYMMDD_HHMMSS.md`). This approach prevents massive, monolithic markdown files and clearly demarcates each run's findings.

## Automation

The `.github/workflows/schedule.yml` file configures a cron job that runs daily at 08:00 UTC. It checks out the code, installs Python and dependencies, runs `main.py` (injecting the Gemini API key from repository secrets), and then commits any new files added to the `data/` or `logs/` directories back to the repository.
