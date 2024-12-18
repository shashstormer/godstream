import requestez
from fastapi import requests
from requestez.parsers import html, load
from extractors.utils import PACKER
import requests.exceptions
import re


class FileMoon:
    def __init__(self):
        self.session = requestez.Session()

    def _infinite_request(self, url, headers):
        while True:
            try:
                return self.session.get(url, headers=headers)
            except (requests.exceptions.ConnectionError,) as e:
                if str(e) == "('Connection aborted.', ConnectionResetError(10054, 'An existing connection was forcibly closed by the remote host', None, 10054, None))":
                    raise e

    def source(self, method_value, domain):
        headers = {'Referer': domain, 'Sec-Fetch-Dest': 'iframe'}
        pg = self._infinite_request(method_value, headers=headers)
        pg = html(pg)
        ifu = pg.select_one('iframe')['src']
        headers["Referer"] = method_value
        ifp = self._infinite_request(ifu, headers=headers)
        pkd = PACKER(ifp)
        pkd = pkd.replace("'", '"')
        pkd = re.sub(r'(\w+):', r'"\1":', pkd)
        pkd = load(re.search(r'jwplayer\("vplayer"\);videop\.setup\((\{.*?\})\)', pkd, re.DOTALL).group(1).replace('""https"://', '"https://').replace('="https":', '=https:'))
        print(pkd)
        pkd.pop("advertising", "")
        pkd.pop("skin", "")
        pkd.pop("displaytitle", "")
        pkd.pop("abouttext", "")
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
        return pkd


if __name__ == '__main__':
    filemoon = FileMoon()
    print(filemoon.source("https://filemoon.sx/e/6toq00rr3fq3", "https://animekhor.org/myth-of-the-ancients-wangu-shenhua-episode-244-subtitles-english-indonesian/"))
