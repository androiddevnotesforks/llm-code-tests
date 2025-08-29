#!/usr/bin/env python3
"""
Twitter Media Downloader (Web Scraping Version)
Downloads GIFs and Videos from X/Twitter posts using web scraping

Usage:
    python twitter_scraper_downloader.py <tweet_url> [output_dir]

Example:
    python twitter_scraper_downloader.py https://x.com/techdevnotes/status/1956686646272790863
"""

import sys
import os
import re
import json
import requests
from urllib.parse import urlparse, unquote
import argparse
from pathlib import Path
import time


class TwitterScraperDownloader:
    def __init__(self):
        self.session = requests.Session()
        # Set headers to mimic a browser request
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

    def extract_tweet_id(self, url):
        """Extract tweet ID from Twitter/X URL"""
        # Handle both x.com and twitter.com URLs
        url = url.replace('twitter.com', 'x.com')

        # Parse URL to get tweet ID
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')

        if len(path_parts) >= 3 and path_parts[1] == 'status':
            return path_parts[2]

        raise ValueError(f"Could not extract tweet ID from URL: {url}")

    def get_page_content(self, tweet_url):
        """Fetch the tweet page content"""
        try:
            response = self.session.get(tweet_url)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching page: {e}")
            return None

    def extract_media_urls_from_html(self, html_content, tweet_url):
        """Extract media URLs from HTML content using regex patterns"""
        media_urls = []

        # Pattern 1: Video/GIF URLs in script tags
        video_patterns = [
            r'"video_url":"([^"]*\.mp4[^"]*)"',  # MP4 videos
            r'"playback_url":"([^"]*\.mp4[^"]*)"',  # Playback URLs
            r'"content_url":"([^"]*\.mp4[^"]*)"',  # Content URLs
        ]

        for pattern in video_patterns:
            matches = re.findall(pattern, html_content)
            for match in matches:
                # Decode URL if needed
                decoded_url = unquote(match)
                if decoded_url.startswith('http'):
                    media_urls.append({
                        'url': decoded_url,
                        'type': 'video',
                        'filename': f"twitter_video_{int(time.time())}.mp4"
                    })

        # Pattern 2: GIF URLs (often served as MP4)
        gif_patterns = [
            r'href="([^"]*\.mp4[^"]*)"',  # MP4 links
            r'src="([^"]*\.mp4[^"]*)"',  # MP4 sources
        ]

        for pattern in gif_patterns:
            matches = re.findall(pattern, html_content)
            for match in matches:
                decoded_url = unquote(match)
                if decoded_url.startswith('http') and 'video' in decoded_url:
                    media_urls.append({
                        'url': decoded_url,
                        'type': 'gif',
                        'filename': f"twitter_gif_{int(time.time())}.mp4"
                    })

        # Pattern 3: Image URLs
        image_patterns = [
            r'"media_url_https":"([^"]*\.(jpg|jpeg|png|gif)[^"]*)"',  # Media URLs
            r'href="([^"]*\.(jpg|jpeg|png|gif)[^"]*)"',  # Direct image links
            r'src="([^"]*\.(jpg|jpeg|png|gif)[^"]*)"',  # Image sources
        ]

        for pattern in image_patterns:
            matches = re.findall(pattern, html_content)
            for match in matches:
                if isinstance(match, tuple):
                    url, ext = match
                else:
                    url = match
                    ext = url.split('.')[-1] if '.' in url else 'jpg'

                decoded_url = unquote(url)
                if decoded_url.startswith('http'):
                    # Convert to original size if it's a Twitter image
                    if 'pbs.twimg.com/media/' in decoded_url and not decoded_url.endswith(':orig'):
                        decoded_url += ':orig'

                    media_urls.append({
                        'url': decoded_url,
                        'type': 'photo',
                        'filename': f"twitter_photo_{int(time.time())}.jpg"
                    })

        # Remove duplicates while preserving order
        seen_urls = set()
        unique_media = []
        for media in media_urls:
            if media['url'] not in seen_urls:
                seen_urls.add(media['url'])
                unique_media.append(media)

        return unique_media

    def download_media(self, media_info, output_dir='.'):
        """Download media file"""
        url = media_info['url']
        filename = media_info['filename']
        filepath = os.path.join(output_dir, filename)

        print(f"Downloading {media_info['type']}: {filename}")

        try:
            response = self.session.get(url, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0

            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)

                        # Show progress
                        if total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            print(".1f", end='', flush=True)
                        else:
                            print(".", end='', flush=True)

            print(" Done!")
            return filepath

        except Exception as e:
            print(f"Error downloading media: {e}")
            return None

    def download_from_url(self, tweet_url, output_dir='.'):
        """Main method to download media from Twitter URL"""
        # Create output directory if it doesn't exist
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Extract tweet ID for logging
        try:
            tweet_id = self.extract_tweet_id(tweet_url)
            print(f"Extracted tweet ID: {tweet_id}")
        except ValueError as e:
            print(f"Error: {e}")
            return []

        # Get page content
        print("Fetching tweet page...")
        html_content = self.get_page_content(tweet_url)
        if not html_content:
            print("Could not fetch tweet page")
            return []

        # Extract media URLs
        media_urls = self.extract_media_urls_from_html(html_content, tweet_url)
        if not media_urls:
            print("No media found in tweet")
            return []

        print(f"Found {len(media_urls)} media item(s)")

        # Download media
        downloaded_files = []
        for media_info in media_urls:
            filepath = self.download_media(media_info, output_dir)
            if filepath:
                downloaded_files.append(filepath)

        return downloaded_files


def main():
    parser = argparse.ArgumentParser(description='Download media from Twitter/X posts (Web Scraping Version)')
    parser.add_argument('url', help='Twitter/X post URL')
    parser.add_argument('-o', '--output', default='.', help='Output directory (default: current directory)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    args = parser.parse_args()

    if args.verbose:
        print(f"Downloading from: {args.url}")
        print(f"Output directory: {args.output}")

    downloader = TwitterScraperDownloader()
    downloaded_files = downloader.download_from_url(args.url, args.output)

    if downloaded_files:
        print("\nDownload completed!")
        print("Files saved:")
        for file in downloaded_files:
            print(f"  - {file}")
    else:
        print("\nNo files were downloaded.")
        sys.exit(1)


if __name__ == '__main__':
    main()
