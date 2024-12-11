import asyncio
import os
from fastapi import Request, Response
from urllib.parse import quote, unquote
from requestez import Session
import requests.exceptions
from config import Config
from database.cacher import Cacher
from concurrent.futures import ThreadPoolExecutor
import threading

# Initialize global components
session = Session()
lock = threading.Lock()
processing = {}
# cors_files_cache = Cacher("cors_files_cache")
cors_files_cache = Cacher()

# Create a ThreadPoolExecutor with a maximum of 100 threads
executor = ThreadPoolExecutor(max_workers=1)
request_executor = ThreadPoolExecutor(max_workers=1000)


def safe_sub(url):
    return quote(url)


def get_cors_hash(request: Request):
    cors_data = {"origin": request.headers.get("origin"), "url": request.query_params.get("url"),
                 "type": request.query_params.get("type")}
    return cors_data


def fetch_and_cache_seg(url):
    """
    Fetches and caches the requested segment in the cors_files_cache.
    """
    while True:
        try:
            cors_files_cache.set("GET", {"url": url}, {}, session.get(url, text=False, notify=False), 3600)
            break
        except requests.exceptions.ConnectionError:
            pass


def precache_m3u8_seg(url):
    """
    Offloads the task of fetching and caching a segment to the thread pool.
    """
    pass
    # executor.submit(fetch_and_cache_seg, url)


def cors(request: Request, origins, cors_cache: Cacher) -> Response:
    """
    Handles CORS proxying for requests and ensures proper origin validation and response handling.
    """
    cors_data = get_cors_hash(request)
    current_domain = request.headers.get("origin")
    if current_domain is None:
        current_domain = origins
    if current_domain not in origins.replace(", ", ",").split(",") and origins != "*":
        return Response()
    if not request.query_params.get('url'):
        return Response()
    file_type = request.query_params.get('type')
    url = unquote(request.query_params.get('url'))
    if url.endswith("/video/"):
        file_type = "m3u8"
    main_url = Config.cors_proxy_url
    while True:
        try:
            resp = cors_files_cache.get("GET", {"url": url}, {})
            if not resp:
                headers = None
                if "/anime/" in url and (".m3u8" in url or ".ts" in url):
                    headers = {
                        "Cookie": "PHPSESSID=0;__ddgid_=; __ddg2_=; __ddg1_=;",
                        "referer": url.replace("/anime/", "/embed/"),
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-dest": "empty",
                        "sec-fetch-mode": "cors",
                        "sec-ch-ua-platform": '"Windows"'
                    }
                resp = session.get(url,
                                   text=False,
                                   headers=headers
                                   # notify=False
                                   )
                headers = resp.headers
                content = resp.content
                code = resp.status_code
            else:
                headers = resp[2]
                content = resp[0]
                code = resp[1]
            item_domain = "https://" + url.split('?')[0].split("/")[2]
            break
        except requests.exceptions.ConnectionError:
            pass
    headers['Access-Control-Allow-Origin'] = current_domain

    del_keys = [
        'Vary',
        'Content-Encoding',
        'Transfer-Encoding',
        'Content-Length',
    ]
    for key in del_keys:
        headers.pop(key, None)

    if (file_type == "m3u8" or ".m3u8" in url) and code != 404:
        content = content.decode("utf-8")
        new_content = ""
        for line in content.split("\n"):
            if line.startswith("#"):
                new_content += line
            elif line.startswith('/'):
                new_content += main_url + safe_sub(item_domain + line)
                precache_m3u8_seg(item_domain + line)
            elif line.startswith('http'):
                new_content += main_url + safe_sub(line)
                precache_m3u8_seg(line)
            elif line.strip(' '):
                new_content += main_url + safe_sub(
                    item_domain +
                    '/'.join(str(url.replace(item_domain, "")).split('?')[0].split('/')[:-1]) +
                    '/' +
                    safe_sub(line)
                )
                precache_m3u8_seg(item_domain +
                                  '/'.join(str(url.replace(item_domain, "")).split('?')[0].split('/')[:-1]) +
                                  '/' + line)
            new_content += "\n"
        content = new_content
    if "location" in headers:
        if headers["location"].startswith("/"):
            headers["location"] = item_domain + headers["location"]
        headers["location"] = main_url + headers["location"]
    resp = Response(content, code, headers=headers)
    resp.set_cookie("_last_requested", item_domain, max_age=3600, httponly=True)
    cors_cache.set("CORS", cors_data, {}, [content, code, dict(headers)], 3600)
    return resp


def background_cors(request: Request, origins, cors_cache: Cacher):
    """
    Executes CORS logic in the background using the thread pool to prevent blocking.
    """
    cors_data = get_cors_hash(request)
    cors_hash = cors_cache.generate_key("CORS", cors_data, {})
    if cors_cache.get("CORS", cors_data, {}):
        return
    with lock:
        if processing.get(cors_hash, False):
            return
        processing[cors_hash] = True

    # Use the executor to submit the CORS task
    request_executor.submit(cors, request, origins, cors_cache)
    with lock:
        processing.pop(cors_hash, None)


def add_cors(app, origins, cors_cache: Cacher):
    """
    Adds the CORS endpoint to the FastAPI application.
    """
    cors_path = os.getenv('cors_url', '/cors')

    @app.get(cors_path)
    async def cors_caller(request: Request) -> Response:
        cors_data = get_cors_hash(request)
        background_cors(request, origins, cors_cache)
        while True:
            resp = cors_cache.get("CORS", cors_data, {})
            if resp:
                return Response(resp[0], resp[1], headers=resp[2])
            await asyncio.sleep(1)

    return executor, request_executor, cors_files_cache
