import base64
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Semaphore

import requestez
from Crypto.Cipher import AES
from Crypto.Util import Counter

requests = requestez.Session()


class CryptoHelper:
    """Helper class for encryption and decryption."""

    def __init__(self):
        self.decryption_key = "RB0fpH8ZEyVLkv7c2i6MAJ5u3IKFDxlS1NTsnGaqmXYdUrtzjwObCgQP94hoeW+/="

    def get_key(self, video_size):
        """Generate a decryption key based on the video size."""
        # Placeholder: Replace with actual key derivation if needed
        return str(video_size)[:16].ljust(16, "0")

    def decrypt_aes_ctr(self, data, key):
        """Decrypt data using AES CTR mode."""
        iv = key.encode()[:16]
        cipher = AES.new(key.encode(), AES.MODE_CTR, counter=Counter.new(128, initial_value=int.from_bytes(iv, 'big')))
        return cipher.decrypt(data)

    def encrypt_aes_ctr(self, data, key):
        """Encrypt data using AES CTR mode."""
        iv = key.encode()[:16]
        cipher = AES.new(key.encode(), AES.MODE_CTR, counter=Counter.new(128, initial_value=int.from_bytes(iv, 'big')))
        return cipher.encrypt(data)


class VideoDownloader:
    def __init__(self, config, crypto_helper):
        self.config = config
        self.crypto_helper = crypto_helper

    def get_video_metadata(self, url, headers=None):
        """Fetch video metadata."""
        response = requests.get(url, headers=headers, text=False)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch video metadata: {response.status_code}")
        encrypted_data = self.extract_encrypted_metadata(response.text)
        if encrypted_data:
            return json.loads(self.crypto_helper.decode_encrypted_string(encrypted_data))
        return None

    def extract_encrypted_metadata(self, html):
        """Extract encrypted video metadata from HTML content."""
        import re
        match = re.search(r'JSON\.parse\(atob\("([^"]+)"\)\)', html)
        if match:
            return base64.b64decode(match.group(1)).decode("utf-8")
        return None

    def initialize_temp_dir(self, simple_video, total_segments):
        """Create a temporary directory for storing downloaded segments."""
        temp_folder_name = f"temp_{simple_video['slug']}_{simple_video['label']}"
        temp_folder = Path(self.config['output_path']).parent / temp_folder_name
        temp_folder.mkdir(exist_ok=True)

        existing_segments = {int(file.stem.split('_')[1]) for file in temp_folder.glob("segment_*")}
        all_segments = set(range(total_segments))
        missing_segments = list(all_segments - existing_segments)

        return temp_folder, missing_segments

    def generate_ranges(self, size, step=2097152):
        """Generate byte ranges for the video segments."""
        ranges = []
        start = 0
        while start < size:
            end = min(start + step, size)
            ranges.append((start, end))
            start = end
        return ranges

    def download_segment(self, url, body, index, temp_dir, decryption_key):
        """Download a single segment and write to file."""
        print(body.encode("ISO-8859-1"))
        response = requests.post(url, body={"hash": body}, text=False)
        print(response)
        if response.status_code != 200:
            raise Exception(f"Failed to download segment {index}: {response.status_code}")
        is_header = True
        segment_file = temp_dir / f"segment_{index}"
        with segment_file.open("ab") as f:
            for chunk in response.iter_content(65536):
                if is_header:
                    chunk = self.crypto_helper.decrypt_aes_ctr(chunk, decryption_key)
                    is_header = False
                f.write(chunk)

    def merge_segments(self, temp_dir, output_file):
        """Merge all segments into a single MP4 file."""
        output_file = Path(output_file)
        with output_file.open("wb") as merged_file:
            for segment_file in sorted(temp_dir.glob("segment_*"), key=lambda x: int(x.stem.split('_')[1])):
                with segment_file.open("rb") as f:
                    merged_file.write(f.read())
        print(f"Segments merged successfully into {output_file}")
        # Cleanup temp folder
        for file in temp_dir.iterdir():
            file.unlink()
        temp_dir.rmdir()

    def download_video(self, video_metadata):
        """Download video segments in parallel."""
        simple_video = {
            "id": video_metadata['id'],
            "slug": video_metadata['slug'],
            "size": video_metadata['sources'][0]['size'],
            "label": video_metadata['sources'][0]['label']
        }
        segment_bodies = self.generate_segments_body(simple_video)
        segment_url = f"https://{video_metadata['domain']}/{video_metadata['id']}"
        temp_dir, missing_segments = self.initialize_temp_dir(simple_video, len(segment_bodies))

        semaphore = Semaphore(self.config['connections'])
        decryption_key = self.crypto_helper.get_key(simple_video['size'])

        with ThreadPoolExecutor(max_workers=self.config['connections']) as executor:
            futures = []
            for index in missing_segments:
                body = segment_bodies[index]
                futures.append(
                    executor.submit(self.download_segment, segment_url, body, index, temp_dir, decryption_key)
                )
            for future in futures:
                future.result()  # Wait for all to complete

        self.merge_segments(temp_dir, self.config['output_path'])

    def generate_segments_body(self, simple_video):
        """Generate request bodies for video segments."""
        encryption_key = self.crypto_helper.get_key(simple_video['slug'])
        ranges = self.generate_ranges(simple_video['size'])
        segments = {}
        for index, (start, end) in enumerate(ranges):
            body = json.dumps({"range": {"start": start, "end": end}})
            encrypted_body = self.crypto_helper.encrypt_aes_ctr(body.encode(), encryption_key)
            segments[index] = base64.b64encode(encrypted_body).decode()
        return segments


# Example Configuration
config = {
    "output_path": "output/video.mp4",
    "connections": 5,
}

# Instantiate the downloader
crypto_helper = CryptoHelper()
downloader = VideoDownloader(config, crypto_helper)

# Example usage
video_metadata = {
    'width': '100%', 'height': '100%', 'preload': 'auto', 'doNotSaveCookies': False,
    'fullscreenOrientationLock': 'none', 'pipIcon': 'disabled',
    'sources': [
        {'label': '360p', 'res_id': 2, 'size': 17695289, 'codec': 'h264', 'status': True, 'type': 'mp4'},
        {'label': '720p', 'res_id': 4, 'size': 65689683, 'codec': 'h264', 'status': True, 'type': 'mp4'},
        {'label': '1080p', 'res_id': 5, 'size': 142825359, 'codec': 'h264', 'status': True, 'type': 'mp4'},
        {'label': '1080p', 'res_id': 5, 'size': 76548446, 'codec': 'av1', 'status': True, 'type': 'mp4'}
    ],
    'id': 'ednuiloe6WOMbfXcXOJqsYeSNhrVSZUb', 'slug': 'pAWXk3rv7', 'md5_id': 24377658, 'user_id': 397920,
    'domain': 'hptsmyr6x4.globalcdn08.one',
    'ads': {'pop': ['https://psegeevalrat.net/4/7807247', 'https://broadensilkslush.com/2020443/']},
    'image': 'https://cdn.freeimagecdn.net/pAWXk3rv7.jpg', 'preview': True, 'addDownload': True,
    'logo': {'file': 'https://animekhor.org/wp-content/uploads/2021/11/AnimeKhor_darkmode.png',
             'link': 'https://animekhor.org/', 'hide': True, 'margin': '5px', 'position': 'top-right'}, 'tracks': [
        {'file': 'https://cdn1.freeimagecdn.net/24377658/DThyexRfxr.srt', 'label': 'Indonesian', 'kind': 'captions'}]}
downloader.download_video(video_metadata)
