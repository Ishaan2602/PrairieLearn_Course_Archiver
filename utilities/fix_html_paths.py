import os
import re
from pathlib import Path

# Configuration
ARCHIVE_DIR = "pl_archive_final"
PRAIRIELEARN_BASE = "https://us.prairielearn.com"

def fix_html_file(filepath):
    """Fix asset paths in an HTML file to use absolute URLs."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Fix asset paths: /assets/... -> https://us.prairielearn.com/assets/...
        content = re.sub(
            r'(src|href)="(/assets/[^"]+)"',
            r'\1="' + PRAIRIELEARN_BASE + r'\2"',
            content
        )
        
        # Fix other PrairieLearn paths that might be relative
        content = re.sub(
            r'(src|href)="(/pl/[^"]+)"',
            r'\1="' + PRAIRIELEARN_BASE + r'\2"',
            content
        )
        
        # Only write if content changed
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
        
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def main():
    """Fix all HTML files in the archive directory."""
    archive_path = Path(ARCHIVE_DIR)
    
    if not archive_path.exists():
        print(f"Error: {ARCHIVE_DIR} directory not found!")
        return
    
    # Find all HTML files
    html_files = list(archive_path.rglob("*.html"))
    print(f"Found {len(html_files)} HTML files")
    
    fixed_count = 0
    for html_file in html_files:
        if fix_html_file(html_file):
            fixed_count += 1
            if fixed_count % 10 == 0:
                print(f"  Fixed {fixed_count}/{len(html_files)} files...")
    
    print(f"\nCompleted! Fixed {fixed_count} HTML files.")
    print("You can now open the HTML files in your browser and the CSS should load.")

if __name__ == "__main__":
    main()
