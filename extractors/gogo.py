import base64
import requestez
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad, pad
import re
import json
from requestez.parsers import reg_compile, load
from config import Config

KEYS_REGEX = reg_compile(r"(?:container|videocontent)-(\d+)")  # Replace with actual regex
ENCRYPTED_DATA_REGEX = re.compile(r'data-value="(.+?)"')  # Replace with actual regex


class Gogo:
    def __init__(self):
        self.cache = {}  # Assuming a cache dictionary
        self.session = requestez.Session()
        self.main_url = Config.StreamURLS.GogoURLS.gogo_url  # Replace with actual main URL
        self.alternate_domains = ["https://gogoanime3.co/",
                                  "https://ww8.gogoanimes.fi/", ]  # Replace with actual alternate domains

    @staticmethod
    def aes_decrypt(key, iv, string, decode=True, decoded=False, unpad_data=True):
        cip = AES.new(key, AES.MODE_CBC, iv)
        if not decoded:
            string = base64.b64decode(string)
        try:
            string = cip.decrypt(string)
        except ValueError:
            string = pad(string, cip.block_size)
            string = cip.decrypt(string)
        if unpad_data:
            string = unpad(string, cip.block_size)
        if decode:
            string = string.decode("utf-8")
        return string

    @staticmethod
    def aes_encrypt(key, iv, string):
        cip = AES.new(key, AES.MODE_CBC, iv)
        if isinstance(string, str):
            string = string.encode("utf-8")
        string = pad(string, cip.block_size)
        string = cip.encrypt(string)
        return base64.b64encode(string).decode('utf-8')

    def source(self, method_value: str, *__, **_):
        anim_id = method_value.split("/", 1)[-1]
        url_main = f"{self.main_url}/{anim_id}"
        try:
            dt, new = self.cache[url_main]
        except KeyError as e:
            print(e)
            url_main = url_main.replace(self.main_url, self.alternate_domains[0])
            dt, new = self.session.get(url_main), True

        if new:
            x = BeautifulSoup(dt, 'html.parser')
            url = [i['data-video'] for i in x.find_all(class_="anime_muti_link")[0].find_all("a")][0]
            parsed_url = urlparse(url)
            content_id = parse_qs(parsed_url.query)["id"][0]
            next_host = f"https://{parsed_url.netloc}/"
            url = f"https://{parsed_url.netloc}{parsed_url.path}?{parsed_url.query}"
            streaming_page = self.session.get(url)

            encryption_key, iv, decryption_key = (
                _.group(1) for _ in KEYS_REGEX.finditer(streaming_page)
            )

            component = self.aes_decrypt(
                key=encryption_key.encode(),
                iv=iv.encode(),
                string=ENCRYPTED_DATA_REGEX.search(streaming_page).group(1),
            )
            component += f"&id={self.aes_encrypt(key=encryption_key.encode(), iv=iv.encode(), string=content_id)}&alias={content_id}"

            _, component = component.split("&", 1)

            ajax_response = load(self.session.get(
                f"{next_host}encrypt-ajax.php?{component}",
                headers={"x-requested-with": "XMLHttpRequest"},
            ))
            content = self.aes_decrypt(
                string=ajax_response.get("data"),
                key=decryption_key.encode(),
                iv=iv.encode()
            )
            content = json.loads(content)

            download_url = x.select_one("li.dowloads a")
            if download_url:
                try:
                    download_url = download_url["href"]
                except Exception as e:
                    print(e)
                    download_url = ""
            else:
                download_url = ""
            content["download_url"] = download_url
            # ret = {
            #     "source": content["source"][0]["file"] if "source" in content and content["source"] else "",
            #     "alt_src": content["source_bk"][0]["file"] if "source_bk" in content and content["source_bk"] else "",
            #     "thumbnails": [],
            #     "subs": [],
            #     "unknown": [],
            #     "title": anim_id.replace("-", " "),
            #     "download_url": download_url,
            # }
            # if isinstance(content.get("track", {}), list):
            #     del content["track"]
            # for track in content.get("track", {}).get("tracks", []):
            #     if track["kind"] == "thumbnails":
            #         ret["thumbnails"].append(track["file"])
            #     else:
            #         ret["unknown"].append(track)
            self.cache[url_main] = (content, False)
            dt = content

        return dt
