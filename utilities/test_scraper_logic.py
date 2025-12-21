#!/usr/bin/env python3
"""
Test script to validate the general-purpose scraper enhancements
"""

from bs4 import BeautifulSoup
import re

# Read the test HTML
with open('../CS_233_save/old_testing_source_files/main_page.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

soup = BeautifulSoup(html_content, 'html.parser')
all_rows = soup.find_all("tr")

module_types = {}
current_week_num = None
assessments = []

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
                
                # Check if this is a group module
                is_group = link.find("i", class_=lambda x: x and "fa-users" in str(x))
                
                if "/assessment/" in href or "/assessment_instance/" in href:
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
                        
                        assessments.append({
                            "badge": badge_text,
                            "title": link_text,
                            "type": module_type,
                            "is_group": bool(is_group),
                            "week": current_week_num
                        })

print("=== MODULE TYPES FOUND ===\n")
print("Available (non-group) types:")
for module_type, info in sorted(module_types.items()):
    if not info['is_group']:
        print(f"  {module_type:8s} ({info['count']:2d} items) - {info['sample_title'][:60]}")

print("\nExcluded (group) types:")
for module_type, info in sorted(module_types.items()):
    if info['is_group']:
        print(f"  {module_type:8s} ({info['count']:2d} items) - {info['sample_title'][:60]}")

print(f"\nTotal assessments found: {len(assessments)}")
print(f"Group assessments: {sum(1 for a in assessments if a['is_group'])}")
print(f"Non-group assessments: {sum(1 for a in assessments if not a['is_group'])}")

# Show some examples
print("\n=== SAMPLE GROUP MODULES (Should be excluded) ===")
for a in assessments[:20]:
    if a['is_group']:
        print(f"  Week {a['week']:2d} | {a['badge']:10s} | {a['title'][:50]}")

print("\n=== SAMPLE NON-GROUP MODULES (Should be available) ===")
count = 0
for a in assessments:
    if not a['is_group'] and count < 10:
        print(f"  Week {a['week']:2d} | {a['badge']:10s} | {a['title'][:50]}")
        count += 1
