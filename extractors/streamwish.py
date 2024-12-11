import requestez
from fastapi import requests
from requestez.parsers import html, load
from extractors.utils import PACKER
import requests.exceptions
import re


class StreamWish:
    def __init__(self):
        self.session = requestez.Session()

    def _infinite_request(self, url, headers):
        while True:
            try:
                return self.session.get(url, headers=headers)
            except (requests.exceptions.ConnectionError,):
                pass

    def source(self, method_value, domain):
        headers = {'Referer': domain, 'Sec-Fetch-Dest': 'iframe'}
        pg = self._infinite_request(method_value, headers=headers)
        pkd = PACKER(pg)
        pkd = pkd.replace("'", '"')
        pkd = re.sub(r'(\w+):', r'"\1":', pkd)
        pkd = load(re.search(r'jwplayer\("vplayer"\)\.setup\((\{.*?\})\)', pkd, re.DOTALL).group(1).replace('""https"://', '"https://').replace('="https":', '=https:').replace(",}", "}"))
        pkd.pop("advertising", "")
        pkd.pop("skin", "")
        pkd.pop("displaytitle", "")
        pkd.pop("abouttext", "")
        pkd.pop("androidhls", "")
        pkd.pop("aboutlink", "")
        pkd.pop("playbackRateControls", "")
        pkd.pop("playbackRates", "")
        pkd.pop("fullscreenOrientationLock", "")
        pkd.pop("startparam", "")
        pkd.pop("cast", "")
        pkd.pop("stretching", "")
        pkd.pop("preload", "")
        pkd.pop("width", "")
        pkd.pop("height", "")
        pkd.pop("captions", "")
        pkd.pop("logo", "")
        pkd.pop("debug", "")
        return pkd


if __name__ == '__main__':
    filemoon = StreamWish()
    print(filemoon.source("https://asnwish.com/e/d3hjaxdln5q3", "https://animekhor.org/myth-of-the-ancients-wangu-shenhua-episode-244-subtitles-english-indonesian/"))
    