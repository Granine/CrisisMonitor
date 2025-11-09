"""
CSV to Database Import Script for Crisis Monitor
Reads _instance.csv and sends each tweet to the backend API for classification and storage.
Processes tweets one by one sequentially.
"""

import csv
import requests
import time
import os
from typing import Dict, Any


# Configuration
API_URL = os.getenv("NEXT_PUBLIC_API_URL", "")  # Update with your deployed backend URL
CSV_FILE = "data/crisis_example.csv"
DELAY_BETWEEN_REQUESTS = 0.5  # seconds to wait between requests


def read_csv_file(file_path: str) -> list[Dict[str, Any]]:
    """
    Read the CSV file and return a list of dictionaries.
    Assumes CSV has a 'text' column with the tweet content.
    Adjust column names as needed based on your CSV structure.
    """
    tweets = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                tweets.append(row)
        print(f"✓ Loaded {len(tweets)} rows from {file_path}")
        return tweets
    except FileNotFoundError:
        print(f"✗ Error: File '{file_path}' not found!")
        return []
    except Exception as e:
        print(f"✗ Error reading CSV: {e}")
        return []


def send_tweet_to_api(tweet_text: str, api_url: str) -> Dict[str, Any] | None:
    """
    Send a single tweet to the backend API for classification.
    Returns the API response or None if failed.
    """
    endpoint = f"{api_url}/predict-tweet"
    payload = {"text": tweet_text}
    
    try:
        response = requests.post(endpoint, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  ✗ API Error: {e}")
        return None


def process_csv_to_database(csv_file: str, api_url: str, delay: float = 0.5):
    """
    Main function to process CSV and send each row to the database via API.
    """
    print("=" * 70)
    print("🚀 Crisis Monitor - CSV Import Script")
    print("=" * 70)
    print(f"📁 CSV File: {csv_file}")
    print(f"🌐 API URL: {api_url}")
    print(f"⏱️  Delay: {delay}s between requests")
    print("=" * 70)
    print()
    
    # Read CSV
    rows = read_csv_file(csv_file)
    if not rows:
        print("❌ No data to process. Exiting.")
        return
    
    # Determine the column name for tweet text
    # Common column names: 'text', 'tweet', 'cleaned_tweet', 'content'
    sample_row = rows[0]
    text_column = None
    for col in ['text', 'tweet', 'cleaned_tweet', 'content', 'message']:
        if col in sample_row:
            text_column = col
            break
    
    if not text_column:
        print(f"❌ Could not find tweet text column in CSV. Available columns: {list(sample_row.keys())}")
        print("   Please update the script to match your CSV structure.")
        return
    
    print(f"📝 Using column '{text_column}' for tweet text\n")
    
    # Process each row
    total = len(rows)
    successful = 0
    failed = 0
    
    start_time = time.time()
    
    for idx, row in enumerate(rows, 1):
        tweet_text = row.get(text_column, "").strip()
        
        if not tweet_text:
            print(f"[{idx}/{total}] ⚠️  Skipping empty row")
            failed += 1
            continue
        
        # Truncate display text for readability
        display_text = tweet_text[:60] + "..." if len(tweet_text) > 60 else tweet_text
        print(f"[{idx}/{total}] 📤 Processing: {display_text}")
        
        # Send to API
        result = send_tweet_to_api(tweet_text, api_url)
        
        if result:
            is_disaster = result.get("is_real_disaster", False)
            prob = result.get("disaster_probability", 0.0)
            status = "🚨 EMERGENCY" if is_disaster else "✅ SAFE"
            print(f"         {status} (confidence: {prob:.2%})")
            successful += 1
        else:
            print("         ❌ Failed to process")
            failed += 1
        
        # Delay between requests to avoid overwhelming the API
        if idx < total:
            time.sleep(delay)
    
    # Summary
    elapsed_time = time.time() - start_time
    print()
    print("=" * 70)
    print("📊 Import Summary")
    print("=" * 70)
    print(f"✅ Successful: {successful}/{total}")
    print(f"❌ Failed: {failed}/{total}")
    print(f"⏱️  Total time: {elapsed_time:.2f}s")
    print(f"⚡ Average: {elapsed_time/total:.2f}s per tweet")
    print("=" * 70)


if __name__ == "__main__":
    # Check if API_URL environment variable is set
    api_url = os.getenv("API_URL")
    if not api_url:
        print("⚠️  API_URL environment variable not set.")
        print("   Using default: envron")
        print("   Set API_URL to your deployed backend URL:")
        print("   Example: export API_URL=https://your-backend.com")
        print()
        api_url = input("Enter API URL (or press Enter for envron): ").strip()
        if not api_url:
            print("Reading form envron value.")
            api_url = API_URL
    
    # Check if CSV file exists
    if not os.path.exists(CSV_FILE):
        print(f"\n❌ CSV file '{CSV_FILE}' not found in current directory!")
        print(f"   Current directory: {os.getcwd()}")
        print("   Please ensure the file exists or update the CSV_FILE variable in the script.")
        exit(1)
    
    # Run the import
    try:
        process_csv_to_database(CSV_FILE, api_url, DELAY_BETWEEN_REQUESTS)
    except KeyboardInterrupt:
        print("\n\n⚠️  Import interrupted by user. Exiting...")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
