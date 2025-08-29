#!/usr/bin/env python3
"""
Twitter/X Media Downloader
Downloads GIFs, videos, and images from Twitter/X posts using yt-dlp
"""

import os
import sys
import argparse
from pathlib import Path
import yt_dlp


class TwitterMediaDownloader:
    def __init__(self, output_dir="downloads"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
    def download_media(self, url):
        """Download media from Twitter URL"""
        ydl_opts = {
            'outtmpl': str(self.output_dir / '%(uploader)s_%(id)s.%(ext)s'),
            'writeinfojson': False,
            'writethumbnail': False,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                print(f"Downloading media from: {url}")
                ydl.download([url])
                print(f"Download completed! Files saved to: {self.output_dir}")
                
        except Exception as e:
            print(f"Error downloading media: {e}")
            return False
            
        return True


def main():
    parser = argparse.ArgumentParser(description="Download media from Twitter/X posts")
    parser.add_argument("url", help="Twitter/X post URL")
    parser.add_argument("-o", "--output", default="downloads", 
                       help="Output directory (default: downloads)")
    
    args = parser.parse_args()
    
    downloader = TwitterMediaDownloader(args.output)
    success = downloader.download_media(args.url)
    
    if success:
        print("Media download successful!")
    else:
        print("Media download failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()