import gspread
from oauth2client.service_account import ServiceAccountCredentials
import subprocess
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import time
import socket

def is_connected(hostname="www.google.com"):
    try:
        host = socket.gethostbyname(hostname)
        socket.create_connection((host, 80), 2)
        return True
    except:
        return False

# For Google Drive
def authenticate_google_drive():
    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_file('web-performance-testing-397100-b49d0bb7c522.json', scopes=SCOPES)
    drive = build('drive', 'v3', credentials=creds)
    return drive

# For Google Sheets
def authenticate_google_sheets():
    SCOPES = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_file('web-performance-testing-397100-b49d0bb7c522.json', scopes=SCOPES)
    client = gspread.authorize(creds)
    return client



def create_google_sheet_in_folder(title, folder_id):
    drive = authenticate_google_drive()
    file_metadata = {
        'name': title,
        'mimeType': 'application/vnd.google-apps.spreadsheet',
        'parents': [folder_id]
    }
    file = drive.files().create(body=file_metadata, fields='id').execute()
    return file['id']  # Returns the file ID of the created sheet

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
            fixed_url = "http://" + url  # Try to append "http://" to the URL
            if is_valid_url(fixed_url):
                valid_urls.append(fixed_url)
            else:
                print(f"Invalid URL found: {url}")
        else:
            valid_urls.append(url)

    return valid_urls

def run_lighthouse_test_with_reconnect(url):
    while True:
        if is_connected():
            return run_lighthouse_test(url)
        else:
            print("Internet connection lost. Waiting for reconnection...")
            time.sleep(30)  # Check every 30 seconds

# Run Lighthouse test on a website
def run_lighthouse_test(url):
    try:
        result = subprocess.run(['lighthouse', url, '--output=json'],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL,
                                check=True)  # Check=True will raise CalledProcessError if command returns non-zero exit status
        data = json.loads(result.stdout)
        performance_score = data['categories']['performance']['score']
        return (url, performance_score)
    except subprocess.CalledProcessError as e:
        return (url, str(e))
    
def store_results_in_google_sheet_with_reconnect(data, sheet_name, folder_id):
    while True:
        if is_connected():
            return store_results_in_google_sheet(data, sheet_name, folder_id)
        else:
            print("Internet connection lost. Waiting for reconnection...")
            time.sleep(30)  # Check every 30 seconds

# Store results in a new Google Sheet
def store_results_in_google_sheet(data, sheet_name, folder_id):
    client = authenticate_google_sheets()
    drive_service = authenticate_google_drive()
    
    try:
        # Attempt to open the worksheet
        worksheet = client.open(sheet_name).get_worksheet(0)
    except gspread.SpreadsheetNotFound:
        # If not found, create a new Google Sheet
        sh = client.create(sheet_name)
        worksheet = sh.get_worksheet(0)
        headers = ["Website"]
        worksheet.append_row(headers)
        
        # Move the created sheet to the specified folder
        file_id = sh.id
        file = drive_service.files().get(fileId=file_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents'))
        file = drive_service.files().update(fileId=file_id,
                                            addParents=folder_id,
                                            removeParents=previous_parents,
                                            fields='id, parents').execute()
    else:
        # If sheet exists, fetch the headers
        headers = worksheet.row_values(1)

    # Check if a new iteration is needed and add a new column header
    new_column_header = "Performance " + datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if new_column_header not in headers:
        headers.append(new_column_header)
        worksheet.append_row(headers)
    
    # Update each row with the new performance score or add new rows if needed
    for result in data:
        url = result[0]
        performance_score = result[1]
        if not isinstance(performance_score, str):  # If it's not an error message
            performance_score = str(performance_score)
        try:
            cell = worksheet.find(url)
            worksheet.update_cell(cell.row, len(headers), performance_score)  # Add the performance score in the new column
        except gspread.exceptions.CellNotFound:
            # If the website is not already listed in the sheet, add a new row for it
            new_row = [url] + [""] * (len(headers) - 2) + [performance_score]
            worksheet.append_row(new_row)
    
    # Compute average and update the last cell in the new column
    avg_formula = f"=AVERAGE(R2C{len(headers)}:R{worksheet.row_count}C{len(headers)})"
    worksheet.update_cell(worksheet.row_count, len(headers), avg_formula)

def main(iterations, sheet_name, folder_id):
    websites = get_website_list(sheet_name)
    for _ in range(iterations):
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(run_lighthouse_test_with_reconnect, websites))
        store_results_in_google_sheet_with_reconnect(results, sheet_name, folder_id)
        time.sleep(60)  # Introduce a 1-minute delay between iterations


if __name__ == "__main__":
    import sys
    iterations = int(sys.argv[1])
    sheet_name = sys.argv[2]  # Pass the source sheet name as the second argument
    folder_id = sys.argv[3]
    main(iterations, sheet_name, folder_id)
