#!/usr/bin/env python3
"""
Example usage of Twitter Media Downloader
"""

from twitter_scraper_downloader import TwitterScraperDownloader

def main():
    # Example tweet URL (this one contains an image)
    tweet_url = "https://x.com/techdevnotes/status/1956686646272790863"

    # Create downloader instance
    downloader = TwitterScraperDownloader()

    # Download media to 'downloads' folder
    downloaded_files = downloader.download_from_url(tweet_url, "downloads")

    if downloaded_files:
        print("\n✅ Successfully downloaded:")
        for file in downloaded_files:
            print(f"   📁 {file}")
    else:
        print("\n❌ No media found or download failed")

    # You can also download multiple tweets
    tweet_urls = [
        "https://x.com/techdevnotes/status/1956686646272790863",
        # Add more URLs here
    ]

    print("\n🔄 Processing multiple tweets...")
    for url in tweet_urls:
        print(f"\n📱 Processing: {url}")
        files = downloader.download_from_url(url, "downloads")
        if files:
            print(f"   ✅ Downloaded {len(files)} file(s)")
        else:
            print("   ❌ No media found")

if __name__ == '__main__':
    main()
