import requestez
from fastapi import requests
from requestez.parsers import load, regex
import requests.exceptions
import json
from Crypto.Cipher import AES
from Crypto.Util import Counter


class CryptoHelper:
    def __init__(self):
        self.decryption_key = "RB0fpH8ZEyVLkv7c2i6MAJ5u3IKFDxlS1NTsnGaqmXYdUrtzjwObCgQP94hoeW+/="

    def decode_encrypted_string(self, encrypted_input: str):
        if encrypted_input is not None:
            sanitized_input = encrypted_input
            decoded_string = ""
            sanitized_input = self.sanitize_input(sanitized_input)
            index = 0
            while index < len(sanitized_input):
                first_char_value = (self.decryption_key.index(sanitized_input[index]) << 2) | (
                        self.decryption_key.index(sanitized_input[index + 1]) >> 4)
                second_char_value = self.decryption_key.index(sanitized_input[index + 1])
                third_char_value = (second_char_value & 0xf) << 4 | (
                        self.decryption_key.index(sanitized_input[index + 2]) >> 2)
                fourth_char_value = self.decryption_key.index(sanitized_input[index + 2])
                fifth_char_value = (fourth_char_value & 0x3) << 6 | self.decryption_key.index(
                    sanitized_input[index + 3])

                decoded_string += chr(first_char_value)
                if fourth_char_value != 0x40:
                    decoded_string += chr(third_char_value)
                if fifth_char_value != 0x40:
                    decoded_string += chr(fifth_char_value)

                index += 4

            # Convert to Video object
            try:
                return json.loads(self.decode_utf8_string(decoded_string))
            except json.JSONDecodeError as e:
                return None
        else:
            return None

    @staticmethod
    def sanitize_input(input_string: str):
        return ''.join(c for c in input_string if c.isalnum() or c in "+/=")

    @staticmethod
    def decode_utf8_string(input_string: str):
        result = ""
        i = 0
        while i < len(input_string):
            char_code = ord(input_string[i])
            if char_code < 0x80:
                result += chr(char_code)
                i += 1
            elif char_code in range(0xc0, 0xdf):
                next_char_code = ord(input_string[i + 1])
                result += chr(((char_code & 0x1f) << 6) | (next_char_code & 0x3f))
                i += 2
            else:
                next_code = ord(input_string[i + 1])
                third_char_code = ord(input_string[i + 2])
                result += chr(((char_code & 0xf) << 12) | ((next_code & 0x3f) << 6) | (third_char_code & 0x3f))
                i += 3
        return result

    @staticmethod
    def init_cipher(mode, key: str):
        key_bytes = key.encode("utf-8")
        iv = key_bytes[:16]
        cipher = AES.new(key_bytes, AES.MODE_CTR, counter=Counter.new(128, initial_value=int.from_bytes(iv, "big")))
        return cipher

    def encrypt_aes_ctr(self, data: str, key: str):
        cipher = self.init_cipher(AES.MODE_ENCRYPT, key)
        data_bytes = data.encode("utf-8")
        encrypted_bytes = cipher.encrypt(data_bytes)
        return encrypted_bytes.decode("ISO-8859-1")

    def decrypt_aes_ctr(self, data: bytes, key: str):
        cipher = self.init_cipher(AES.MODE_DECRYPT, key)
        return cipher.decrypt(data)

    def get_key(self, value):
        # You can replace this with the JS function to generate key if needed.
        return self.generate_key(value)

    def generate_key(self, video_id: str):
        if video_id is None:
            raise ValueError(f"Illegal argument {video_id}")
        # Assuming video_id is a string to be processed into a key
        return self.bytes_to_hex(self.words_to_bytes(self.encoder(video_id)))

    @staticmethod
    def words_to_bytes(words):
        byte_array = []
        index = 0
        for i in range(32 * len(words)):
            byte_array.append((words[i >> 5] >> (24 - (i % 32))) & 255)
        return byte_array

    @staticmethod
    def encoder(input_str):
        # The encoder function that converts string to bytes (similar to the JavaScript encoder)
        return [ord(c) for c in input_str]

    @staticmethod
    def bytes_to_hex(bytes_data):
        return ''.join(f"{byte:02x}" for byte in bytes_data)


# Sample usage
crypto_helper = CryptoHelper()


# encrypted_input = "your_encrypted_string_here"
# video = crypto_helper.decode_encrypted_string(encrypted_input)
# print(video)


class AbyssCDN:
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
        headers = {'Referer': domain, 'Sec-Fetch-Dest': 'iframe', }
        pg = self._infinite_request(method_value, headers=headers)
        reg = r'atob\(\"([^"]+)'
        reg_res = regex(pg, reg)[0]
        decoded = load(crypto_helper.decode_encrypted_string(reg_res))
        print(decoded)
        # for source in decoded["sources"]:
        #     source["file"] = crypto_helper.decrypt_aes_ctr(source[""], crypto_helper.get_key(decoded["video_id"]))

    def download_abyss(self, decoded_data):
        pass





if __name__ == "__main__":
    abysscdn = AbyssCDN()
    print(abysscdn.source("https://short.ink/pAWXk3rv7", "https://animekhor.org/"))
