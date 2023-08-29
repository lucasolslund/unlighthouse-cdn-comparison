import pandas as pd
import requests
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor

def is_website(domain):
    """Check if a domain is a website by sending a GET request."""
    try:
        response = requests.get(f'http://{domain}', timeout=5)
        return response.status_code == 200
    except (requests.ConnectionError, requests.Timeout):
        return False

def main():
    # Load the CSV data into a dataframe
    df = pd.read_csv('top-1000.csv')
    
    # Use ThreadPoolExecutor to concurrently check domains
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(tqdm(executor.map(is_website, df['Domain']), total=len(df), desc="Checking domains"))
    
    # Filter the dataframe to only include domains that are websites
    websites_df = df[results]
    
    # Save the result to a new CSV file
    websites_df.to_csv('websites.csv', index=False)
    print(f"Filtered websites saved to 'websites.csv'")

if __name__ == "__main__":
    main()
