# PrairieLearn Scraper

Downloads course content from PrairieLearn for offline viewing.

## Requirements

- Python 3.x
- Selenium
- BeautifulSoup4
- Chrome browser
- requests

## Usage

```bash
python scraper.py [course_url]
```

If no URL provided, uses default course URL. Browser window will open for login - complete authentication then press Enter in terminal to start scraping.

Output saved to `{course_name}_archive/` directory.

## Utilities

- `utilities/fix_html_paths.py` - Fix asset paths in downloaded HTML files
- `utilities/test_scraper_logic.py` - Test scraper parsing logic
