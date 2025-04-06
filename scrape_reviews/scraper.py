import csv
import json
import os
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import argparse
import tempfile

OUTPUT_DIR = "restaurant_reviews"
DEBUG_DIR = "debug"
MAX_REVIEWS_PER_RESTAURANT = 1000

def find_chrome_executable():
    possible_locations = [
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ]
    
    for location in possible_locations:
        if os.path.exists(location):
            print(f"Found Chrome/Chromium at: {location}")
            return location
    return "/usr/bin/chromium-browser"

def setup_driver():
    """Setup Chrome browser with appropriate options"""
    try:
        print("Setting up Chrome driver...")
        
        chrome_path = find_chrome_executable()
        chrome_options = Options()
        chrome_options.binary_location = chrome_path
        
        temp_dir = tempfile.mkdtemp(prefix="chrome_user_data_")
        chrome_options.add_argument(f"--user-data-dir={temp_dir}")
        
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--incognito")
        
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        chromedriver_path = "/usr/bin/chromedriver"
        print(f"Using chromedriver at: {chromedriver_path}")
        
        service = Service(executable_path=chromedriver_path)
        
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    except Exception as e:
        print(f"Error setting up driver: {e}")
        import traceback
        traceback.print_exc()
        return None

def handle_cookie_consent(driver, restaurant_name):
    """Handle cookie consent dialog if present"""
    try:
        cookie_button = driver.find_element(By.CSS_SELECTOR, "button[aria-label='Accept all']")
        if cookie_button and cookie_button.is_displayed():
            print("Clicking cookie accept button")
            cookie_button.click()
            time.sleep(1)
            return True
        return False
    
    except Exception as e:
        print(f"Error handling cookie consent: {e}")
        return False

def is_restaurant_detail_page(driver):
    """Check if the current page is already a restaurant detail page"""
    try:
        time.sleep(2)
        if "/maps/place/" in driver.current_url:
            return True

        try:
            header = driver.find_element(By.CSS_SELECTOR, "h1.DUwDvf")
            if header and header.text.strip():
                return True
        except:
            pass
    except Exception as e:
        print(f"Restaurant detail check failed: {e}")
    
    return False


def find_and_click_restaurant_result(driver, restaurant_name, address=None):
    """
    If not already on a restaurant detail page, search for and click the best matching result.
    """

    if is_restaurant_detail_page(driver):
        print("Already on a restaurant detail page; skipping click logic.")
        return True

    print(f"\nAttempting to find restaurant: {restaurant_name}")

    xpath = (
        f"//a[contains(@class, 'hfpxzc') and "
        f"contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{restaurant_name.lower()}')]"
    )
    
    potential_elements = driver.find_elements(By.XPATH, xpath)
    best_match = None
    best_score = 0
    
    for element in potential_elements:
        try:
            aria_label = element.get_attribute("aria-label")
            if aria_label and "sponsored" in aria_label.lower():
                print(f"Skipping sponsored result: {aria_label}")
                continue
            
            score = 0
            if aria_label:
                element_text = aria_label.lower()
                if restaurant_name.lower() == element_text:
                    score += 100
                elif restaurant_name.lower() in element_text:
                    score += 50
                if address:
                    for keyword in address.lower().split():
                        if keyword in element_text:
                            score += 10
            
            if score > best_score:
                best_score = score
                best_match = element
                print(f"New best match: {aria_label} with score {score}")
        except Exception as e:
            print(f"Error processing an element: {e}")
            continue

    if best_match:
        try:
            driver.execute_script("arguments[0].scrollIntoView(true);", best_match)
            time.sleep(0.5)
            best_match.click()
            print("Clicked on the best matching restaurant result.")
            time.sleep(2)
            return True
        except Exception as e:
            print(f"Error clicking the best match: {e}")
            return False

    print("No suitable, non-sponsored restaurant result found.")
    return False



def extract_restaurant_info(driver):
    """Extract basic information about the restaurant"""
    info = {
        "name": "",
        "rating": "",
        "address": ""
    }
    
    try:
        name_selectors = [
            "h1.fontHeadlineLarge",
            "h1",
            "div.DUwDvf"
        ]
        
        for selector in name_selectors:
            try:
                name_element = driver.find_element(By.CSS_SELECTOR, selector)
                if name_element and name_element.text.strip():
                    raw_name = name_element.text.strip()
                    clean_name = raw_name.replace("Sponsored", "").strip()
                    if clean_name.startswith("\n"):
                        clean_name = clean_name[1:].strip()
                    
                    info["name"] = clean_name
                    print(f"Found restaurant name: {info['name']}")
                    break
            except:
                continue
        
        rating_selectors = [
            "div.fontBodyMedium span.fontTitleSmall",
            "span.fontTitleSmall[aria-hidden='true']",
            "div.F7nice span",
            "span.section-star-display",
            "div.jANrlb div.fontDisplayLarge"
        ]
        
        for selector in rating_selectors:
            try:
                rating_element = driver.find_element(By.CSS_SELECTOR, selector)
                if rating_element and rating_element.text.strip():
                    rating_text = rating_element.text.strip()
                    rating_match = re.search(r'(\d+\.\d+|\d+)', rating_text)
                    if rating_match:
                        info["rating"] = rating_match.group(1)
                        print(f"Found restaurant rating: {info['rating']}")
                        break
            except:
                continue
        
        address_selectors = [
            "button[data-item-id='address']",
            "button[aria-label*='Address']",
            "div[data-tooltip='Copy address']",
            "div.rogA2c",
            "span.section-info-text"
        ]
        
        for selector in address_selectors:
            try:
                address_element = driver.find_element(By.CSS_SELECTOR, selector)
                if address_element and address_element.text.strip():
                    info["address"] = address_element.text.strip()
                    print(f"Found restaurant address: {info['address']}")
                    break
            except:
                continue
                
    except Exception as e:
        print(f"Error extracting restaurant info: {e}")
    
    return info

def scroll_once(driver):
    try:
        review_elements = driver.find_elements(By.CSS_SELECTOR, "div.jftiEf, div[data-review-id]")
        if review_elements:
            last_element = review_elements[-1]
            driver.execute_script("arguments[0].scrollIntoView(true);", last_element)
        time.sleep(1)
    except Exception as e:
        print("Error during scroll_once:", e)

def extract_reviews_incrementally(driver, max_reviews=1000, scroll_pause_time=2, max_attempts_no_new=1):
    """
    Incrementally scroll and extract reviews.
    
    This routine:
      1. Extracts reviews from the current DOM via JS.
      2. Deduplicates them using a composite key.
      3. Calls scroll_once(driver) to load more reviews.
      4. Repeats until max_reviews are reached or several rounds yield no new reviews.
    """
    collected_reviews = {}
    attempts_no_new = 0
    extraction_round = 0

    while len(collected_reviews) < max_reviews and attempts_no_new < max_attempts_no_new:
        extraction_round += 1
        print(f"\nExtraction round {extraction_round}")
        
        js_reviews_data = driver.execute_script("""
            function extractAllReviews() {
                const reviewElements = Array.from(document.querySelectorAll('div.jftiEf, div[data-review-id]'));
                console.log(`Found ${reviewElements.length} review elements`);
                if (reviewElements.length === 0) return [];
                const reviewsData = [];
                reviewElements.forEach(element => {
                    try {
                        const review = {
                            reviewerName: "Unknown",
                            rating: 0,
                            text: "",
                            date: ""
                        };
                        const nameElement = element.querySelector('div.d4r55, div.X5PpBb, [class*="title"], .lMbq3e');
                        if (nameElement && nameElement.textContent) {
                            review.reviewerName = nameElement.textContent.trim();
                        }
                        const ratingElement = element.querySelector('[aria-label*="star"], [aria-label*="stars"]');
                        if (ratingElement) {
                            const ariaLabel = ratingElement.getAttribute('aria-label');
                            if (ariaLabel) {
                                const match = ariaLabel.match(/(\\d+)/);
                                if (match) {
                                    review.rating = parseInt(match[1], 10);
                                }
                            }
                        }
                        let textElement = element.querySelector('.wiI7pd, .review-full-text, [class*="text-container"]');
                        if (textElement && textElement.textContent) {
                            review.text = textElement.textContent.trim();
                        } else {
                            let longestText = "";
                            element.querySelectorAll('*').forEach(el => {
                                if (el.children.length > 0 || el.tagName === 'BUTTON' || el.tagName === 'INPUT') return;
                                const txt = el.textContent.trim();
                                if (txt.length > 30 && txt.length > longestText.length &&
                                    !txt.includes('star') && !txt.includes('ago')) {
                                    longestText = txt;
                                }
                            });
                            review.text = longestText;
                        }
                        const dateElement = element.querySelector('.rsqaWe, .dehysf, [class*="date"]');
                        if (dateElement && dateElement.textContent) {
                            review.date = dateElement.textContent.trim();
                        }
                        if (review.reviewerName !== "Unknown" || review.rating > 0 || review.text) {
                            reviewsData.push(review);
                        }
                    } catch (e) {
                        console.error('Error extracting review:', e);
                    }
                });
                return reviewsData;
            }
            return extractAllReviews();
        """)
        if js_reviews_data is None:
            js_reviews_data = []
        
        round_count_before = len(collected_reviews)

        # brute force deduplication
        for js_review in js_reviews_data:
            review = {
                "reviewer_name": js_review.get("reviewerName", "Unknown"),
                "rating": js_review.get("rating", 0),
                "text": js_review.get("text", ""),
                "date": js_review.get("date", "")
            }
            key = (review["reviewer_name"], review["text"], review["date"])
            if key not in collected_reviews:
                collected_reviews[key] = review
        
        round_count_after = len(collected_reviews)
        new_reviews = round_count_after - round_count_before
        print(f"Unique reviews collected so far: {round_count_after} (+{new_reviews} new)")
        
        if new_reviews == 0:
            attempts_no_new += 1
            print(f"No new reviews in this round. (Attempt {attempts_no_new}/{max_attempts_no_new})")
        else:
            attempts_no_new = 0
        
        if len(collected_reviews) >= max_reviews:
            break
        
        print("Scrolling for more reviews...")
        scroll_once(driver)
        time.sleep(scroll_pause_time)
    
    final_reviews = list(collected_reviews.values())[:max_reviews]
    print(f"\nExtraction complete. Total unique reviews collected: {len(final_reviews)}")
    return final_reviews



def find_and_click_more_reviews(driver, debug=False):
    """Find and click the 'More reviews' button if it exists"""
    print("Looking for 'More reviews' button...")
    
    try:
        if debug:
            os.makedirs(DEBUG_DIR, exist_ok=True)
            driver.save_screenshot(f"{DEBUG_DIR}/before_more_reviews_click.png")
            
            with open(f"{DEBUG_DIR}/before_more_reviews.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
        
        more_reviews_selectors = [
            "button span:contains('More reviews')",
            "div.m6QErb button span:contains('More reviews')",
            "div.m6QErb button:has(span:contains('More reviews'))",
            "button[jsaction*='pane.rating.moreReviews']",
            "button[aria-label*='review']",
            "button:has(span:contains('review'))"
        ]
        
        found = driver.execute_script("""
            function findMoreReviewsButton() {
                const specificSelector = document.querySelector("div.m6QErb > div > button > span");
                if (specificSelector && 
                    specificSelector.textContent && 
                    specificSelector.textContent.toLowerCase().includes('more review')) {
                    console.log("Found by specific selector");
                    return specificSelector.parentNode;
                }
                
                const spans = Array.from(document.querySelectorAll('span'));
                for (const span of spans) {
                    if (span.textContent && 
                        span.textContent.toLowerCase().includes('more review')) {
                        
                        let parent = span.parentElement;
                        while (parent && parent.tagName !== 'BUTTON') {
                            parent = parent.parentElement;
                            if (!parent) break;
                        }
                        
                        if (parent && parent.tagName === 'BUTTON') {
                            console.log("Found More reviews button by text content");
                            return parent;
                        }
                    }
                }
                
                const buttons = Array.from(document.querySelectorAll('button'));
                for (const button of buttons) {
                    const ariaLabel = button.getAttribute('aria-label');
                    if (ariaLabel && 
                        ariaLabel.toLowerCase().includes('review')) {
                        console.log("Found button by aria-label");
                        return button;
                    }
                }
                
                return null;
            }
            
            const button = findMoreReviewsButton();
            if (button) {
                button.scrollIntoView();
                setTimeout(() => {
                    try {
                        button.click();
                        console.log("Clicked More reviews button");
                        return true;
                    } catch(e) {
                        console.error("Click failed", e);
                        return false;
                    }
                }, 500);
                return true;
            }
            return false;
        """)
        
        if found:
            print("Successfully found and clicked 'More reviews' button using JavaScript")
            time.sleep(3)
            
            if debug:
                driver.save_screenshot(f"{DEBUG_DIR}/after_more_reviews_click.png")
            return True
        
        print("Could not find 'More reviews' button")
        return False
        
    except Exception as e:
        print(f"Error finding 'More reviews' button: {e}")
        return False

def process_restaurant(driver, restaurant_name, restaurant_data, debug=False):
    """Process a single restaurant to extract reviews"""
    try:
        address = restaurant_data.get("address", "").strip()
        
        if address:
            match = re.match(r"^(.+?)\s+(\d+)$", address)
            if match:
                street_name = match.group(1)
                street_number = match.group(2)
                address = f"{street_number} {street_name}"
                print(f"Normalized address to '{address}'")
        
        search_parts = [restaurant_name]
        if address:
            search_parts.append(address)
        cuisine = restaurant_data.get("cuisine", "").strip()
        if cuisine:
            search_parts.append(cuisine)
        search_parts.append("London")
        
        search_query = " ".join(search_parts)
        print(f"Searching for: {search_query}")
        
        maps_url = f"https://www.url.com/maps/search/{search_query.replace(' ', '+')}" # definitely dont use google maps here!!
        
        if debug:
            restaurant_debug_dir = f"{DEBUG_DIR}/{restaurant_name.replace(' ', '_')}"
            os.makedirs(restaurant_debug_dir, exist_ok=True)
        
        driver.get(maps_url)
        
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        print("Page loaded")
        
        if debug:
            driver.save_screenshot(f"{restaurant_debug_dir}/01_initial.png")
            with open(f"{restaurant_debug_dir}/01_search_page.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
        
        handle_cookie_consent(driver, restaurant_name)
        
        click_attempts = 0
        max_attempts = 3
        details_found = False
        
        while click_attempts < max_attempts and not details_found:
            click_attempts += 1
            
            if click_attempts > 1:
                print(f"Retry attempt {click_attempts}/{max_attempts}")
                driver.refresh()
                time.sleep(3)
                handle_cookie_consent(driver, restaurant_name)
            
            if not find_and_click_restaurant_result(driver, restaurant_name, address=address):
                print("Could not find restaurant result to click")
                continue
            
            try:
                details_selectors = [
                    "h1.DUwDvf",
                    "div.skqShb",
                    "div.rogA2c",
                    "button[data-item-id='address']",
                    "div.m6QErb"
                ]
                
                for selector in details_selectors:
                    try:
                        WebDriverWait(driver, 8).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        details_found = True
                        break
                    except:
                        pass
                
                if details_found:
                    time.sleep(2)
                    break
                else:
                    print("Details page didn't load properly, retrying...")
                    if debug:
                        driver.save_screenshot(f"{restaurant_debug_dir}/02_failed_details_{click_attempts}.png")
            except Exception as e:
                print(f"Error waiting for details page: {e}")
        
        if not details_found:
            print("Could not load restaurant details page after multiple attempts")
            return [], restaurant_data
        
        if debug:
            driver.save_screenshot(f"{restaurant_debug_dir}/03_details_page.png")
            with open(f"{restaurant_debug_dir}/03_details_page.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            
        restaurant_info = extract_restaurant_info(driver)
        print(f"Restaurant info: {restaurant_info}")
        
        reviews = []
        
        print("Attempting to find and click 'More reviews' button...")
        if find_and_click_more_reviews(driver, debug=debug):
            print("Successfully navigated to reviews via 'More reviews' button")
            if debug:
                driver.save_screenshot(f"{restaurant_debug_dir}/04_after_more_reviews_click.png")
                with open(f"{restaurant_debug_dir}/04_after_more_reviews_click.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
            
            reviews = extract_reviews_incrementally(driver, max_reviews=MAX_REVIEWS_PER_RESTAURANT)
        
        for review in reviews:
            review["restaurant_name"] = restaurant_info.get("name", restaurant_name)
            review["restaurant_rating"] = restaurant_info.get("rating", "Unknown")
            review["restaurant_address"] = restaurant_info.get("address", restaurant_data.get("address", "London"))
            review["restaurant_cuisine"] = restaurant_data.get("cuisine", "")
        
        return reviews, restaurant_info
            
    except Exception as e:
        print(f"Error processing restaurant: {e}")
        import traceback
        traceback.print_exc()
        return [], restaurant_data

def main():
    """Main function to run the scraper"""
    print("Initializing Google Maps Review Scraper...")
    
    parser = argparse.ArgumentParser(description='Google Maps Restaurant Review Scraper')
    parser.add_argument('--csv', type=str, default="restaurants.csv", 
                        help='CSV file with restaurant data (default: restaurants.csv)')
    parser.add_argument('--limit', type=int, default=1000, 
                        help='Maximum number of restaurants to process (default: 1000)')
    parser.add_argument('--start', type=int, default=0,
                        help='Index of first restaurant to process (default: 0, starts from beginning)')
    parser.add_argument('--debug', action='store_true', 
                        help='Enable debug mode with screenshots and HTML dumps')
    args = parser.parse_args()
        
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if args.debug:
        os.makedirs(DEBUG_DIR, exist_ok=True)
    
    driver = None
    try:
        driver = setup_driver()
        if not driver:
            print("Driver setup failed. Exiting...")
            return
            
        print("Chrome driver setup complete")
                
        csv_file = args.csv
        if os.path.exists(csv_file):
            print(f"Reading restaurants from {csv_file}")
            with open(csv_file, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                restaurants = list(reader)
                print(f"Found {len(restaurants)} restaurants in CSV")
                
                if args.start > 0:
                    if args.start < len(restaurants):
                        print(f"Starting from restaurant at index {args.start}")
                        restaurants = restaurants[args.start:]
                    else:
                        print(f"Start index {args.start} is out of range (max: {len(restaurants)-1})")
                        return
                
                if args.limit and args.limit < len(restaurants):
                    print(f"Processing {args.limit} restaurants")
                    restaurants = restaurants[:args.limit]
        else:
            return
        
        for i, restaurant_data in enumerate(restaurants):
            global_index = i + args.start
            
            restaurant_name = restaurant_data.get("name", "")
            if not restaurant_name:
                print(f"Skipping restaurant {global_index+1} - invalid name")
                continue
                
            print(f"\n{'='*50}")
            print(f"Processing restaurant {global_index+1}/{len(restaurants)+(args.start or 0)}: {restaurant_name}")
            print(f"{'='*50}")
            
            reviews, info = process_restaurant(driver, restaurant_name, restaurant_data, debug=args.debug)
            
            for key, value in info.items():
                if value and key in restaurant_data and not restaurant_data[key]:
                    restaurant_data[key] = value
            
            if reviews:
                filename = f"{OUTPUT_DIR}/{restaurant_name.replace(' ', '_')}_reviews.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(reviews, f, indent=2, ensure_ascii=False)
                print(f"Saved {len(reviews)} reviews to {filename}")
            
        
    except Exception as e:
        print(f"Error in main function: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            try:
                driver.quit()
                print("Browser closed")
            except:
                pass

if __name__ == "__main__":
    main()