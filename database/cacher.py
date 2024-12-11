import hashlib
import json
import os
import threading
import time
from config import Config


class Cacher:
    def __init__(self, cacher_name=""):
        self.cache = {}
        self.lock = threading.Lock()
        self.running = False
        self.cacher_name = cacher_name
        self.cache_file = f"{self.cacher_name}.json"
        if Config.is_local:
            try:
                with open(self.cache_file) as f:
                    self.cache = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                if os.path.exists(self.cache_file + ".temp"):
                    with open(self.cache_file + ".temp") as f:
                        try:
                            self.cache = json.load(f)
                        except (json.JSONDecodeError, ):
                            pass

            self.start_cleanup_thread()

    @staticmethod
    def generate_key(method, data, account):
        # Create a unique key based on the method, data, and account
        data_str = json.dumps(data, sort_keys=True) if data else ""
        account_str = json.dumps(account, sort_keys=True) if account else ""
        key = f"{method}:{data_str}:{account_str}"
        return hashlib.sha256(key.encode()).hexdigest()

    def get(self, method, data, account):
        key = self.generate_key(method, data, account)
        with self.lock:
            res = self.cache.get(key)
            if res:
                return res["response"]
            return res

    def set(self, method, data, account, response, ttl):
        key = self.generate_key(method, data, account)
        with self.lock:
            self.cache[key] = {
                "response": response,
                "expires_at": time.time() + ttl
            }

    def cleanup(self):
        # Clean up expired cache entries and try to save to local file system
        current_time = time.time()
        with self.lock:
            keys_to_delete = [key for key, value in self.cache.items() if
                              value.get("expires_at", current_time + 1) < current_time]
            for key in keys_to_delete:
                del self.cache[key]
        if self.cacher_name:
            try:
                with open(self.cache_file + ".temp", "wt") as f:
                    json.dump(self.cache.copy(), f, indent=4)
                while os.path.exists(self.cache_file):
                    os.remove(self.cache_file)
                    time.sleep(1)
                os.rename(self.cache_file + ".temp", self.cache_file)
            except TypeError:
                print("Not Supported")
                self.running = False

    def cleanup_thread(self):
        while self.running:
            time.sleep(30)
            try:
                self.cleanup()
            except Exception as e:
                print("Cleanup Error: ", e)

    def start_cleanup_thread(self):
        if self.running:
            return False
        self.running = True
        threading.Thread(target=self.cleanup_thread, daemon=True).start()
        return True

    def stop_cleanup_thread(self):
        if not self.running:
            return False
        self.running = False
        return True
