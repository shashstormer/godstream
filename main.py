import fastapi
import uvicorn
from streamable import add_streamable
from mapper import add_mappers
from mapper.map_animes import create_map_multithread
from database.cacher import Cacher
from mapped import add_mapped
import threading
from config import Config


app = fastapi.FastAPI()
streamable_cache = Cacher("streamable_anime")
recent_cache = Cacher("recent_pages")


@app.get("/")
async def root():
    return {"Hello": "World"}


add_streamable(app, cache_store=streamable_cache)
if Config.mongo_url:
    add_mappers(app, streamable_cache=streamable_cache)
    add_mapped(app, streamable_cache=streamable_cache)
    threading.Thread(target=create_map_multithread, args=(streamable_cache, recent_cache, 10)).start()

print("Running on http://127.0.0.1:5636")
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5636)
