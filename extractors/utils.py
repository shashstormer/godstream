import base64
import re
import urllib.parse as urllib
from requestez.parsers import regex
from requestez.helpers import log


def DEJUICE(content):
    def find_single_match(data, patron, index=0):
        try:
            if index == 0:
                matches = re.search(patron, data, flags=re.DOTALL)
                if matches:
                    if len(matches.groups()) == 1:
                        return matches.group(1)
                    elif len(matches.groups()) > 1:
                        return matches.groups()
                    else:
                        return matches.group()
                else:
                    return ""
            else:
                matches = re.findall(patron, data, flags=re.DOTALL)
                return matches[index]
        except Exception as e:
            print(e)
            return ""

    def dejuice(data):
        juiced = find_single_match(data, r'JuicyCodes.Run\((.*?)\);')
        b64_data = juiced.replace('+', '').replace('"', '')
        b64_decode = base64.b64decode(b64_data)
        dejuiced = PACKER(b64_decode)
        return dejuiced

    return dejuice(data=content)


def PACKER(string, cust_pattern=None):
    class CPacker:
        @staticmethod
        def detect(source):
            """Detects whether `source` is P.A.C.K.E.R. coded."""
            return source.replace(' ', '').startswith('eval(function(p,a,c,k,e,')

        def unpack(self, source):
            """Unpacks P.A.C.K.E.R. packed js code."""
            payload, symtab, radix, count = self._filter_args(source)

            # correction pour eviter bypass
            if (len(symtab) > count) and (count > 0):
                del symtab[count:]
            if (len(symtab) < count) and (count > 0):
                symtab.append('BUGGED')

            if count != len(symtab):
                raise UnpackingError('Malformed p.a.c.k.e.r. symtab.')

            try:
                unbase = Unbaser(radix)
            except TypeError:
                raise UnpackingError('Unknown p.a.c.k.e.r. encoding.')

            def lookup(match):
                """Look up symbols in the synthetic symtab."""
                word = match.group(0)
                return symtab[unbase(word)] or word

            source = re.sub(r'\b\w+\b', lookup, payload)
            return self._replace_strings(source)

        @staticmethod
        def _clean_str(_str):
            _str = _str.strip()
            if _str.find("function") == 0:
                _pattern = r"=\"([^\"]+).*}\s*\((\d+)\)"
                args = re.search(_pattern, _str, re.DOTALL)
                if args:
                    a = args.groups()

                    def openload_re(match):
                        c = match.group(0)
                        b = ord(c) + int(a[1])
                        return chr(b if (90 if c <= "Z" else 122) >= b else b - 26)

                    _str = re.sub(r"[a-zA-Z]", openload_re, a[0])
                    _str = urllib.unquote(_str)

            elif _str.find("decodeURIComponent") == 0:
                _str = re.sub(r"(^decodeURIComponent\s*\(\s*(['\"]))|((['\"])\s*\)$)", "", _str)
                _str = urllib.unquote(_str)
            elif _str.find("\"") == 0:
                _str = re.sub(r"(^\")|(\"$)|(\".*?\")", "", _str)
            elif _str.find("'") == 0:
                _str = re.sub(r"(^')|('$)|('.*?')", "", _str)

            return _str

        def _filter_args(self, source):
            """Juice from a source file the four args needed by decoder."""

            source = source.replace(',[],', ',0,').replace("\\'", "'")

            juicer = r"}\s*\(\s*(.*?)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*\((.*?)\).split\((.*?)\)"
            args = re.search(juicer, source, re.DOTALL)
            if args:
                a = args.groups()
                try:
                    return self._clean_str(a[0]), self._clean_str(a[3]).split(self._clean_str(a[4])), int(a[1]), \
                        int(a[2])
                except ValueError:
                    raise UnpackingError('Corrupted p.a.c.k.e.r. data.')

            juicer = r"}\('(.*)', *(\d+), *(\d+), *'(.*)'\.split\('(.*?)'\)"
            #           juicer = (r"}\(\\'(.*)', *(\d+), *(\d+), *\\'(.*)'\.split\(\\'(.*?)\\'\)")
            args = re.search(juicer, source, re.DOTALL)
            if args:
                a = args.groups()
                try:
                    return a[0], a[3].split(a[4]), int(a[1]), int(a[2])
                except ValueError:
                    raise UnpackingError('Corrupted p.a.c.k.e.r. data.')

            # could not find a satisfying regex
            raise UnpackingError('Could not make sense of p.a.c.k.e.r data (unexpected code structure)')

        @staticmethod
        def _replace_strings(source):
            """Strip string lookup table (list) and replace values in source."""
            match = re.search(r'var *(_\w+)=\["(.*?)"];', source, re.DOTALL)

            if match:
                varname, strings = match.groups()
                startpoint = len(match.group(0))
                lookup = strings.split('","')
                variable = '%s[%%d]' % varname
                for index, value in enumerate(lookup):
                    source = source.replace(variable % index, '"%s"' % value)
                return source[startpoint:]
            return source

    def UnpackingError(err):
        # Badly packed source or general error.#
        log(err, log_level="e", color="red")

    class Unbaser(object):
        """Functor for a given base. Will efficiently convert
    strings to natural numbers."""
        ALPHABET = {
            62: '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',
            95: (r' !"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                 r'[\]^_`abcdefghijklmnopqrstuvwxyz{|}~')
        }

        def __init__(self, base):
            self.base = base

            # Error not possible, use 36 by default
            if base == 0:
                base = 36

            # If base can be handled by int() builtin, let it do it for us
            if 2 <= base <= 36:
                self.unbase = lambda _string: int(_string, base)
            else:
                if base < 62:
                    self.ALPHABET[base] = self.ALPHABET[62][0:base]
                elif 62 < base < 95:
                    self.ALPHABET[base] = self.ALPHABET[95][0:base]
                # Build conversion dictionary cache
                try:
                    self.dictionary = dict((cipher, index) for index, cipher in enumerate(self.ALPHABET[base]))
                except KeyError:
                    raise TypeError('Unsupported base encoding.')

                self.unbase = self._dict_unbaser

        def __call__(self, _string):
            return self.unbase(_string)

        def _dict_unbaser(self, _string):
            """Decodes a  value to an integer."""
            ret = 0
            for index, cipher in enumerate(_string[::-1]):
                ret += (self.base ** index) * self.dictionary[cipher]
            return ret

    pattern = r'(eval\(function\(p,a,c,k,e(?:.|\s)+?\))<\/script>'
    if cust_pattern is not None:
        pattern = cust_pattern
    result = regex(string, pattern)
    if len(result) > 0:
        result = [True, result]
    # print("RESULT: \n", result)
    if result[0] is True:
        string = CPacker().unpack(result[1][0])
    # print("STRING: \n", string)
    return string
