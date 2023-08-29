import gspread
from oauth2client.service_account import ServiceAccountCredentials
import subprocess
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from apiclient import discovery
from google.oauth2 import service_account

# For Google Drive
def authenticate_google_drive():
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    credentials = Credentials.from_service_account_file(
        scopes=scopes
    )
    gc = authenticate_google_sheets()
    drive = discovery.build('drive', 'v3', credentials=credentials)
    return drive

# For Google Sheets
def authenticate_google_sheets():
    gc = gspread.service_account()
    return gc


# Check if a URL is valid
def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

# Modify this function to add URL validation
def get_website_list(sheet_name):
    client = authenticate_google_sheets()
    worksheet = client.open(sheet_name).get_worksheet(0)
    website_col = worksheet.find("Website").col
    urls = worksheet.col_values(website_col)[1:]  # Excluding the header

    # Validate and potentially fix URLs
    valid_urls = []
    for url in urls:
        if not is_valid_url(url):
            fixed_url = "https://" + url  # Try to append "https://" to the URL
            if is_valid_url(fixed_url):
                valid_urls.append(fixed_url)
            else:
                print(f"Invalid URL found: {url}")
        else:
            valid_urls.append(url)

    return valid_urls

def create_google_sheet_in_folder(title, folder_id):
    drive = authenticate_google_drive()
    file_metadata = {
        'name': title,
        'mimeType': 'application/vnd.google-apps.spreadsheet',
        'parents': [folder_id]
    }
    file = drive.files().create(body=file_metadata).execute()
    return file['id']  # Returns the file ID of the created sheet

def store_results_in_google_sheet(data, folder_id):
    title = f"Results - Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    file_id = create_google_sheet_in_folder(title, folder_id)
    
    client = authenticate_google_sheets()
    worksheet = client.open_by_key(file_id).get_worksheet(0)
    
    headers = ["Website", "Performance", "Accessibility", "Best Practices", "SEO", "PWA"]
    worksheet.append_row(headers)
    
    for result in data:
        if isinstance(result[1], dict):
            row = [result[0]] + [result[1][header] for header in headers[1:]]
        else:
            row = [result[0], "Error: " + result[1]]
        worksheet.append_row(row)

# Run Lighthouse test on a website
def run_lighthouse_test(url):
    try:
        result = subprocess.check_output(['lighthouse', url, '--output=json'])
        data = json.loads(result)
        scores = {
            'Performance': data['categories']['performance']['score'],
            'Accessibility': data['categories']['accessibility']['score'],
            'Best Practices': data['categories']['best-practices']['score'],
            'SEO': data['categories']['seo']['score'],
            'PWA': data['categories']['pwa']['score'] if 'pwa' in data['categories'] else None
        }
        return (url, scores)
    except subprocess.CalledProcessError as e:
        return (url, str(e))

def main(iterations, sheet_name, folder_id):
    websites = get_website_list(sheet_name)
    for _ in range(iterations):
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(run_lighthouse_test, websites))
        store_results_in_google_sheet(results, folder_id)

if __name__ == "__main__":
    import sys
    iterations = int(sys.argv[1])
    sheet_name = sys.argv[2]  # Pass the source sheet name as the second argument
    folder_id = sys.argv[3]
    main(iterations, sheet_name, folder_id)
