from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, StaleElementReferenceException
import time
import json
import csv

def initialize_driver():
    """Initializes the Selenium WebDriver."""
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless') # Uncomment if you want to run in headless mode
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--start-maximized')
    driver = webdriver.Chrome(options=options)
    return driver

def get_field_value(driver, label_text, parent_xpath=".", timeout=7):
    """
    Generic function to find a label and then extract the value from its sibling or parent.
    Adjusted to be more robust by looking for the nearest text-containing element.
    """
    try:
        # Find the label element
        label_element_xpath = f"{parent_xpath}//label[contains(text(), '{label_text}')]"
        label_element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, label_element_xpath))
        )

        # Try to find the value in different ways:
        # 1. Immediately following strong tag (most common for your site)
        try:
            value_element = label_element.find_element(By.XPATH, "./following-sibling::strong")
            value = value_element.text.strip()
            if value and value.lower() != '--': return value
        except:
            pass

        # 2. Immediately following div/span (might be for some cases)
        try:
            value_element = label_element.find_element(By.XPATH, "./following-sibling::*[self::div or self::span]")
            value = value_element.text.strip()
            if value and value.lower() != '--': return value
        except:
            pass

        # 3. Try to find the content within the parent 'd-flex align-items-center mb-3' div
        #    This covers the overall container for the label and its value.
        try:
            parent_div = label_element.find_element(By.XPATH, "./ancestor::div[contains(@class, 'details-project')]")
            # Get all text from this parent div, then clean it up to isolate the value
            full_text = parent_div.text
            # Remove the label text from the full text to get the value
            value = full_text.replace(label_text, '').strip()
            # Clean up any residual newlines or extra spaces that might result from replacing label
            value = ' '.join(value.split())
            if value and value.lower() != '--': return value
        except:
            pass

        return ""
    except Exception as e:
        return ""


def scrape_project_details(driver):
    """
    Scrapes detailed information from a single project details page.
    This function assumes it's ALREADY on the project details page.
    """
    project_data = {
        "Rera Regd. No": "",
        "Project Name": "",
        "Promoter Name": "",
        "Promoter Address": "",
        "GST No": ""
    }

    print("DEBUGGING NEW PAGE CONTENT")
    print(f"Current URL: {driver.current_url}")
    print(f"Page Title: {driver.title}")

    try:
        # --- Wait for the loading overlay to disappear ---
        WebDriverWait(driver, 25).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, "ngx-ui-loader .ngx-overlay"))
        )
        print("✓ Loading overlay disappeared.")
        time.sleep(1)
    except TimeoutException:
        print("Loading overlay did not disappear in time. Proceeding anyway, but extraction might fail.")
    except Exception as e:
        print(f"Error waiting for loading overlay: {e}")


    # --- Extract Project Name ---
    project_data["Project Name"] = get_field_value(driver, "Project Name")
    if project_data["Project Name"]:
        print(f"✓ Found Project Name: {project_data['Project Name']}")
    else:
        print("Could not extract Project Name.")

    # --- Extract Rera Regd. No ---
    project_data["Rera Regd. No"] = get_field_value(driver, "RERA Regd. No.")
    if project_data["Rera Regd. No"]:
        print(f"✓ Found Rera Regd. No: {project_data['Rera Regd. No']}")
    else:
        print("Could not extract Rera Regd. No.")

    # --- Extract Promoter Details (Company Name, Registered Office Address, GST No) ---
    print("\n Looking for Promoter Details...")
    try:
        # Click the 'Promoter Details' tab
        promoter_tab = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'nav-link') and contains(text(), 'Promoter Details')]"))
        )
        print("✓ Found 'Promoter Details' tab, clicking...")
        driver.execute_script("arguments[0].click();", promoter_tab)

        # Wait for the Promoter Details content to load/become visible
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "app-promoter-details"))
        )
        print("✓ 'Promoter Details' section is visible (or its parent element is present).")
        # Wait for any potential loader to disappear after tab click
        WebDriverWait(driver, 15).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, "ngx-ui-loader .ngx-overlay"))
        )
        time.sleep(1.5)

        # Now, attempt to extract Promoter Name, Address, GST No. using the robust function
        promoter_section_xpath = "//app-promoter-details"

        project_data["Promoter Name"] = get_field_value(driver, "Company Name", parent_xpath=promoter_section_xpath)
        if project_data["Promoter Name"]:
            print(f"✓ Found Promoter Name: {project_data['Promoter Name']}")
        else:
            print("Could not extract Promoter Name (Company Name).")

        project_data["Promoter Address"] = get_field_value(driver, "Registered Office Address", parent_xpath=promoter_section_xpath)
        if project_data["Promoter Address"]:
            print(f"Found Promoter Address: {project_data['Promoter Address']}")
        else:
            print("Could not extract Promoter Address (Registered Office Address).")

        project_data["GST No"] = get_field_value(driver, "GST No.", parent_xpath=promoter_section_xpath)
        if project_data["GST No"]:
            print(f"Found GST No: {project_data['GST No']}")
        else:
            print("Could not extract GST No from Promoter Details. It might not be available or is in a different section.")

    except TimeoutException as e:
        print(f"'Promoter Details' tab not found or its content did not load in time: {e}")
    except Exception as e:
        print(f"Error during Promoter Details extraction (tab click or content search): {e}")

    return project_data

def main():
    driver = None
    all_projects_data = []
    max_projects_to_scrape = 6

    try:
        driver = initialize_driver()
        list_page_url = "https://rera.odisha.gov.in/projects/project-list"
        driver.get(list_page_url)
        print(f"Loading: {list_page_url}")
        print("ChromeDriver initialized successfully")
        print(f"Starting to scrape top {max_projects_to_scrape} projects...")

        try:
            WebDriverWait(driver, 25).until(
                EC.invisibility_of_element_located((By.CSS_SELECTOR, "ngx-ui-loader .ngx-overlay"))
            )
            print("✓ List page loading overlay disappeared.")
            time.sleep(2)
        except TimeoutException:
            print("List page loading overlay did not disappear in time. Proceeding anyway.")

        view_details_buttons = WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.XPATH, "//a[contains(text(), 'View Details')]"))
        )
        print(f"✓ Found {len(view_details_buttons)} 'View Details' buttons.")

        for i in range(min(max_projects_to_scrape, len(view_details_buttons))):
            print(f"\n--- Scraping Project {i + 1} of {min(max_projects_to_scrape, len(view_details_buttons))} ---")
            
            project_list_url_before_click = driver.current_url

            try:
                current_button = WebDriverWait(driver, 15).until(
                    EC.presence_of_all_elements_located((By.XPATH, "//a[contains(text(), 'View Details')]"))
                )[i]
                print(f"✓ Clicking View Details button for project {i+1}...")
                driver.execute_script("arguments[0].click();", current_button)
            except (ElementClickInterceptedException, StaleElementReferenceException) as e:
                print(f"Click failed for project {i+1} ({type(e).__name__}). Skipping this project.")
                driver.get(list_page_url)
                continue
            except Exception as e:
                print(f"Unexpected error clicking button for project {i+1}: {e}. Skipping this project.")
                driver.get(list_page_url)
                continue

            try:
                WebDriverWait(driver, 25).until(EC.url_changes(project_list_url_before_click))
                print("Navigated to new page!")
            except TimeoutException:
                print(f"Navigation to details page timed out for project {i+1}. Skipping.")
                driver.get(list_page_url)
                continue

            print("\n EXTRACTING PROJECT DATA FROM PAGE")
            project_details = scrape_project_details(driver)
            all_projects_data.append(project_details)

            print("\n EXTRACTED DATA FOR CURRENT PROJECT:")
            for key, value in project_details.items():
                print(f"  {key}: {value if value else 'Not Found'}")

            print("\n Navigating back to project list page...")
            driver.back()
            try:
                WebDriverWait(driver, 25).until(EC.url_to_be(list_page_url))
                print("Successfully navigated back to list page.")
                WebDriverWait(driver, 25).until(
                    EC.invisibility_of_element_located((By.CSS_SELECTOR, "ngx-ui-loader .ngx-overlay"))
                )
                time.sleep(2)
            except TimeoutException:
                print("Timed out waiting for list page to load after navigating back. Force reloading.")
                driver.get(list_page_url)
                WebDriverWait(driver, 25).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, "ngx-ui-loader .ngx-overlay")))
                time.sleep(2)

        print("\n All requested projects scraped!")

        json_output_filename = f"top_{min(max_projects_to_scrape, len(all_projects_data))}_projects_data.json"
        with open(json_output_filename, "w", encoding="utf-8") as f:
            json.dump(all_projects_data, f, indent=4, ensure_ascii=False)
        print(f"\n All results saved to {json_output_filename}")

        csv_output_filename = f"top_{min(max_projects_to_scrape, len(all_projects_data))}_projects_data.csv"
        if all_projects_data:
            fieldnames = all_projects_data[0].keys()
            with open(csv_output_filename, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for project in all_projects_data:
                    writer.writerow(project)
            print(f"All results also saved to {csv_output_filename}")
        else:
            print("No data collected to write to CSV.")

    except Exception as e:
        print(f"An error occurred in main execution: {e}")
    finally:
        if driver:
            print("Keeping browser open for 5 seconds for final inspection...")
            time.sleep(5)
            driver.quit()
            print("✓ Browser closed")

if __name__ == "__main__":
    main()