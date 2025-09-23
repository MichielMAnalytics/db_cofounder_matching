#!/usr/bin/env python3
"""
Antler Hub Phone Number Scraper
Scrapes phone numbers from individual candidate profiles and optionally updates MongoDB
"""

import os
import sys
import time
import getpass
import argparse
from datetime import datetime, timezone
from typing import List, Dict, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from pymongo import MongoClient, errors
from dotenv import load_dotenv


class AntlerPhoneScraper:
    """Scraper for Antler Hub candidate phone numbers"""
    
    def __init__(self, headless: bool = False, save_to_db: bool = False):
        """
        Initialize the scraper
        
        Args:
            headless: Run browser in headless mode (default: False for debugging)
            save_to_db: Whether to save results to database (default: False)
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
        self.save_to_db = save_to_db
        self.results = []  # Store results for output
        
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
                
                # Navigate to founders page
                print(f"Navigating to founders page: {self.founders_url}")
                self.driver.get(self.founders_url)
                time.sleep(4)
                    
            except Exception as e:
                print(f"Login process encountered an error: {e}")
                print("You may need to login manually in the browser window.")
                input("Press Enter after you've logged in manually...")
                # After manual login, navigate to founders page
                self.driver.get(self.founders_url)
                time.sleep(3)
                
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
        
    def get_candidates_without_phone(self) -> List[Dict]:
        """
        Get list of candidates from MongoDB that don't have phone numbers
        
        Returns:
            List of candidate documents without phone numbers
        """
        # Find candidates without phone numbers or with empty phone field
        # Exclude the test account
        query = {
            '$and': [
                {'name': {'$ne': 'Chris (Test) Klam'}},
                {'$or': [
                    {'phone': {'$exists': False}},
                    {'phone': ''},
                    {'phone': None}
                ]}
            ]
        }
        
        candidates = list(self.collection.find(query))
        print(f"Found {len(candidates)} candidates without phone numbers")
        return candidates
        
    def get_candidate_contact_info(self, name: str) -> Optional[str]:
        """
        Get contact info for a candidate by clicking Contact Info button
        
        Args:
            name: Name of the candidate
            
        Returns:
            Phone number if found, None otherwise
        """
        try:
            # Handle special case for Michiel
            search_name = name
            if name == 'Michiel Voortman':
                try:
                    elem = self.driver.find_element(By.XPATH, "//p[@class='css-5gltw' and text()='Michiel(you)']")
                    if elem:
                        search_name = 'Michiel(you)'
                except:
                    pass
            
            # Find all candidate containers
            containers = self.driver.find_elements(By.CSS_SELECTOR, "div.css-iuxpug")
            
            for container in containers:
                try:
                    # Check if this container has the candidate's name
                    name_elem = container.find_element(By.CSS_SELECTOR, "p.css-5gltw")
                    if name_elem.text.strip() != search_name:
                        continue
                    
                    # Found the right container, look for Contact Info button
                    try:
                        contact_btn = container.find_element(By.XPATH, ".//button[contains(., 'Contact Info') or contains(., 'Contact info')]")
                        
                        # Scroll into view
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", contact_btn)
                        time.sleep(1)
                        
                        # Click using JavaScript to avoid interception
                        self.driver.execute_script("arguments[0].click();", contact_btn)
                        time.sleep(2)
                        
                        # Extract phone from the revealed contact info
                        phone = self.extract_phone_from_container(container)
                        if phone:
                            return phone
                        
                        # Check if a modal opened with contact info
                        try:
                            modal = self.driver.find_element(By.CSS_SELECTOR, "[role='dialog'], .modal, .popup")
                            if modal.is_displayed():
                                phone = self.extract_phone_from_element(modal)
                                if phone:
                                    return phone
                        except:
                            pass
                        
                        return None
                        
                    except:
                        # No Contact Info button - try to find phone directly in container
                        phone = self.extract_phone_from_container(container)
                        if phone:
                            return phone
                        
                        print(f"No contact info available for {name}")
                        return None
                        
                except:
                    continue
            
            # Candidate not found on this page
            return None
            
        except:
            return None
            
    def extract_phone_from_container(self, container) -> Optional[str]:
        """Extract phone from a web element container"""
        try:
            html = container.get_attribute('innerHTML')
            soup = BeautifulSoup(html, 'lxml')
            return self.extract_phone_from_soup(soup)
        except:
            return None
            
    def extract_phone_from_element(self, element) -> Optional[str]:
        """Extract phone from a web element"""
        try:
            html = element.get_attribute('innerHTML')
            soup = BeautifulSoup(html, 'lxml')
            return self.extract_phone_from_soup(soup)
        except:
            return None
            
    def extract_phone_from_soup(self, soup) -> Optional[str]:
        """Extract phone number from BeautifulSoup object"""
        import re
        phone_pattern = re.compile(r'[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,5}[-\s\.]?[0-9]{1,5}')
        
        # Check all text elements
        all_text = soup.get_text()
        matches = phone_pattern.findall(all_text)
        
        for match in matches:
            # Validate it's a reasonable phone number (at least 7 digits)
            digits_only = re.sub(r'\D', '', match)
            if len(digits_only) >= 7:
                return match
        
        # Look for tel: links
        tel_links = soup.find_all('a', href=re.compile(r'^tel:'))
        if tel_links:
            for link in tel_links:
                phone = link.get('href').replace('tel:', '').strip()
                if phone:
                    return phone
        
        return None
            
    def extract_phone_from_profile(self) -> Optional[str]:
        """
        Extract phone number from the current profile page
        
        Returns:
            Phone number string or None if not found
        """
        try:
            # Wait for profile to fully load
            time.sleep(2)
            
            # Parse the page
            soup = BeautifulSoup(self.driver.page_source, 'lxml')
            
            # Look for phone number in various possible locations
            # Strategy 1: Look for elements with phone-like text patterns
            import re
            phone_pattern = re.compile(r'[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,5}[-\s\.]?[0-9]{1,5}')
            
            # Check all text elements
            all_text_elements = soup.find_all(['p', 'span', 'div'], string=True)
            
            for element in all_text_elements:
                text = element.get_text(strip=True)
                if text:
                    # Look for phone patterns
                    match = phone_pattern.search(text)
                    if match:
                        phone = match.group(0)
                        # Validate it's a reasonable phone number (at least 7 digits)
                        digits_only = re.sub(r'\D', '', phone)
                        if len(digits_only) >= 7:
                            print(f"Found phone number: {phone}")
                            return phone
            
            # Strategy 2: Look for specific phone-related labels
            phone_labels = ['Phone', 'Mobile', 'Cell', 'Contact', 'Number', 'Tel']
            for label in phone_labels:
                # Look for label followed by number
                label_element = soup.find(string=re.compile(label, re.IGNORECASE))
                if label_element:
                    parent = label_element.parent
                    if parent:
                        # Check parent and siblings for phone number
                        parent_text = parent.get_text(strip=True)
                        match = phone_pattern.search(parent_text)
                        if match:
                            phone = match.group(0)
                            digits_only = re.sub(r'\D', '', phone)
                            if len(digits_only) >= 7:
                                print(f"Found phone number near '{label}': {phone}")
                                return phone
            
            # Strategy 3: Look for tel: links
            tel_links = soup.find_all('a', href=re.compile(r'^tel:'))
            if tel_links:
                for link in tel_links:
                    phone = link.get('href').replace('tel:', '').strip()
                    if phone:
                        print(f"Found phone number in tel link: {phone}")
                        return phone
            
            print("No phone number found on profile")
            return None
            
        except Exception as e:
            print(f"Error extracting phone number: {e}")
            return None
            
    def go_back_to_list(self):
        """Navigate back to the candidates list"""
        try:
            # Try using browser back button
            self.driver.back()
            time.sleep(3)
        except:
            # If back doesn't work, navigate directly
            self.driver.get(self.founders_url)
            time.sleep(4)
            
    def navigate_to_page(self, page_num: int) -> bool:
        """
        Navigate to a specific page number (same logic as main scraper)
        
        Args:
            page_num: Page number to navigate to
            
        Returns:
            True if successful, False otherwise
        """
        if page_num == 1:
            return True  # Already on page 1
            
        try:
            print(f"Looking for page {page_num} button...")
            
            # Strategy 1: Look for button with specific page number
            try:
                page_button = self.driver.find_element(By.XPATH, f"//button[.//div[text()='{page_num}']]")
                if page_button.is_enabled() and page_button.is_displayed():
                    print(f"Found page {page_num} button, clicking...")
                    # Scroll into view and use JavaScript click
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", page_button)
                    time.sleep(1)
                    self.driver.execute_script("arguments[0].click();", page_button)
                    time.sleep(4)
                    return True
            except:
                pass
            
            # Strategy 2: Look for any button containing the page number
            try:
                buttons_with_page = self.driver.find_elements(By.XPATH, f"//button[contains(text(), '{page_num}')]")
                for button in buttons_with_page:
                    if button.is_enabled() and button.is_displayed():
                        print(f"Found button with '{page_num}', clicking...")
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                        time.sleep(1)
                        self.driver.execute_script("arguments[0].click();", button)
                        time.sleep(4)
                        return True
            except:
                pass
            
            print(f"No page {page_num} button found")
            return False
                
        except Exception as e:
            print(f"Error navigating to page {page_num}: {e}")
            return False
            
    def update_candidate_phone(self, candidate_id, phone: str):
        """
        Update candidate's phone number in MongoDB (if save_to_db is True)
        
        Args:
            candidate_id: MongoDB document ID
            phone: Phone number to save
        """
        if self.save_to_db:
            try:
                result = self.collection.update_one(
                    {'_id': candidate_id},
                    {'$set': {'phone': phone}}
                )
                if result.modified_count > 0:
                    print(f"  → Saved to database")
            except Exception as e:
                print(f"Error updating phone in database: {e}")
            
    def scrape_current_page_phones(self) -> List[Dict]:
        """Scrape phone numbers from candidates on current page (only for those missing phone numbers)"""
        results = []
        
        print("Scraping phone numbers from current page...")
        
        # Find all candidate containers
        containers = self.driver.find_elements(By.CSS_SELECTOR, "div.css-iuxpug")
        print(f"Found {len(containers)} candidate containers")
        
        processed = 0
        skipped = 0
        
        for container in containers:
            try:
                # Get candidate name
                name_elem = container.find_element(By.CSS_SELECTOR, "p.css-5gltw")
                name = name_elem.text.strip()
                
                # Normalize Michiel(you) to Michiel Voortman
                if name == 'Michiel(you)':
                    name = 'Michiel Voortman'
                    print("Found 'Michiel(you)' - normalizing to 'Michiel Voortman'")
                
                # Skip test account
                if name == 'Chris (Test) Klam':
                    print("Skipping test account: Chris (Test) Klam")
                    continue
                
                # Check if this candidate already has a phone number in database
                existing_candidate = self.collection.find_one({'name': name})
                if existing_candidate and existing_candidate.get('phone') and existing_candidate.get('phone').strip():
                    print(f"Skipping {name}: already has phone {existing_candidate.get('phone')}")
                    skipped += 1
                    continue
                
                phone = None
                
                # Look for Contact Info button
                try:
                    contact_btn = container.find_element(By.XPATH, ".//button[contains(., 'Contact Info')]")
                    
                    # Scroll into view
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", contact_btn)
                    time.sleep(1)
                    
                    # Click using JavaScript to avoid interception
                    self.driver.execute_script("arguments[0].click();", contact_btn)
                    time.sleep(2)
                    
                    # Extract phone from the container after clicking
                    phone = self.extract_phone_from_container(container)
                    
                    print(f"Processed {name}: {phone if phone else 'NO PHONE'}")
                    
                except:
                    # No Contact Info button - try to find phone directly
                    phone = self.extract_phone_from_container(container)
                    print(f"No Contact Info button for {name}: {phone if phone else 'NO PHONE'}")
                
                results.append({
                    'name': name,
                    'phone': phone if phone else ''
                })
                processed += 1
                
            except Exception as e:
                print(f"Error processing container: {e}")
                continue
        
        print(f"Processed: {processed}, Skipped (already have phone): {skipped}")
        return results

    def scrape_phones(self):
        """Main function to scrape phone numbers for all candidates"""
        try:
            self.setup_driver()
            self.setup_mongodb()
            
            if not self.login_if_needed():
                print("Login failed. Exiting.")
                return
                
            print(f"\nStarting to scrape phone numbers...")
            if not self.save_to_db:
                print("(DRY RUN - Not saving to database. Use --save flag to save results)\n")
            
            all_results = []
            max_pages = 3  # Check up to 3 pages
            
            for page_num in range(1, max_pages + 1):
                print(f"\n--- Scraping page {page_num} ---")
                
                # Wait for candidates to load
                if not self.wait_for_candidates_to_load():
                    print(f"Failed to load candidates on page {page_num}")
                    break
                
                # Scrape phone numbers from current page
                page_results = self.scrape_current_page_phones()
                print(f"Found {len(page_results)} candidates on page {page_num}")
                all_results.extend(page_results)
                
                # Navigate to next page
                if page_num < max_pages:
                    if not self.navigate_to_page(page_num + 1):
                        print(f"Could not navigate to page {page_num + 1}. Stopping.")
                        break
                    time.sleep(3)
            
            # Process results and update database if needed
            phones_found = 0
            phones_not_found = 0
            
            for result in all_results:
                name = result['name']
                phone = result['phone']
                
                self.results.append({'name': name, 'phone': phone if phone else 'NO PHONE'})
                
                if self.save_to_db:
                    # Find candidate in database and update
                    candidate = self.collection.find_one({'name': name})
                    if candidate:
                        self.update_candidate_phone(candidate['_id'], phone)
                
                if phone:
                    phones_found += 1
                else:
                    phones_not_found += 1
            
            # Print results summary
            print(f"\n{'='*60}")
            print("RESULTS SUMMARY")
            print(f"{'='*60}")
            
            # Print all results in a clean format
            for result in self.results:
                name = result['name']
                phone = result['phone']
                if phone and phone not in ['NO PHONE', 'NOT FOUND - Could not click profile', 'NO PROFILE AVAILABLE', 'NOT FOUND - Candidate not in list']:
                    print(f"{name:<30} | {phone}")
                else:
                    print(f"{name:<30} | {phone}")
            
            print(f"\n{'='*60}")
            print(f"Phones found: {phones_found}")
            print(f"Phones not found: {phones_not_found}")
            print(f"Total processed: {phones_found + phones_not_found}")
            
            if not self.save_to_db:
                print("\n⚠️  Results were NOT saved to database (use --save flag to persist)")
            
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
    parser = argparse.ArgumentParser(description='Scrape phone numbers from Antler Hub candidate profiles')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--save', action='store_true', help='Save results to MongoDB database')
    
    args = parser.parse_args()
    
    print("=== Antler Hub Phone Number Scraper ===\n")
    
    if args.save:
        print("⚠️  Database saving is ENABLED (--save flag detected)")
    else:
        print("ℹ️  Running in DRY RUN mode (use --save to persist to database)")
    
    if args.headless:
        print("Running in headless mode")
    else:
        print("Running with visible browser (use --headless for headless mode)")
    
    print()
    
    scraper = AntlerPhoneScraper(headless=args.headless, save_to_db=args.save)
    
    try:
        scraper.scrape_phones()
        print("\nPhone scraping completed successfully!")
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user")
    except Exception as e:
        print(f"\nError during scraping: {e}")
        sys.exit(1)
        

if __name__ == "__main__":
    main()