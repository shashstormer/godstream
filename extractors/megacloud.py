import requests
import hashlib
import base64
from Crypto.Cipher import AES
from typing import List, Dict, Any, Tuple, Optional
import re
import json
import time
from requestez import Session
from requestez.parsers import load


class MegaCloud:
    def __init__(self, session: Session):
        self.server_name = "MegaCloud"
        self.sources: List[Dict[str, Any]] = []
        self.session = session

    def extract(self, video_url: str) -> Dict[str, Any]:
        print(video_url)
        try:
            result = {
                "sources": [],
                "subtitles": [],
                "intro": None,
                "outro": None,
            }

            video_id = video_url.split("/")[-1].split("?")[0]
            url = f"https://megacloud.tv/embed-2/ajax/e-1/getSources?id={video_id}"

            headers = {
                "Accept": "*/*",
                # "X-Requested-With": "XMLHttpRequest",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
                ),
                "Cookie": "userSettings={%22auto_play%22:1%2C%22auto_next%22:1%2C%22auto_skip_intro%22:1%2C%22show_comments_at_home%22:1%2C%22public_watch_list%22:0%2C%22enable_dub%22:0%2C%22anime_name%22:%22en%22%2C%22play_original_audio%22:0}; watched_19353=true; watched_19321=true",
                "Referer": video_url,
            }
            response = self.session.get(url, headers=headers)
            # response.raise_for_status()
            # print(response.status_code)
            # srcs_data = response.json()
            srcs_data = load(response)

            if not srcs_data:
                raise ValueError("Url may have an invalid video id")

            encrypted_string = srcs_data.get("sources")
            print(srcs_data)
            if not srcs_data["encrypted"] and isinstance(encrypted_string, list):
                result["intro"] = srcs_data.get("intro")
                result["outro"] = srcs_data.get("outro")
                result["subtitles"] = [
                    {"url": s["file"], "lang": s.get("label", "Thumbnails")}
                    for s in srcs_data["tracks"]
                ]
                result["sources"] = [
                    {"url": s["file"], "type": s["type"], "isM3U8": ".m3u8" in s["file"]}
                    for s in encrypted_string
                ]
                return result

            script_url = f"https://megacloud.tv/js/player/a/prod/e1-player.min.js?v={int(time.time())}"
            script_response = requests.get(script_url)
            script_response.raise_for_status()

            text = script_response.text
            if not text:
                raise ValueError("Couldn't fetch script to decrypt resource")

            vars_ = self.extract_variables(text)
            secret, encrypted_source = self.get_secret(encrypted_string, vars_)
            decrypted = self.decrypt(encrypted_source, secret).strip("").strip("")
            try:
                sources = json.loads(decrypted)
                result["intro"] = srcs_data.get("intro")
                result["outro"] = srcs_data.get("outro")
                result["subtitles"] = [
                    {"url": s["file"], "lang": s.get("label", "Thumbnails")}
                    for s in srcs_data["tracks"]
                ]
                result["sources"] = [
                    {"url": s["file"], "type": s["type"], "isM3U8": ".m3u8" in s["file"]}
                    for s in sources
                ]

                return result
            except Exception as error:
                raise ValueError("Failed to decrypt resource") from error

        except Exception as e:
            raise e

    def extract_variables(self, text: str) -> List[Tuple[int, int]]:
        regex = r"case\s*0x[0-9a-f]+:(?![^;]*=partKey)\s*\w+\s*=\s*(\w+)\s*,\s*\w+\s*=\s*(\w+);"
        matches = re.finditer(regex, text)
        vars_ = []

        for match in matches:
            try:
                match_key1 = self.matching_key(match.group(1), text)
                match_key2 = self.matching_key(match.group(2), text)
                vars_.append((int(match_key1, 16), int(match_key2, 16)))
            except ValueError:
                continue

        return vars_

    def get_secret(self, encrypted_string: str, values: List[Tuple[int, int]]) -> Tuple[str, str]:
        secret = ""
        encrypted_source_array = list(encrypted_string)
        current_index = 0

        for start, length in values:
            start += current_index
            end = start + length

            for i in range(start, end):
                secret += encrypted_string[i]
                encrypted_source_array[i] = ""

            current_index += length

        encrypted_source = "".join(encrypted_source_array)
        return secret, encrypted_source

    def decrypt(self, encrypted: str, key_or_secret: str, maybe_iv: Optional[str] = None) -> str:
        if maybe_iv:
            key = key_or_secret
            iv = maybe_iv
            contents = encrypted
        else:
            cipher = base64.b64decode(encrypted)
            salt = cipher[8:16]
            password = key_or_secret.encode("utf-8") + salt
            md5_hashes = []

            digest = password
            for _ in range(3):
                md5 = hashlib.md5(digest).digest()
                md5_hashes.append(md5)
                digest = md5 + password

            key = md5_hashes[0] + md5_hashes[1]
            iv = md5_hashes[2]
            contents = cipher[16:]

        decipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = decipher.decrypt(contents).decode("utf-8")
        return decrypted

    def matching_key(self, value: str, script: str) -> str:
        regex = fr",{value}=((?:0x)?[0-9a-fA-F]+)"
        match = re.search(regex, script)
        if match:
            return match.group(1).lstrip("0x")
        else:
            raise ValueError("Failed to match the key")
