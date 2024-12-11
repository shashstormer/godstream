import requestez
from fastapi import requests
from requestez.parsers import load
import requests.exceptions
import re
from extractors.utils import AADECODE
import binascii
import base64


class VidGuard:
    def __init__(self):
        self.session = requestez.Session()

    def _infinite_request(self, url, headers):
        while True:
            try:
                return self.session.get(url, headers=headers)
            except (requests.exceptions.ConnectionError,) as e:
                if str(e) == "('Connection aborted.', ConnectionResetError(10054, 'An existing connection was forcibly closed by the remote host', None, 10054, None))":
                    raise e

    def source(self, method_value, _=''):
        pg = self.session.get(method_value)
        r = re.search(r'eval\("window\.ADBLOCKER\s*=\s*false;\\n(.+?);"\);</script', pg)
        r = r.group(1).replace('\\u002b', '+')
        r = r.replace('\\u0027', "'")
        r = r.replace('\\u0022', '"')
        r = r.replace('\\/', '/')
        r = r.replace('\\\\', '\\')
        r = r.replace('\\"', '"')
        r = AADECODE(r, True)
        stream_url = load(r[11:]).get('stream')
        print(stream_url)
        stream_url = self._sig_decode(stream_url)
        return {
            "sources": [{"url": stream_url}]
        }

    @staticmethod
    def _sig_decode(url):
        """Decode the signature-protected URL."""
        sig = url.split('sig=')[1].split('&')[0]
        decoded_sig = ''.join(
            chr((v if isinstance(v, int) else ord(str(v))) ^ 2)
            for v in binascii.unhexlify(sig)
        )
        t = list(base64.b64decode(decoded_sig + '==')[:-5][::-1])

        for i in range(0, len(t) - 1, 2):
            t[i + 1], t[i] = t[i], t[i + 1]
        return url.replace(sig, ''.join(chr(c) for c in t)[:-5])


if __name__ == '__main__':
    vidguard = VidGuard()
    print(vidguard.source("https://listeamed.net/e/3Q0lxBbmD8Vxj1J"))
