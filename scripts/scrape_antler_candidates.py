#!/usr/bin/env python3
"""
Antler Hub Candidate Scraper
Scrapes candidate information from Antler Hub and stores in MongoDB
"""

import os
import sys
import time
import getpass
from datetime import datetime, timezone
from typing import List, Dict

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from pymongo import MongoClient, errors
from dotenv import load_dotenv


class AntlerScraper:
    """Scraper for Antler Hub candidate information"""
    
    def __init__(self, headless: bool = False):
        """
        Initialize the scraper
        
        Args:
            headless: Run browser in headless mode (default: False for debugging)
        """
        load_dotenv()
        self.mongo_uri = os.getenv('MONGO_URI')
        if not self.mongo_uri:
            raise ValueError("MONGO_URI not found in .env file")
        
        self.antler_email = os.getenv('ANTLER_EMAIL')
        self.antler_password = os.getenv('ANTLER_PASSWORD')
        
        self.base_url = "https://hub.antler.co"
        self.founders_url = f"{self.base_url}/cohort/founder"
        self.driver = None
        self.wait = None
        self.db_client = None
        self.db = None
        self.collection = None
        self.headless = headless
        
    def setup_driver(self):
        """Setup Chrome driver with appropriate options"""
        print("Setting up Chrome driver...")
        options = Options()
        
        if self.headless:
            options.add_argument('--headless')
            
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Fix for ARM Mac - find the actual chromedriver executable
        import platform
        import glob
        
        if platform.system() == 'Darwin' and platform.machine() == 'arm64':
            # For ARM Macs, manually find chromedriver
            driver_path = ChromeDriverManager().install()
            driver_dir = os.path.dirname(driver_path)
            
            # Look for the actual chromedriver executable
            chromedriver_files = glob.glob(os.path.join(driver_dir, 'chromedriver*'))
            chromedriver_path = None
            
            for file in chromedriver_files:
                if os.path.isfile(file) and 'THIRD_PARTY' not in file and 'LICENSE' not in file:
                    chromedriver_path = file
                    break
            
            if not chromedriver_path:
                # Fallback: look for chromedriver without extension
                possible_path = os.path.join(driver_dir, 'chromedriver')
                if os.path.exists(possible_path):
                    chromedriver_path = possible_path
                    
            if chromedriver_path:
                # Make sure it's executable
                os.chmod(chromedriver_path, 0o755)
                service = Service(chromedriver_path)
            else:
                # Fallback to system chromedriver
                print("Could not find chromedriver in webdriver-manager cache, trying system chromedriver...")
                service = Service()
        else:
            # For other systems, use the standard approach
            service = Service(ChromeDriverManager().install())
            
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, 20)
        print("Chrome driver setup complete")
        
    def setup_mongodb(self):
        """Setup MongoDB connection and collection"""
        print("Connecting to MongoDB...")
        try:
            self.db_client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
            self.db_client.server_info()
            
            self.db = self.db_client['last-recruiter-mvp']
            self.collection = self.db['users']
            
            self.collection.create_index("name", unique=True, sparse=True)
            self.collection.create_index("antler_profile_url", unique=True, sparse=True)
            
            print(f"Connected to MongoDB. Using database: {self.db.name}, collection: {self.collection.name}")
        except errors.ServerSelectionTimeoutError:
            print("Failed to connect to MongoDB. Please check your connection string.")
            raise
            
    def login_if_needed(self):
        """Handle login if required"""
        print(f"Navigating to {self.founders_url}...")
        self.driver.get(self.founders_url)
        time.sleep(3)
        
        current_url = self.driver.current_url
        if "login" in current_url.lower() or "signin" in current_url.lower() or "auth" in current_url.lower():
            print("\nLogin required...")
            
            # Use credentials from .env if available
            if self.antler_email and self.antler_password:
                email = self.antler_email
                password = self.antler_password
                print(f"Using credentials from .env for: {email}")
            else:
                print("Please enter your credentials:")
                email = input("Email: ")
                password = getpass.getpass("Password: ")
            
            try:
                # Wait for login form to be fully loaded
                time.sleep(2)
                
                # Try multiple selectors for email field
                email_selectors = [
                    "input[type='email']",
                    "input[name='email']",
                    "input[id*='email']",
                    "input[placeholder*='email' i]",
                    "input[autocomplete='email']"
                ]
                
                email_field = None
                for selector in email_selectors:
                    try:
                        email_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if email_field.is_displayed():
                            break
                    except:
                        continue
                
                if not email_field:
                    raise Exception("Could not find email field")
                
                # Clear and enter email
                email_field.clear()
                email_field.send_keys(email)
                time.sleep(1)
                
                # Try multiple selectors for password field
                password_selectors = [
                    "input[type='password']",
                    "input[name='password']",
                    "input[id*='password']",
                    "input[placeholder*='password' i]"
                ]
                
                password_field = None
                for selector in password_selectors:
                    try:
                        password_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if password_field.is_displayed():
                            break
                    except:
                        continue
                
                if not password_field:
                    raise Exception("Could not find password field")
                
                # Clear and enter password
                password_field.clear()
                password_field.send_keys(password)
                time.sleep(1)
                
                # Find and click login button
                login_button_selectors = [
                    "button[type='submit']",
                    "button[class*='login']",
                    "button[class*='signin']",
                    "button:contains('Log in')",
                    "button:contains('Sign in')",
                    "input[type='submit']"
                ]
                
                login_button = None
                for selector in login_button_selectors:
                    try:
                        if ':contains' in selector:
                            # Use XPath for text content
                            text = selector.split("'")[1]
                            login_button = self.driver.find_element(By.XPATH, f"//button[contains(text(), '{text}')]")
                        else:
                            login_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if login_button.is_displayed() and login_button.is_enabled():
                            break
                    except:
                        continue
                
                if login_button:
                    login_button.click()
                else:
                    # Try submitting the form directly
                    password_field.submit()
                
                print("Logging in...")
                
                # Wait for login to complete
                time.sleep(5)
                
                # Check if still on login page
                current_url = self.driver.current_url
                if "login" in current_url.lower() or "signin" in current_url.lower():
                    print("Login might have failed. Checking...")
                    # Look for error messages
                    try:
                        error = self.driver.find_element(By.CSS_SELECTOR, "[class*='error'], [class*='alert']")
                        if error.is_displayed():
                            print(f"Login error: {error.text}")
                    except:
                        pass
                    
                    print("Retrying navigation...")
                
                # Navigate to founders page
                print(f"Navigating to founders page: {self.founders_url}")
                self.driver.get(self.founders_url)
                time.sleep(4)
                
                # Double check we're on the right page
                current_url = self.driver.current_url
                if "/cohort/founder" not in current_url and "login" not in current_url.lower():
                    # We might be on the home page, try clicking on Cohort link
                    try:
                        cohort_link = self.driver.find_element(By.LINK_TEXT, "Cohort")
                        cohort_link.click()
                        time.sleep(2)
                        
                        # Then click on Founders tab
                        founders_tab = self.driver.find_element(By.LINK_TEXT, "Founders")
                        founders_tab.click()
                        time.sleep(2)
                    except:
                        # Direct navigation as fallback
                        self.driver.get(self.founders_url)
                        time.sleep(3)
                    
            except Exception as e:
                print(f"Login process encountered an error: {e}")
                print("You may need to login manually in the browser window.")
                input("Press Enter after you've logged in manually...")
                # After manual login, navigate to founders page
                self.driver.get(self.founders_url)
                time.sleep(3)
        else:
            # Already logged in, ensure we're on the founders page
            if "/cohort/founder" not in self.driver.current_url:
                print(f"Already logged in. Navigating to founders page: {self.founders_url}")
                self.driver.get(self.founders_url)
                time.sleep(3)
                
        # Final verification
        final_url = self.driver.current_url
        print(f"Current URL: {final_url}")
        if "/cohort/founder" in final_url:
            print("Successfully on founders page!")
        else:
            print("Warning: May not be on the correct page. Proceeding anyway...")
                
        return True
        
    def wait_for_candidates_to_load(self):
        """Wait for candidate cards to load on the page"""
        print("Waiting for candidates to load...")
        
        # Give the page a moment to start loading
        time.sleep(5)
        
        # Check if candidates are already loaded
        try:
            candidate_containers = self.driver.find_elements(By.CSS_SELECTOR, "div.css-iuxpug")
            if candidate_containers:
                print(f"Candidates already loaded: {len(candidate_containers)} found")
                return True
            
            name_elements = self.driver.find_elements(By.CSS_SELECTOR, "p.css-5gltw")
            if name_elements:
                print(f"Candidate names already loaded: {len(name_elements)} found")
                return True
        except:
            pass
        
        # If not loaded yet, wait with polling
        print("Candidates not immediately visible, waiting...")
        max_wait_time = 15  # seconds
        wait_interval = 3   # seconds
        total_waited = 0
        
        while total_waited < max_wait_time:
            print(f"Still waiting for candidates... ({total_waited}s elapsed)")
            
            try:
                # Scroll to trigger any lazy loading
                self.driver.execute_script("window.scrollTo(0, 500)")
                time.sleep(1)
                self.driver.execute_script("window.scrollTo(0, 0)")
                
                # Check again
                candidate_containers = self.driver.find_elements(By.CSS_SELECTOR, "div.css-iuxpug")
                if candidate_containers:
                    print(f"Found {len(candidate_containers)} candidate containers")
                    return True
                
                name_elements = self.driver.find_elements(By.CSS_SELECTOR, "p.css-5gltw")
                if name_elements:
                    print(f"Found {len(name_elements)} name elements")
                    return True
                    
            except Exception as e:
                print(f"Error during wait: {e}")
            
            time.sleep(wait_interval)
            total_waited += wait_interval
        
        print("Proceeding with scraping regardless...")
        return True
            
    def scrape_current_page(self) -> List[Dict]:
        """
        Scrape candidates from the current page
        
        Returns:
            List of candidate dictionaries
        """
        candidates = []
        
        print("Scraping current page...")
        soup = BeautifulSoup(self.driver.page_source, 'lxml')
        
        # Find all candidate profile containers
        # Look for the main profile containers that contain all candidate info
        profile_containers = soup.find_all('div', class_='css-iuxpug')
        
        if profile_containers:
            print(f"Found {len(profile_containers)} candidate profiles")
            
            for container in profile_containers:
                candidate_data = self.extract_full_candidate_info(container)
                if candidate_data and candidate_data.get('name'):
                    candidates.append(candidate_data)
        
        # Fallback: Try the original name-only approach
        if not candidates:
            print("No profile containers found, trying name-only extraction...")
            name_elements = soup.find_all('p', class_='css-5gltw')
            
            if name_elements:
                print(f"Found {len(name_elements)} candidate names")
                for elem in name_elements:
                    name_text = elem.get_text(strip=True)
                    candidates.append({
                        'name': name_text,
                        'scraped_at': datetime.now(timezone.utc),
                        'source': 'antler_hub'
                    })
        
        # Remove duplicates based on name
        seen_names = set()
        unique_candidates = []
        
        for candidate in candidates:
            name = candidate.get('name', '')
            if name and name not in seen_names:
                seen_names.add(name)
                unique_candidates.append(candidate)
        
        print(f"Found {len(unique_candidates)} unique candidates on this page")
        
        return unique_candidates
        
    def extract_full_candidate_info(self, container) -> Dict:
        """
        Extract complete information from a candidate profile container
        
        Args:
            container: BeautifulSoup element containing candidate profile
            
        Returns:
            Dictionary with complete candidate information
        """
        candidate = {
            'scraped_at': datetime.now(timezone.utc),
            'source': 'antler_hub'
        }
        
        # Extract name (css-5gltw class)
        name_elem = container.find('p', class_='css-5gltw')
        if name_elem:
            candidate['name'] = name_elem.get_text(strip=True)
        
        # Extract tagline/description (css-1s1jbr2 class)
        tagline_elem = container.find('p', class_='css-1s1jbr2')
        if tagline_elem:
            candidate['tagline'] = tagline_elem.get_text(strip=True)
        
        # Extract location
        location_elem = container.find('span', class_='css-1l60zjl')
        if location_elem:
            candidate['location'] = location_elem.get_text(strip=True)
        
        # Extract status (In a team / Looking for co-founder)
        status_elem = container.find('p', class_='css-f9cheu') or container.find('p', class_='css-viedx2')
        if status_elem:
            candidate['status'] = status_elem.get_text(strip=True)
        
        # Extract About Me section
        about_section = container.find('p', class_='css-1b5s80b')
        if about_section:
            candidate['about_me'] = about_section.get_text(strip=True)
        
        # Extract skills
        skill_elements = container.find_all('p', class_='css-olbwyb')
        if skill_elements:
            skills = [skill.get_text(strip=True) for skill in skill_elements]
            # Filter out section headers and non-skill text
            filtered_skills = [skill for skill in skills if skill not in ['Technology', 'Technical Software', 'Domain', 'Business']]
            if filtered_skills:
                candidate['skills'] = filtered_skills
        
        # Check if phone data already exists for this candidate, only add empty field if none exists
        existing_candidate = None
        if 'antler_profile_url' in candidate:
            existing_candidate = self.collection.find_one({'antler_profile_url': candidate['antler_profile_url']})
        else:
            existing_candidate = self.collection.find_one({'name': candidate['name']})
        
        # Only set phone to empty if no existing phone data or if existing phone is empty
        if not existing_candidate or not existing_candidate.get('phone'):
            candidate['phone'] = ""
        
        # Extract profile image URL
        avatar_img = container.find('img', class_='chakra-avatar__img')
        if avatar_img:
            candidate['avatar_url'] = avatar_img.get('src', '')
        
        # Extract Antler cofounder type (Technology, Business, Domain)
        # Try multiple approaches to find the Antler type classification
        antler_types_set = set()  # Use set to avoid duplicates
        
        # Strategy 1: Look for css-10pjdbc class
        cofounder_type_elements = container.find_all('p', class_='css-10pjdbc')
        for type_elem in cofounder_type_elements:
            type_text = type_elem.get_text(strip=True)
            if type_text in ['Technology', 'Business', 'Domain']:
                antler_types_set.add(type_text)
        
        # Strategy 2: Look for any element containing these exact words (if Strategy 1 didn't find anything)
        if not antler_types_set:
            all_elements = container.find_all(['p', 'span', 'div'])
            for elem in all_elements:
                elem_text = elem.get_text(strip=True)
                if elem_text in ['Technology', 'Business', 'Domain']:
                    # Make sure this isn't part of the skills/categories sections
                    parent_classes = elem.parent.get('class', []) if elem.parent else []
                    if not any('css-olbwyb' in str(cls) for cls in parent_classes):
                        antler_types_set.add(elem_text)
        
        # Convert set to list and save if any types found
        if antler_types_set:
            candidate['antler_cofounder_type'] = sorted(list(antler_types_set))
        
        # Extract categories/tags (about me tags)
        category_elements = container.find_all('div', class_='css-i310wq')
        if category_elements:
            categories = []
            for cat_div in category_elements:
                cat_p = cat_div.find('p', class_='css-olbwyb')
                if cat_p:
                    cat_text = cat_p.get_text(strip=True)
                    if cat_text not in ['Technology', 'Technical Software', 'Domain', 'Business']:
                        categories.append(cat_text)
            if categories:
                candidate['categories'] = categories
        
        return candidate if candidate.get('name') else None
        
    def navigate_to_next_page(self) -> bool:
        """
        Navigate to the next page of results
        
        Returns:
            True if navigation successful, False otherwise
        """
        try:
            print("Looking for next page button...")
            
            # Strategy 1: Look for button with text "2"
            try:
                page_2_button = self.driver.find_element(By.XPATH, "//button[.//div[text()='2']]")
                if page_2_button.is_enabled() and page_2_button.is_displayed():
                    print("Found page 2 button, clicking...")
                    page_2_button.click()
                    time.sleep(4)
                    return True
            except:
                pass
            
            # Strategy 2: Look for any button containing "2"
            try:
                buttons_with_2 = self.driver.find_elements(By.XPATH, "//button[contains(text(), '2')]")
                for button in buttons_with_2:
                    if button.is_enabled() and button.is_displayed():
                        print("Found button with '2', clicking...")
                        button.click()
                        time.sleep(4)
                        return True
            except:
                pass
            
            # Strategy 3: Look for next page arrow or similar
            try:
                next_buttons = self.driver.find_elements(By.XPATH, "//button[contains(@class, 'pagination') or contains(@aria-label, 'next') or contains(@class, 'next')]")
                for button in next_buttons:
                    if button.is_enabled() and button.is_displayed():
                        print("Found next page button, clicking...")
                        button.click()
                        time.sleep(4)
                        return True
            except:
                pass
            
            print("No next page button found")
            return False
            
        except Exception as e:
            print(f"Error navigating to next page: {e}")
            return False
            
    def save_candidates(self, candidates: List[Dict]) -> int:
        """
        Save candidates to MongoDB
        
        Args:
            candidates: List of candidate dictionaries
            
        Returns:
            Number of new candidates inserted
        """
        if not candidates:
            return 0
            
        inserted_count = 0
        updated_count = 0
        
        for candidate in candidates:
            try:
                if 'antler_profile_url' in candidate:
                    result = self.collection.update_one(
                        {'antler_profile_url': candidate['antler_profile_url']},
                        {'$set': candidate},
                        upsert=True
                    )
                else:
                    result = self.collection.update_one(
                        {'name': candidate['name']},
                        {'$set': candidate},
                        upsert=True
                    )
                    
                if result.upserted_id:
                    inserted_count += 1
                elif result.modified_count > 0:
                    updated_count += 1
                    
            except errors.DuplicateKeyError:
                updated_count += 1
            except Exception as e:
                print(f"Error saving candidate {candidate.get('name', 'Unknown')}: {e}")
                
        print(f"Saved {inserted_count} new candidates, updated {updated_count} existing")
        return inserted_count
        
    def scrape(self, max_pages: int = 2):
        """
        Main scraping function
        
        Args:
            max_pages: Maximum number of pages to scrape
        """
        try:
            self.setup_driver()
            self.setup_mongodb()
            
            if not self.login_if_needed():
                print("Login failed. Exiting.")
                return
                
            all_candidates = []
            
            for page_num in range(1, max_pages + 1):
                print(f"\n--- Scraping page {page_num} ---")
                
                if page_num == 1:
                    if not self.wait_for_candidates_to_load():
                        print("Failed to load candidates on first page")
                        break
                        
                candidates = self.scrape_current_page()
                print(f"Found {len(candidates)} candidates on page {page_num}")
                all_candidates.extend(candidates)
                
                if page_num < max_pages:
                    if not self.navigate_to_next_page():
                        print(f"Could not navigate to page {page_num + 1}. Stopping.")
                        break
                    time.sleep(2)
                    
            print(f"\n--- Scraping Complete ---")
            print(f"Total candidates found: {len(all_candidates)}")
            
            if all_candidates:
                self.save_candidates(all_candidates)
                
            total_in_db = self.collection.count_documents({})
            print(f"Total candidates in database: {total_in_db}")
            
        except Exception as e:
            print(f"Scraping error: {e}")
            raise
        finally:
            self.cleanup()
            
    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
            print("Browser closed")
        if self.db_client:
            self.db_client.close()
            print("Database connection closed")
            

def main():
    """Main entry point"""
    print("=== Antler Hub Candidate Scraper ===\n")
    
    headless = input("Run in headless mode? (y/n, default: n): ").lower() == 'y'
    max_pages = input("Number of pages to scrape (default: 2): ").strip()
    max_pages = int(max_pages) if max_pages.isdigit() else 2
    
    scraper = AntlerScraper(headless=headless)
    
    try:
        scraper.scrape(max_pages=max_pages)
        print("\nScraping completed successfully!")
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user")
    except Exception as e:
        print(f"\nError during scraping: {e}")
        sys.exit(1)
        

if __name__ == "__main__":
    main()