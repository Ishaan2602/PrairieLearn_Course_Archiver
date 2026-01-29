# PrairieLearn Course Archiver

Creates permanent, offline read-only archives of PrairieLearn courses for personal study and review. 

I built this tool to save PrairieLearn course resources for later reference before professors disabled access to the course on PL after its completion.

## What It Does

This automated scraper uses Selenium WebDriver and BeautifulSoup to:

1. **Authentication** - Handles UIUC SSO/Duo 2FA login via browser automation
2. **Scanning** - Parses all weeks and detects available assessment types (PRE, HW, PQ, etc.)
3. **Filter** - Automatically excludes group modules (GA, LAB) with fa-users icons
4. **Download content** - For each selected assessment question:
   - **HTML file** (`index.html`) - Full question content with problem statement and solutions
   - **Screenshots** (`render.png`) - Full-page capture with answers expanded for perfect rendering
   - **Images** - All embedded images downloaded to local `images/` folders


## Output Structure

```
CS_233_archive/
├── Week_1/
│   ├── PRE_01/
│   │   ├── General/
│   │   │   ├── Question_Title_abc123/
│   │   │   │   ├── index.html
│   │   │   │   ├── render.png
│   │   │   │   └── images/
│   │   │   │       ├── diagram.png
│   │   │   │       └── ...
│   ├── HW_01/
│   │   └── ...
├── Week_2/
│   └── ...
└── CS_233_progress.json
```

Files are organized hierarchically: **Week → Assessment → Category → Question**

## Features

- Works with any PrairieLearn course URL
- Extracts course name (e.g., "CS 233") from navbar and creates `{course_name}_archive` folder
- Prompts user to select which module types to download (PRE, HW, PQ, etc.)
- Automatically excludes group assignments that require collaboration
- Skips already-downloaded files and tracks progress per course
- Truncates long filenames to 80 characters with MD5 hash for Windows compatibility

## Requirements

```bash
pip install selenium beautifulsoup4 requests
```

- Note: Use Chrome browser (WebDriver managed automatically)

## Usage

```bash
python scraper_enhanced.py [course_url]
```

**Example:**
```bash
python scraper_enhanced.py https://us.prairielearn.com/pl/course_instance/12345/assessments
```

The scraper will:

1. Open Chrome browser for manual login
2. Wait for you to complete authentication (SSO + Duo)
3. Prompt "PRESS ENTER ONCE YOU ARE LOGGED IN"
4. Scan available assessment types and display options
5. Ask which types to download (e.g., `1,2,5` or `all`)
6. Download all content for selected types
7. Automatically fix CSS paths when complete

Output saved to `{CourseName}_archive/` directory.
