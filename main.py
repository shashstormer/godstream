import fastapi
import uvicorn
from starlette.middleware.cors import CORSMiddleware
from streamable import add_streamable
from mapper import add_mappers
from mapper.map_animes import MapperUtils
from database.cacher import Cacher
from mapped import add_mapped
import threading
from config import Config
from cors.cors_route import add_cors
import time
import traceback
from store_data import add_user_datastorage
import os
import sys


def thread_trace(frame, event, arg):
    if event == "call":
        print(f"Thread {threading.current_thread().name} starting:")
        for line in traceback.format_stack(frame):
            print(line.strip())


# Set the trace function for all threads
# threading.settrace(thread_trace)
app = fastapi.FastAPI()
streamable_cache = Cacher("streamable_anime")
sources_cache = Cacher()
# streamable_cache = Cacher()
recent_cache = Cacher("recent_pages")
# cors_cache = Cacher("cors_cache")
cors_cache = Cacher()
mapper_utils = MapperUtils()


@app.get("/")
async def root():
    return {"Hello": "World"}


@app.get("/stop")
async def exit_pgm():
    try:
        os._exit(9)
    except Exception as e:
        print(e)
        try:
            sys._exit(9)
        except Exception as e:
            print(e)
            sys.exit(9)
    return {"status": "unknown"}



app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Adjust this to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

add_streamable(app, cache_store=streamable_cache)
if Config.enable_cors_proxy:
    executor, request_executor, cors_files_cache = add_cors(app, "*", cors_cache)
if Config.mongo_url:
    mapper_obj = add_mappers(app, streamable_cache=streamable_cache)
    mapped_obj = add_mapped(app, streamable_cache=streamable_cache, mapper_utils=mapper_utils,
                            sources_cache=sources_cache)
    # threading.Thread(target=mapper_utils.create_map_multithread, args=(streamable_cache, recent_cache, 10)).start()
add_user_datastorage(app)

print("Running on http://127.0.0.1:5636")
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5636)
    streamable_cache.stop_cleanup_thread()
    recent_cache.stop_cleanup_thread()
    cors_cache.stop_cleanup_thread()
    mapper_utils.running = False
    if Config.enable_cors_proxy:
        cors_files_cache.stop_cleanup_thread()
        executor.shutdown(wait=False, cancel_futures=True)
        request_executor.shutdown(wait=False, cancel_futures=True)
    if Config.mongo_url:
        mapper_obj.database.shutdown()
        mapped_obj.database.shutdown()
    while True:
        time.sleep(10)
        print(threading.enumerate())
