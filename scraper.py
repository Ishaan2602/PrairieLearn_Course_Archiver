import os
import sys
import time
import re
import hashlib
import json
import logging
from datetime import datetime
import requests
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup

# Configuration
DEFAULT_COURSE_URL = "https://us.prairielearn.com/pl/course_instance/187195/assessments"
MAX_RETRIES = 3
REQUEST_TIMEOUT = 15

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(f'scraper_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def clean_filename(text, max_length=80):
    """Sanitize text for use as filename, truncating if needed."""
    clean = re.sub(r'[\\/*?:"<>|]', "", text)
    clean = clean.strip().replace(" ", "_")
    
    if len(clean) > max_length:
        hash_suffix = hashlib.md5(text.encode()).hexdigest()[:8]
        clean = clean[:max_length-9] + "_" + hash_suffix
    
    return clean

def validate_html_file(filepath):
    """Check if HTML file exists and is valid."""
    if not os.path.exists(filepath):
        return False
    
    try:
        size = os.path.getsize(filepath)
        if size < 1000:  # Suspiciously small
            return False
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(500)
            if '<!doctype html>' not in content.lower() and '<html' not in content.lower():
                return False
        
        return True
    except:
        return False





def download_with_retry(url, cookies, max_retries=MAX_RETRIES):
    """Download content with retry logic."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, cookies=cookies, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                return response.content
            elif response.status_code == 401:
                logger.error("Session expired - please re-login")
                return None
        except requests.Timeout:
            logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries}")
            time.sleep(2 ** attempt)
        except Exception as e:
            logger.warning(f"Download failed (attempt {attempt + 1}): {e}")
            time.sleep(2 ** attempt)
    
    return None

def download_images(driver, html_content, question_folder):
    """Download PrairieLearn images and update HTML to use local paths."""
    soup = BeautifulSoup(html_content, 'html.parser')
    images = soup.find_all('img', src=True)
    
    if not images:
        return html_content
    
    images_folder = os.path.join(question_folder, 'images')
    os.makedirs(images_folder, exist_ok=True)
    
    cookies = {cookie['name']: cookie['value'] for cookie in driver.get_cookies()}
    downloaded_count = 0
    
    for img in images:
        src = img['src']
        
        if 'prairielearn.com' in src and ('clientFilesCourse' in src or 'clientFilesQuestion' in src):
            try:
                filename = os.path.basename(urlparse(src).path)
                if not filename:
                    filename = f"image_{hashlib.md5(src.encode()).hexdigest()[:8]}.png"
                
                local_path = os.path.join(images_folder, filename)
                
                if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                    img['src'] = f"images/{filename}"
                    continue
                
                content = download_with_retry(src, cookies)
                
                if content:
                    with open(local_path, 'wb') as f:
                        f.write(content)
                    img['src'] = f"images/{filename}"
                    downloaded_count += 1
                    logger.info(f"    Downloaded image: {filename}")
            
            except Exception as e:
                logger.error(f"    Image download error: {e}")
    
    if downloaded_count > 0:
        logger.info(f"  Downloaded {downloaded_count} image(s)")
    
    return str(soup)

def take_full_page_screenshot(driver, filepath):
    """Capture full-page screenshot using Chrome DevTools."""
    try:
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)
        
        total_height = driver.execute_script("return document.body.scrollHeight")
        viewport_height = driver.execute_script("return document.documentElement.clientHeight")
        
        try:
            if total_height > viewport_height:
                result = driver.execute_cdp_cmd('Page.captureScreenshot', {
                    'captureBeyondViewport': True,
                    'fromSurface': True
                })
                
                import base64
                screenshot = base64.b64decode(result['data'])
            else:
                screenshot = driver.get_screenshot_as_png()
            
            with open(filepath, 'wb') as f:
                f.write(screenshot)
            
            logger.info(f"  Screenshot saved")
            return True
            
        except Exception as e:
            driver.save_screenshot(filepath)
            logger.info(f"  Screenshot saved (fallback)")
            return True
            
    except Exception as e:
        logger.error(f"  Screenshot failed: {e}")
        return False

def expand_answer_panel(driver):
    """Attempt to expand answer/solution panels."""
    try:
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            text = btn.text.lower()
            if "correct answer" in text or "solution" in text or "submission" in text:
                try:
                    btn.click()
                    time.sleep(0.5)
                except:
                    pass
    except:
        pass

def check_session_valid(driver):
    """Verify the session is still authenticated."""
    try:
        current_url = driver.current_url
        if "login" in current_url.lower() or "sign" in current_url.lower():
            logger.error("Session expired - please re-login")
            return False
        return True
    except:
        return True

def extract_course_name(driver):
    """Extract course name/code from the page."""
    try:
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Try to find course name in navbar
        navbar_text = soup.find('li', class_='navbar-text')
        if navbar_text:
            text = navbar_text.get_text(strip=True)
            # Usually in format "CS 233, Fa25" or similar
            match = re.search(r'([A-Z]+\s*\d+)', text)
            if match:
                return match.group(1).replace(' ', '_')
        
        # Fallback: extract from URL
        url = driver.current_url
        match = re.search(r'/course_instance/(\d+)', url)
        if match:
            return f"Course_{match.group(1)}"
        
        return "PrairieLearn_Archive"
    except:
        return "PrairieLearn_Archive"

def fix_css_paths(output_dir):
    """Fix HTML files to use absolute URLs for CSS/JS assets."""
    from pathlib import Path
    
    logger.info("\n=== FIXING CSS/JS PATHS ===")
    archive_path = Path(output_dir)
    
    if not archive_path.exists():
        logger.warning("Output directory not found, skipping CSS fix")
        return
    
    html_files = list(archive_path.rglob("*.html"))
    logger.info(f"Found {len(html_files)} HTML files to fix")
    
    fixed_count = 0
    prairielearn_base = "https://us.prairielearn.com"
    
    for html_file in html_files:
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Fix asset paths
            content = re.sub(
                r'(src|href)="(/assets/[^"]+)"',
                r'\1="' + prairielearn_base + r'\2"',
                content
            )
            
            # Fix PrairieLearn paths
            content = re.sub(
                r'(src|href)="(/pl/[^"]+)"',
                r'\1="' + prairielearn_base + r'\2"',
                content
            )
            
            if content != original_content:
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                fixed_count += 1
                
                if fixed_count % 50 == 0:
                    logger.info(f"  Fixed {fixed_count}/{len(html_files)} files...")
        
        except Exception as e:
            logger.warning(f"Failed to fix {html_file}: {e}")
    
    logger.info(f"CSS fix complete! Fixed {fixed_count} HTML files.")

def main():
    course_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_COURSE_URL
    logger.info(f"Starting scraper for: {course_url}")
    
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(options=options)
    
    # Will be set after login when we can extract course name
    output_dir = None
    completed_questions = set()

    try:
        logger.info("=== LOGIN PHASE ===")
        driver.get(course_url)
        
        try:
            sign_in_buttons = driver.find_elements(By.XPATH, "//a[contains(text(), 'Sign in with')]")
            for btn in sign_in_buttons:
                if "Microsoft" in btn.text or "Illinois" in btn.text:
                    btn.click()
                    break
        except:
            pass

        print("\nAction Required: Please log in via the browser window.")
        print("Navigate until you see the list of Weeks (Week 1, Week 2...).")
        input(">>> PRESS ENTER HERE ONCE YOU ARE LOGGED IN <<<\n")

        logger.info("Waiting for page to load...")
        time.sleep(3)
        
        if "/assessments" not in driver.current_url:
            logger.info("Navigating to assessments page...")
            driver.get(course_url)
            time.sleep(3)

        # Extract course name and create output directory
        course_name = extract_course_name(driver)
        output_dir = f"{course_name}_archive"
        
        logger.info(f"Course identified: {course_name}")
        logger.info(f"Output directory: {output_dir}")

        logger.info("=== SCANNING WEEKS ===")
        
        debug_path = os.path.join(output_dir, "_debug_main_page.html")
        os.makedirs(output_dir, exist_ok=True)
        with open(debug_path, 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        all_rows = soup.find_all("tr")
        
        # Phase 1: Discover all module types
        logger.info("\n=== DISCOVERING MODULE TYPES ===")
        module_types = {}  # {type: {count, is_group, sample_title}}
        temp_assessments = []
        current_week_num = None

        for row in all_rows:
            header_th = row.find("th", {"data-testid": "assessment-group-heading"})
            
            if header_th:
                week_title = header_th.get_text(strip=True)
                week_match = re.search(r'Week\s+(\d+)', week_title, re.IGNORECASE)
                
                if week_match:
                    week_num = int(week_match.group(1))
                    if 1 <= week_num <= 14:
                        current_week_num = week_num
                    else:
                        current_week_num = None
                continue
            
            if current_week_num is not None:
                badge = row.find("span", class_="badge")
                
                if badge:
                    badge_text = badge.get_text(strip=True)
                    link = row.find("a", href=True)
                    
                    if link and link.get('href'):
                        href = link.get('href')
                        link_text = link.get_text(strip=True)
                        
                        # Check if this is a group module (has users icon)
                        is_group = link.find("i", class_=lambda x: x and "fa-users" in str(x))
                        
                        if "/assessment/" in href or "/assessment_instance/" in href:
                            # Extract module type prefix (PRE, HW, GA, LAB, etc.)
                            type_match = re.match(r'^([A-Z]+)', badge_text)
                            if type_match:
                                module_type = type_match.group(1)
                                
                                if module_type not in module_types:
                                    module_types[module_type] = {
                                        'count': 0,
                                        'is_group': bool(is_group),
                                        'sample_title': link_text
                                    }
                                
                                module_types[module_type]['count'] += 1
                                
                                # Store for later filtering
                                full_url = href if href.startswith("http") else "https://us.prairielearn.com" + href
                                temp_assessments.append({
                                    "week": clean_filename(f"Week_{current_week_num}"),
                                    "name": clean_filename(badge_text),
                                    "title": link_text,
                                    "url": full_url,
                                    "type": module_type,
                                    "is_group": bool(is_group)
                                })
        
        # Phase 2: Display non-group types and get user selection
        available_types = {k: v for k, v in module_types.items() if not v['is_group']}
        
        if not available_types:
            logger.error("No downloadable module types found!")
            return
        
        logger.info("\nFound the following module types:")
        type_list = sorted(available_types.keys())
        for idx, module_type in enumerate(type_list, 1):
            info = available_types[module_type]
            logger.info(f"  {idx}. {module_type:8s} ({info['count']:2d} items) - {info['sample_title'][:50]}")
        
        # Excluded group types
        excluded_types = {k: v for k, v in module_types.items() if v['is_group']}
        if excluded_types:
            logger.info("\nExcluded (group modules):")
            for module_type, info in sorted(excluded_types.items()):
                logger.info(f"  - {module_type:8s} ({info['count']:2d} items) - {info['sample_title'][:50]}")
        
        print("\nSelect module types to download:")
        print("  Enter numbers separated by commas (e.g., 1,2,5)")
        print("  Or enter 'all' to download all non-group types")
        user_input = input(">>> Your selection: ").strip().lower()
        
        # Parse user selection
        if user_input == 'all':
            selected_types = set(type_list)
        else:
            try:
                indices = [int(x.strip()) for x in user_input.split(',')]
                selected_types = {type_list[i-1] for i in indices if 1 <= i <= len(type_list)}
            except (ValueError, IndexError):
                logger.error("Invalid selection! Please enter valid numbers or 'all'")
                return
        
        if not selected_types:
            logger.error("No types selected!")
            return
        
        logger.info(f"\nSelected types: {', '.join(sorted(selected_types))}")
        
        # Filter assessments based on selection
        assessments_to_process = [
            a for a in temp_assessments 
            if a['type'] in selected_types and not a['is_group']
        ]

        logger.info(f"\nFound {len(assessments_to_process)} assessments to download")
        
        for assess_idx, assess in enumerate(assessments_to_process, 1):
            logger.info(f"\n[{assess_idx}/{len(assessments_to_process)}] Processing: {assess['name']} ({assess['week']})")
            
            if not check_session_valid(driver):
                logger.error("Session lost. Please restart scraper.")
                break
            
            try:
                driver.get(assess['url'])
                time.sleep(2)
            except Exception as e:
                logger.error(f"Failed to load assessment: {e}")
                continue
            
            assess_soup = BeautifulSoup(driver.page_source, "html.parser")
            rows = assess_soup.find_all("tr")
            
            current_category = "General"
            questions_to_scrape = []
            
            for row in rows:
                th = row.find("th", {"colspan": True})
                if th:
                    category_text = th.get_text(strip=True)
                    if "Question" not in category_text and "Value" not in category_text and category_text:
                        current_category = clean_filename(category_text)
                    continue

                link = row.find("a", href=True)
                if link and link.get("href") and "/instance_question/" in link.get("href"):
                    q_title = link.get_text(strip=True)
                    q_url = "https://us.prairielearn.com" + link.get("href")
                    
                    questions_to_scrape.append({
                        "category": current_category,
                        "title": clean_filename(q_title),
                        "url": q_url
                    })

            logger.info(f"  Found {len(questions_to_scrape)} questions")

            for q_idx, q in enumerate(questions_to_scrape, 1):
                question_id = f"{assess['name']}_{q['title']}"
                
                if question_id in completed_questions:
                    logger.info(f"  [{q_idx}/{len(questions_to_scrape)}] SKIP: {q['title'][:50]} (completed)")
                    continue
                
                try:
                    question_folder = os.path.join(
                        output_dir,
                        assess['week'],
                        assess['name'],
                        q['category'],
                        q['title']
                    )
                    
                    save_path = os.path.join(question_folder, "index.html")
                    screenshot_path = os.path.join(question_folder, "render.png")
                    
                    if validate_html_file(save_path):
                        images_folder = os.path.join(question_folder, 'images')
                        needs_images = not os.path.exists(images_folder) or len(os.listdir(images_folder)) == 0
                        needs_screenshot = not os.path.exists(screenshot_path)
                        
                        if not needs_images and not needs_screenshot:
                            logger.info(f"  [{q_idx}/{len(questions_to_scrape)}] SKIP: {q['title'][:50]}")
                            completed_questions.add(question_id)
                            continue
                    
                    logger.info(f"  [{q_idx}/{len(questions_to_scrape)}] Downloading: {q['title'][:50]}")
                    
                    driver.get(q['url'])
                    time.sleep(1.5)
                    
                    expand_answer_panel(driver)
                    time.sleep(0.5)
                    
                    updated_html = download_images(driver, driver.page_source, question_folder)
                    
                    os.makedirs(question_folder, exist_ok=True)
                    with open(save_path, 'w', encoding='utf-8') as f:
                        f.write(updated_html)
                    
                    take_full_page_screenshot(driver, screenshot_path)
                    
                    completed_questions.add(question_id)
                    
                except Exception as e:
                    logger.error(f"  Error processing {q['title'][:50]}: {e}")
                    continue

        logger.info("\n=== SCRAPING COMPLETE ===")
        
        # Automatically fix CSS paths for offline viewing
        logger.info("\n=== APPLYING CSS FIXES ===")
        fix_css_paths(output_dir)
        logger.info("=== ALL DONE! ===")

    except Exception as e:
        logger.error(f"\nFATAL ERROR: {e}")
    finally:
        logger.info("Closing browser...")
        driver.quit()

if __name__ == "__main__":
    main()
