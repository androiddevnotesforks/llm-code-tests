#!/usr/bin/env python3
"""
Twitter Media Downloader
Downloads GIFs and Videos from X/Twitter posts

Usage:
    python twitter_media_downloader.py <tweet_url> [output_dir]

Example:
    python twitter_media_downloader.py https://x.com/techdevnotes/status/1956686646272790863
"""

import sys
import os
import json
import re
import requests
from urllib.parse import urlparse, parse_qs
import argparse
from pathlib import Path
import time


class TwitterMediaDownloader:
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

        # Try to extract from query parameters
        if parsed.query:
            params = parse_qs(parsed.query)
            if 'status' in params:
                return params['status'][0]

        raise ValueError(f"Could not extract tweet ID from URL: {url}")

    def get_guest_token(self):
        """Get guest token for accessing Twitter API"""
        try:
            response = self.session.post('https://api.twitter.com/1.1/guest/activate.json')
            if response.status_code == 200:
                return response.json()['guest_token']
        except Exception as e:
            print(f"Warning: Could not get guest token: {e}")
        return None

    def get_tweet_data(self, tweet_id):
        """Fetch tweet data using Twitter's GraphQL API"""
        guest_token = self.get_guest_token()
        if guest_token:
            self.session.headers['x-guest-token'] = guest_token

        # Twitter's GraphQL endpoint for tweet details
        api_url = 'https://twitter.com/i/api/graphql/0hWvDhmW8YQ-S_ib3azIrQ/TweetResultByRestId'

        variables = {
            'tweetId': tweet_id,
            'withCommunity': False,
            'includePromotedContent': False,
            'withVoice': False
        }

        features = {
            'creator_subscriptions_quote_tweet_preview_enabled': False,
            'communities_web_enable_tweet_community_results_fetch': False,
            'c9s_tweet_anatomy_moderator_badge_enabled': False,
            'articles_preview_enabled': True,
            'tweetypie_unmention_optimization_enabled': True,
            'responsive_web_edit_tweet_api_enabled': True,
            'graphql_is_translatable_rweb_tweet_is_translatable_enabled': True,
            'view_counts_everywhere_api_enabled': True,
            'longform_notetweets_consumption_enabled': True,
            'responsive_web_twitter_article_tweet_consumption_enabled': False,
            'tweet_awards_web_tipping_enabled': False,
            'freedom_of_speech_not_reach_fetch_enabled': True,
            'standardized_nudges_misinfo': True,
            'tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled': True,
            'longform_notetweets_rich_text_read_enabled': True,
            'longform_notetweets_inline_media_enabled': True,
            'responsive_web_graphql_exclude_directive_enabled': True,
            'verified_phone_label_enabled': False,
            'responsive_web_graphql_skip_user_profile_image_extensions_enabled': False,
            'responsive_web_graphql_timeline_navigation_enabled': True,
            'responsive_web_enhance_cards_enabled': False
        }

        params = {
            'variables': json.dumps(variables),
            'features': json.dumps(features)
        }

        try:
            response = self.session.get(api_url, params=params)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error fetching tweet data via API: {e}")

        return None

    def extract_media_urls(self, tweet_data):
        """Extract media URLs from tweet data"""
        media_urls = []

        try:
            if 'data' in tweet_data and 'threaded_conversation_with_injections_v2' in tweet_data['data']:
                instructions = tweet_data['data']['threaded_conversation_with_injections_v2']['instructions']

                for instruction in instructions:
                    if instruction.get('type') == 'TimelineAddEntries':
                        for entry in instruction.get('entries', []):
                            if entry['entryId'].startswith('tweet-'):
                                tweet_result = entry['content']['itemContent']['tweet_results']['result']

                                # Handle regular tweets
                                if 'legacy' in tweet_result:
                                    legacy = tweet_result['legacy']
                                    if 'extended_entities' in legacy:
                                        for media in legacy['extended_entities']['media']:
                                            media_urls.extend(self._extract_media_from_entity(media))

                                # Handle quoted tweets
                                if 'quoted_status_result' in tweet_result:
                                    quoted_result = tweet_result['quoted_status_result']['result']
                                    if 'legacy' in quoted_result:
                                        quoted_legacy = quoted_result['legacy']
                                        if 'extended_entities' in quoted_legacy:
                                            for media in quoted_legacy['extended_entities']['media']:
                                                media_urls.extend(self._extract_media_from_entity(media))

        except Exception as e:
            print(f"Error parsing tweet data: {e}")

        return media_urls

    def _extract_media_from_entity(self, media_entity):
        """Extract media URLs from a single media entity"""
        urls = []

        media_type = media_entity.get('type')

        if media_type == 'video':
            # Get the highest quality video
            video_info = media_entity.get('video_info', {})
            variants = video_info.get('variants', [])

            # Filter for MP4 variants and sort by bitrate
            mp4_variants = [v for v in variants if v.get('content_type') == 'video/mp4']
            if mp4_variants:
                # Sort by bitrate (highest first)
                mp4_variants.sort(key=lambda x: x.get('bitrate', 0), reverse=True)
                urls.append({
                    'url': mp4_variants[0]['url'],
                    'type': 'video',
                    'filename': f"twitter_video_{int(time.time())}.mp4"
                })

        elif media_type == 'animated_gif':
            # Get the GIF URL
            video_info = media_entity.get('video_info', {})
            variants = video_info.get('variants', [])

            # Filter for MP4 variants (Twitter serves GIFs as MP4)
            mp4_variants = [v for v in variants if v.get('content_type') == 'video/mp4']
            if mp4_variants:
                urls.append({
                    'url': mp4_variants[0]['url'],
                    'type': 'gif',
                    'filename': f"twitter_gif_{int(time.time())}.mp4"
                })

        elif media_type == 'photo':
            # For photos, get the original size
            media_url = media_entity.get('media_url_https', '')
            if media_url:
                # Replace with original size
                original_url = media_url + ':orig'
                urls.append({
                    'url': original_url,
                    'type': 'photo',
                    'filename': f"twitter_photo_{int(time.time())}.jpg"
                })

        return urls

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

        # Extract tweet ID
        try:
            tweet_id = self.extract_tweet_id(tweet_url)
            print(f"Extracted tweet ID: {tweet_id}")
        except ValueError as e:
            print(f"Error: {e}")
            return []

        # Get tweet data
        tweet_data = self.get_tweet_data(tweet_id)
        if not tweet_data:
            print("Could not fetch tweet data")
            return []

        # Extract media URLs
        media_urls = self.extract_media_urls(tweet_data)
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
    parser = argparse.ArgumentParser(description='Download media from Twitter/X posts')
    parser.add_argument('url', help='Twitter/X post URL')
    parser.add_argument('-o', '--output', default='.', help='Output directory (default: current directory)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    args = parser.parse_args()

    if args.verbose:
        print(f"Downloading from: {args.url}")
        print(f"Output directory: {args.output}")

    downloader = TwitterMediaDownloader()
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
