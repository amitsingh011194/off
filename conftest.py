import os
import time
from datetime import datetime
from selenium.webdriver.support.ui import WebDriverWait
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

class MainPage:
    ACCOUNT_XPATH = "div[1]/div[1]/div[1]/div[4]/div[1]/button[1]"
    FILTER_FIELD_ID = "polaris-table-formfield-filter"
    BUCKET_ID = "link-self502-1750316646834-8007"
    USERNAME_NAME = "loginfmt"
    NEXT_BUTTON_ID = "idSIButton9"
    PASSWORD_NAME = "passwd"
    SIGNIN_TYPE = "submit"
    S3_DECRYPTED_FILES_URL = (
        "https://us-east-1.console.aws.amazon.com/s3/buckets/"
        "sb-utp1-tenant-1674e330-tenantbucket-qzttjz75pp8k"
        "?region=us-east-1&bucketType=general&prefix=etl/decrypted-files/&showversions=false"
    )
    RDS_QUERY_EDITOR_URL = "https://us-east-1.console.aws.amazon.com/rds/home?region=us-east-1#query-editor:"
    RDS_DROPDOWN_XPATH = "//button[@id='formField:rds-console-rhb:']"

    #def __init__(self, driver):
    #    self.driver = driver
    #    self.wait = WebDriverWait(driver, 10)

    #def open(self, url):
    #    self.driver.get(url)

    def __init__(self, headless=True):
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
 
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
 
    def open(self, url):
        self.driver.get(url)

    def enter_username(self, username):
        field = self.wait.until(EC.visibility_of_element_located((By.NAME, self.USERNAME_NAME)))
        field.clear()
        field.send_keys(username)

    def click_next_button(self):
        btn = self.wait.until(EC.element_to_be_clickable((By.ID, self.NEXT_BUTTON_ID)))
        btn.click()

    def enter_password(self, password):
        field = self.wait.until(EC.visibility_of_element_located((By.NAME, self.PASSWORD_NAME)))
        field.clear()
        field.send_keys(password)

    def click_sign_in_button(self):
        btn = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='submit']")))
        btn.click()

    def select_account(self):
        self.wait.until(EC.element_to_be_clickable((By.XPATH, f"//{self.ACCOUNT_XPATH}"))).click()

    def select_special_role_account(self):
        special_role_elem = self.wait.until(
            EC.element_to_be_clickable((By.XPATH, "//div[2]/div[1]/div[1]/div[1]/div[4]/div[1]/div[1]/div[1]/a[1]"))
        )
        special_role_elem.click()

    def select_s3(self):
        self.driver.get("https://us-east-1.console.aws.amazon.com/s3/home?region=us-east-1#")

    def enter_filter_field(self, text):
        field = self.wait.until(EC.visibility_of_element_located((By.ID, self.FILTER_FIELD_ID)))
        field.clear()
        field.send_keys(text)

    def select_upload_bucket(self):
        self.wait.until(EC.element_to_be_clickable((By.ID, self.BUCKET_ID))).click()

    def upload_all_files_in_folder(self, folder_path):
        files = [
            os.path.join(folder_path, f)
            for f in os.listdir(folder_path)
            if os.path.isfile(os.path.join(folder_path, f))
        ]
        if not files:
            raise Exception("No files found in folder!")
        file_input = self.wait.until(
            lambda driver: driver.find_element(By.XPATH, "//span[normalize-space()='Add files']")
        )
        file_input.send_keys('\n'.join(files))
        time.sleep(2)

    def open_s3_decrypted_files_folder(self):
        self.driver.get(self.S3_DECRYPTED_FILES_URL)

    def get_csv_files(self):
        file_elements = self.wait.until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "span[data-testid='file-name']"))
        )
        return [el.text for el in file_elements if el.text.endswith('.csv')]

    def take_screenshot(self, folder="screenshots", suffix=""):
        """
        Takes a screenshot and saves it to the specified folder with an optional suffix.
        Returns the full path to the saved screenshot.
        """
        if not os.path.exists(folder):
            os.makedirs(folder)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix_str = f"_{suffix}" if suffix else ""
        filename = os.path.join(folder, f"s3{suffix_str}_{timestamp}.png")
        self.driver.save_screenshot(filename)
        return filename

    def save_screenshot(self, folder="screenshots", suffix=""):
        """
        Alias for take_screenshot for compatibility with test code.
        """
        return self.take_screenshot(folder, suffix)

    def open_rds_query_editor(self):
        self.driver.get(self.RDS_QUERY_EDITOR_URL)
        print("Opened RDS Query Editor UI in browser")

    def wait_for_and_click_rds_dropdown(self, timeout=30):
        try:
            dropdown = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, self.RDS_DROPDOWN_XPATH))
            )
            dropdown.click()
            print("Dropdown clicked successfully")
        except Exception as e:
            print(f"Dropdown not found or not clickable: {e}")
            raise
    

# ================== Lambda Log Utility (outside the class) ==================

def save_latest_lambda_log_to_file(log_group, profile, region, folder):
    """
    Fetches the latest log stream and events for the given Lambda log group,
    and saves them to a timestamped file in the specified folder.
    """
    import subprocess
    import json

    def get_latest_log_stream(log_group_name, profile='qa', region='us-east-1'):
        cmd = [
            "aws", "logs", "describe-log-streams",
            "--log-group-name", log_group_name,
            "--order-by", "LastEventTime",
            "--descending",
            "--limit", "1",
            "--region", region,
            "--profile", profile
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Failed to describe log streams: {result.stderr}")
        streams = json.loads(result.stdout).get('logStreams', [])
        if not streams:
            raise Exception(f"No log streams found in {log_group_name}")
        return streams[0]['logStreamName']

    def get_log_events(log_group_name, log_stream_name, profile='qa', region='us-east-1'):
        cmd = [
            "aws", "logs", "get-log-events",
            "--log-group-name", log_group_name,
            "--log-stream-name", log_stream_name,
            "--limit", "10000",
            "--region", region,
            "--profile", profile
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Failed to get log events: {result.stderr}")
        events = json.loads(result.stdout).get('events', [])
        return [event['message'] for event in events]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(folder, exist_ok=True)
    log_group_name = log_group.strip('/').replace('/', '_')
    filename = f"{log_group_name}_latest_log_{timestamp}.txt"
    filepath = os.path.join(folder, filename)

    try:
        log_stream = get_latest_log_stream(log_group, profile, region)
        logs = get_log_events(log_group, log_stream, profile, region)
        with open(filepath, "w", encoding="utf-8") as f:
            for log in logs:
                f.write(log + "\n")
        print(f"Latest log saved to {filepath}")
        return filepath
    except Exception as e:
        print("Failed to save log:", e)
        return None


====================================================================


this is my conftest.py:

import pytest
import uuid
import os
import configparser
import boto3
import yaml
from datetime import datetime
from selenium import webdriver

@pytest.fixture(scope="session")
def config():
    """Load test configuration from subconfig.yaml."""
    with open("subconfig.yaml") as f:
        return yaml.safe_load(f)

# Add the missing 'url' fixture
@pytest.fixture
def url(config):
    """Provide base URL from configuration"""
    return config["base_url"]  # Ensure subconfig.yaml has 'base_url' defined

@pytest.fixture(scope="function")
def dynamic_aws_profile(config):
    """
    Dynamically create an AWS profile using hardcoded credentials.
    Cleans up the profile after the test.
    """
    # HARDCODED AWS CREDENTIALS - FOR DEMO/LOCAL USE ONLY!
    access_key = ""
    secret_key = ""
    region = config.get("region", "us-east-1")
    profile_name = f"qa-profile-{uuid.uuid4().hex[:8]}"

    # Write credentials to ~/.aws/credentials
    cred_path = os.path.expanduser("~/.aws/credentials")
    creds = configparser.ConfigParser()
    if os.path.exists(cred_path):
        creds.read(cred_path)
    creds[profile_name] = {
        "aws_access_key_id": access_key,
        "aws_secret_access_key": secret_key,
        "aws_session_token": session_token,
    }
    with open(cred_path, "w") as f:
        creds.write(f)

    # Write region to ~/.aws/config
    conf_path = os.path.expanduser("~/.aws/config")
    config_file = configparser.ConfigParser()
    if os.path.exists(conf_path):
        config_file.read(conf_path)
    config_file[f"profile {profile_name}"] = {"region": region}
    with open(conf_path, "w") as f:
        config_file.write(f)

    yield profile_name

    # Cleanup: Remove the profile after the test
    creds.read(cred_path)
    if profile_name in creds:
        creds.remove_section(profile_name)
        with open(cred_path, "w") as f:
            creds.write(f)
    config_file.read(conf_path)
    section = f"profile {profile_name}"
    if section in config_file:
        config_file.remove_section(section)
        with open(conf_path, "w") as f:
            config_file.write(f)

@pytest.fixture
def aws_session(dynamic_aws_profile):
    """Return a boto3.Session using the dynamic AWS profile."""
    return boto3.Session(profile_name=dynamic_aws_profile)

@pytest.fixture
def today_str():
    """Returns today's date as YYYY-MM-DD string."""
    return datetime.now().strftime("%Y-%m-%d")

# ------------------- ADD THIS FOR SELENIUM WEBDRIVER -------------------

from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

@pytest.fixture
def driver():
    """Provide a Selenium WebDriver instance using Chrome."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Use GUI browser in local by commenting this line
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    yield driver
    driver.quit()


@pytest.fixture
def main_page(driver):
    return MainPage(driver)
