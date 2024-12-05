import threading
from fastapi import FastAPI
from database import Database
from mapper.map_animes import run_mapper, Mapper
from streamable import caller
import time


class Mapped:
    def __init__(self, streamable_cache):
        """
        Mapped class interacts with the database to fetch cached data.
        If data is not available, it triggers the Mapper in a background thread.
        """
        self.database = Database("storm_stream", "anime")
        self.streamable_cache = streamable_cache
        self.mapper = Mapper(streamable_cache)
        self.running_threads = []  # Store like [[[method, queryXs], thread], ...]
        self.lock = threading.Lock()
        threading.Thread(target=self._cleanup_threads).start()

    def _cleanup_threads(self):
        """
        Clean up completed threads from the running_threads list.
        """
        while True:
            with self.lock:
                self.running_threads = [
                    thd for thd in self.running_threads if thd[1].is_alive()
                ]
            time.sleep(5)

    def _start_mapper(self, method, queryXs):
        """
        Starts the Mapper in a background thread for the given method and query parameters.
        """
        with self.lock:
            for thd in self.running_threads:
                if thd[0] == [method, queryXs]:
                    return
        td = threading.Thread(target=run_mapper, args=(self.streamable_cache, method, queryXs))
        self.running_threads.append([[method, queryXs], td])
        td.start()

    async def home(self):
        """
        Retrieve ongoing or recently updated anime from the database.
        """
        try:
            self._start_mapper("home", {})
            current_time = time.time()
            thirty_days_ago = current_time - 30 * 24 * 60 * 60
            ongoing_anime = self.database.collection.find({
                "$or": [
                    {"status": "Currently Airing"},
                    {"time_seasons": "Ongoing"},
                    {"updated_on": {"$gte": thirty_days_ago}}
                ]
            })
            ani = []
            async for anime in ongoing_anime:
                del ani["_id"]
                ani.append(anime)
            return ani
        except Exception as e:
            return {"error": str(e)}

    async def details(self, title):
        """
        Retrieve detailed information for a specific title.
        If not found, triggers Mapper in the background.
        """
        try:
            self._start_mapper("search", {"query": title})
            anime_details = await self.database.collection.find_one({"title": title})
            if anime_details:
                del anime_details["_id"]  # Remove MongoDB internal ID for cleaner output
                return anime_details
            return {"status": "Details not available yet. Mapper triggered for update."}
        except Exception as e:
            return {"error": str(e)}

    async def search(self, query):
        """
        Search for anime based on a query string.
        """
        try:
            self._start_mapper("search", {"query": query})
            search_results = []
            for anime in await self.database.title(query):
                del anime["_id"]
                search_results.append(anime)
            if search_results:
                return search_results
            return {"status": "No results found in cache. Mapper triggered for update."}
        except Exception as e:
            return {"error": str(e)}

    async def episodes(self, season_id):
        """
        Retrieve episodes for a specific season from the database or trigger Mapper.
        """
        try:
            self._start_mapper("get_episodes", {"season_id": season_id})
            episodes = await self.mapper.get_episodes({"season_id": season_id})
            if episodes:
                return episodes
            return {"status": "Episodes not available yet. Mapper triggered for update."}
        except Exception as e:
            return {"error": str(e)}

    async def source(self, episode_id):
        return await caller("source", {"episode_id": episode_id}, self.streamable_cache)


def add_mapped(app: FastAPI, streamable_cache):
    """
    Adds Mapped routes to the FastAPI app.
    """
    mapped = Mapped(streamable_cache)

    @app.get("/mapped/anime/home")
    async def home():
        return await mapped.home()

    @app.get("/mapped/anime/details")
    async def details(title: str):
        return await mapped.details(title)

    @app.get("/mapped/anime/search")
    async def search(query: str):
        return await mapped.search(query)

    @app.get("/mapped/anime/episodes")
    async def episodes(season_id: str):
        return await mapped.episodes(season_id)

    @app.get("/mapped/anime/source")
    async def episodes(episode_id: str):
        return await mapped.source(episode_id)
