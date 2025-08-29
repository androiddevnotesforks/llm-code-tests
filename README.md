# Twitter Media Downloader

A Python script to download GIFs and videos from X/Twitter posts using web scraping.

## Features

- Downloads videos, GIFs, and photos from Twitter/X posts
- Supports both `x.com` and `twitter.com` URLs
- Downloads highest quality available
- Shows download progress
- Saves files with timestamp-based names
- Handles multiple media items in a single tweet
- Uses web scraping (more reliable than API)

## Installation

1. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Command Line

```bash
python twitter_scraper_downloader.py <tweet_url> [output_directory]
```

### Examples

Download media from a specific tweet:
```bash
python twitter_scraper_downloader.py https://x.com/techdevnotes/status/1956686646272790863
```

Download to a specific directory:
```bash
python twitter_scraper_downloader.py https://x.com/techdevnotes/status/1956686646272790863 ./downloads
```

### Python Module

```python
from twitter_scraper_downloader import TwitterScraperDownloader

downloader = TwitterScraperDownloader()
files = downloader.download_from_url("https://x.com/techdevnotes/status/1956686646272790863")
print(f"Downloaded: {files}")
```

### Running the Example

```bash
python example.py
```

## Output

The script will download media files with names like:
- `twitter_video_1703123456.mp4` (for videos)
- `twitter_gif_1703123456.mp4` (for GIFs)
- `twitter_photo_1703123456.jpg` (for photos)

## Files

- `twitter_scraper_downloader.py` - Main downloader script (working version)
- `twitter_media_downloader.py` - API-based version (may not work due to Twitter changes)
- `example.py` - Example usage script
- `requirements.txt` - Python dependencies
- `README.md` - This documentation

## Notes

- Uses web scraping with proper browser headers to avoid blocking
- GIFs are downloaded as MP4 files (Twitter's native format for animated GIFs)
- Photos are downloaded in original quality when available
- Videos are downloaded in the highest available bitrate
- Works with both x.com and twitter.com URLs

## Requirements

- Python 3.6+
- requests library

## Troubleshooting

If you encounter issues:
1. Make sure you're using the virtual environment
2. Check that the tweet URL is correct and public
3. Some tweets may not have downloadable media
4. Twitter may change their page structure over time

## Tested With

- ✅ Photos: https://x.com/techdevnotes/status/1956686646272790863
- Add more test URLs as needed
