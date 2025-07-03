from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
 
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
 
