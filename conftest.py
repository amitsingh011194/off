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

@pytest.fixture
def driver():
    """Provide a Selenium WebDriver instance."""
    driver = webdriver.Firefox()
    driver.maximize_window()
    yield driver
    driver.quit()  # Uncommented to ensure cleanup

@pytest.fixture
def main_page(driver):
    return MainPage(driver)


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
