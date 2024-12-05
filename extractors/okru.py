import requestez
from requestez.parsers import load, html
import requests.exceptions


class OkRu:
    def __init__(self):
        self.session = requestez.Session()

    def _infinite_request(self, url):
        while True:
            try:
                return self.session.get(url)
            except (requests.exceptions.ConnectionError,):
                pass

    @staticmethod
    def _format(qualities):
        result = {
            "sources": []
        }
        for quality, url in qualities.items():
            if quality == "auto":
                result["sources"].append({
                    "url": url,
                    "type": "hls",
                    "isM3U8": ".m3u8" in url,
                    "label": "auto"
                })
            else:
                result["sources"].append({
                    "url": url,
                    "type": "video/mp4",
                    "label": quality
                })
        return result

    def source(self, method_value: str, *_, **__):
        pg = self._infinite_request(method_value)
        pg = html(pg)
        dt = load(pg.select_one('div[data-module="OKVideo"]')['data-options'], iterate=True)
        m3u8_url = dt['flashvars']['metadata']['hlsManifestUrl']
        qualities = {"auto": m3u8_url}
        for i in dt['flashvars']['metadata']['videos']:
            qualities[i['name']] = i['url']
        return self._format(qualities)


if __name__ == '__main__':
    import extractors

    print(OkRu().source(extractors.test_urls["okru"]))
