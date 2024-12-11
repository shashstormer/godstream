import re
import threading
from fastapi import FastAPI
from database import Database
from database.cacher import Cacher
from mapper.map_animes import MapperUtils, Mapper
from streamable import caller
import time
import secrets
import datetime
import random


class Mapped:
    def __init__(self, streamable_cache: Cacher, mapper_utils: MapperUtils, sources_cache: Cacher):
        """
        Mapped class interacts with the database to fetch cached data.
        If data is not available, it triggers the Mapper in a background thread.
        """
        self.database = Database("storm_stream", "anime")
        self.streamable_cache = streamable_cache
        self.mapper = Mapper(streamable_cache)
        self.running_threads = []  # Store like [[[method, queryXs], thread], ...]
        self.lock = threading.Lock()
        self.mapper_utils = mapper_utils
        self.sources_cache = sources_cache
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
        td = threading.Thread(target=self.mapper_utils.run_mapper, args=(self.streamable_cache, method, queryXs))
        self.running_threads.append([[method, queryXs], td])
        td.start()

    @staticmethod
    def _shuffle(lst):
        shuffled = lst[:]
        for i in range(len(shuffled) - 1, 0, -1):
            # Pick a random index from 0 to i
            j = secrets.randbelow(i + 1)
            # Swap elements
            shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
        return shuffled

    @staticmethod
    def _hourly_shuffle(lst):
        # Use the current hour as the seed
        current_hour = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
        seed = int(current_hour.timestamp())  # Use the UNIX timestamp for the hour as a seed

        # Initialize a random generator with the seed
        rng = random.Random(seed)

        # Create a shuffled copy of the list
        shuffled = lst[:]
        for i in range(len(shuffled) - 1, 0, -1):
            j = rng.randint(0, i)  # Use deterministic rng for consistent shuffle
            shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
        return shuffled

    @staticmethod
    def _half_hourly_shuffle(lst):
        # Use the current half-hour as the seed
        now = datetime.datetime.now()
        current_half_hour = now.replace(
            minute=(0 if now.minute < 30 else 30),
            second=0,
            microsecond=0
        )
        seed = int(current_half_hour.timestamp())  # Use the UNIX timestamp for the half-hour as a seed

        # Initialize a random generator with the seed
        rng = random.Random(seed)

        # Create a shuffled copy of the list
        shuffled = lst[:]
        for i in range(len(shuffled) - 1, 0, -1):
            j = rng.randint(0, i)  # Use deterministic rng for consistent shuffle
            shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
        return shuffled

    @staticmethod
    def _sort_episodes(episode_list):
        def extract_episode_number(name):
            # Match episode numbers in the format "Episode <number>" or "<number>:"
            match = re.search(r'(\d+)', name)
            return int(match.group(1)) if match else float('inf')  # Return a high value if no number is found

        # Sort the list using the extracted episode numbers
        return sorted(episode_list, key=lambda x: extract_episode_number(x['name']))

    @staticmethod
    def normalize_source(source):
        """
        Normalize the source URL to be accessible by the frontend.
        """
        src = {
            "sources": source.get("sources", []),
            "tracks": source.get("tracks", []),
            "thumbnails": source.get("thumbnails", []),
            "title": source.get("title", ""),
            "image": source.get("image", ""),
            "intro": source.get("intro", {}),
            "outro": source.get("outro", {}),
            "download_url": source.get("download_url", ""),
        }
        src["sources"].extend(source.get("source", []))
        src["sources"].extend(source.get("source_bk", []))
        src["tracks"].extend(source.get("subtitles", []))
        tracks = source.get("track", {})
        if isinstance(tracks, dict):
            src["tracks"].extend(tracks.get("tracks", []))
            src["thumbnails"].extend(source.get("track", {}).get("thumbnails", []))
        elif isinstance(tracks, list):
            src["tracks"].extend(tracks)
        print("SOURCE X: ", src)
        for track in src["tracks"]:
            if not isinstance(track, dict):
                print("TRACK: ", track)
                src["tracks"].remove(track)
                continue
            if track.get("kind", "").lower() in ["thumbnails", "thumbnail"]:
                src["tracks"].remove(track)
                src["thumbnails"].append(track)
            elif track.get("lang", "").lower() in ["thumbnails", "thumbnail"]:
                src["tracks"].remove(track)
                src["thumbnails"].append(track)
        source.update(src)
        return source

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
                del anime["_id"]
                if (
                        str(anime.get("episodes", "")) != str(anime.get("sub", "skip"))
                        and str(anime.get("sub", "")) != str(anime.get("dub", "skip"))
                ):
                    ani.append(anime)
            # return ani
            return self._half_hourly_shuffle(ani)
        except Exception as e:
            return {"error": str(e)}

    async def details(self, title):
        """
        Retrieve detailed information for a specific title.
        If not found, triggers Mapper in the background.
        """
        try:
            self._start_mapper("search", {"query": title})
            anime_details = await self.database.title(title)
            if anime_details:
                del anime_details[0]["_id"]  # Remove MongoDB internal ID for cleaner output
                return anime_details[0]
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
                print("EPISODES: ", episodes)
                episodes = self._sort_episodes(episodes)
                print("SORTED EPISODES: ", episodes)
                return episodes
            return []
        except Exception as e:
            return {"error": str(e)}

    async def source(self, episode_id):
        return await caller("source", {"episode_id": episode_id}, self.sources_cache)


def add_mapped(app: FastAPI, streamable_cache, mapper_utils, sources_cache):
    """
    Adds Mapped routes to the FastAPI app.
    """
    mapped = Mapped(streamable_cache, mapper_utils, sources_cache)

    @app.get("/mapped/anime/home")
    async def home():
        return await mapped.home()

    @app.get("/mapped/anime/details")
    async def details(title: str):
        return await mapped.details(title.replace("%20", " "))

    @app.get("/mapped/anime/search")
    async def search(query: str):
        return await mapped.search(query.replace("%20", " "))

    @app.get("/mapped/anime/episodes")
    async def episodes(season_id: str):
        return await mapped.episodes(season_id.replace("%20", " "))

    @app.get("/mapped/anime/source")
    async def episodes(episode_id: str):
        source = await mapped.source(episode_id.replace("%20", " "))
        print("SOURCE: ", source)
        print("SOURCE REMAPPED: ", mapped.normalize_source(source))
        return source

    return mapped
