import time
from fastapi import FastAPI
from database.cacher import Cacher
from streamable import caller
from database import Database


class Mapper:
    def __init__(self, streamable_cache, database=None):
        if database is None:
            self.database = Database("storm_stream", "anime")
        else:
            self.database = database
        self.streamable_cache = streamable_cache

    async def _make_call(self, method, dt):
        return await caller(method, dt, self.streamable_cache)

    def _merge(self, a, b):
        new_d = a.copy()
        for key in b:
            if not new_d.get(key, None):
                new_d.pop(key, None)
            if key in new_d:
                if isinstance(new_d[key], list):
                    if isinstance(b[key], list):
                        if (new_d[key] and isinstance(new_d[key][0], list)) or (b[key] and isinstance(b[key][0], list)):
                            if isinstance(b[key][0], list) and isinstance(new_d[key][0], list):
                                new_d[key].extend(b[key])
                            elif isinstance(b[key][0], list) and isinstance(new_d[key][0], str):
                                new_d[key] = [new_d[key]]
                                new_d[key].extend(b[key])
                            elif isinstance(b[key][0], str) and isinstance(new_d[key][0], list):
                                new_d[key].append(b[key])
                            else:
                                print(
                                    f"List Merge Fault ({key}) ({type(b[key][0])}, {type(new_d[key][0])}): {b[key]}, {new_d[key]}")
                        else:
                            new_d[key].extend(b[key])
                    elif isinstance(b[key], str):
                        if new_d[key] and isinstance(new_d[key][0], str):
                            new_d[key].append(b[key])
                    elif isinstance(b[key], int):
                        if new_d[key] and isinstance(new_d[key][0], int):
                            new_d[key].append(b[key])
                    else:
                        print(f"Merging this type not supported (KEY: {key}): ({type(b[key])}, {type(new_d[key])})")
                elif isinstance(new_d[key], dict):
                    if isinstance(b[key], dict):
                        new_d[key] = self._merge(new_d[key], b[key])
                else:
                    if new_d[key] != b[key] and b[key] is not None:
                        if key in ["description", ]:
                            if len(new_d[key]) < len(b[key]):
                                new_d[key] = b[key]
                        elif key in ["episodes_count", ]:
                            if int(new_d[key]) < int(b[key]):
                                new_d[key] = b[key]
                        elif new_d[key] is None:
                            new_d[key] = b[key]
                        elif key in [
                            "title", "image",
                        ]:
                            pass
                        elif key in ["premiered", "anilist_id", "mal_id", "age_rating", "aired", "sub", "dub"]:
                            if a['title'] != b['title']:
                                return a
                        else:
                            print(
                                f"Merging this type not supported ({key}): ({type(b[key])}, {type(new_d[key])}): {b[key]}, {new_d[key]} : {b}, {new_d}")
            else:
                new_d[key] = b[key]
        return self.de_duplicate_lists(new_d)

    def de_duplicate_lists(self, a):
        def deduplicate_list(lst):
            seen = []
            for item in lst:
                if isinstance(item, list):
                    item = deduplicate_list(item)
                if item not in seen:
                    seen.append(item)
            return seen

        for key in list(a.keys()):
            if isinstance(a[key], list):
                a[key] = deduplicate_list(a[key])
            elif isinstance(a[key], dict):
                a[key] = self.de_duplicate_lists(a[key])
        return a

    @staticmethod
    def _merge_search(dt):
        res = []
        sections = list(dt.keys())
        for section in sections:
            res.extend(dt[section])
        return res

    async def home(self, dt: dict[str, list[dict]]):
        res = self._merge_search(dt)
        d_resp = []
        for anime in res:
            if isinstance(anime["url"], str):
                d_resp.append(await self.get_details({"slug": anime["url"], "title": anime["title"]}))
        return {"details": [i for i in d_resp if i]}

    async def get_details(self, dt):
        title = dt["title"]
        url = dt.get("slug", None)
        cached_storm_details = await self.database.title(title)
        if cached_storm_details:
            cached_storm_details = cached_storm_details[0]
            if time.time() - cached_storm_details["storm_last_updated"] < 604800:
                del cached_storm_details["_id"], cached_storm_details["storm_last_updated"]
                return cached_storm_details
        if url is None:
            return {"error": "No details found"}
        dts = await caller("details", {"slug": url}, self.streamable_cache)
        if "error" in dts:
            return dts
        search_details = []
        contains_title = []
        dts = self.de_duplicate_lists(dts)
        for title in dts["titles"]:
            search_results = self._merge_search(await caller("search", {"query": title}, self.streamable_cache))
            for result in search_results:
                x = await caller("details", {"slug": result["url"]}, self.streamable_cache)
                if "error" not in x:
                    x = self.de_duplicate_lists(x)
                    try:
                        x["titles"] = [i for i in x["titles"] if i]
                    except TypeError:
                        x["titles"] = [x["title"], ]
                    search_details.append(x)
        for title in dts["titles"]:
            for dtl in search_details:
                if "titles" not in dtl:
                    print("Erroring: ", dtl)
                if title in dtl["titles"]:
                    if dtl not in contains_title:
                        contains_title.append(dtl)
        final_details = dts
        while contains_title:
            final_details = self._merge(final_details, contains_title.pop())
        final_details["extended_titles"] = final_details["extended_titles"] = [season[1] for season in
                                                                               final_details.get("seasons", []) if
                                                                               isinstance(season, list) and len(
                                                                                   season) > 1]
        final_details["extended_titles"] = list(set(final_details["extended_titles"]))
        final_details["storm_last_updated"] = time.time()
        await self.database.update_title(final_details["title"], final_details)

    async def search(self, dt):
        return await self.home(dt)

    async def get_episodes(self, dt):
        anis = self.database.collection.find({})
        sel = {}
        async for elem in anis:
            for season in elem["seasons"]:
                if season[0].strip("/") == dt.get("season_id").strip("/"):
                    sel = elem
        sns = []
        if "seasons" not in sel:
            print(sel)
            return []
        for season in sel["seasons"]:
            if season[1] in sel["titles"]:
                sns.append(season)
            else:
                print(season, sel)
        if not sns:
            sns = [[dt.get("season_id").strip("/")]]
        episodes = {}
        for season in sns:
            episode_x = await caller("episodes", {"season_id": season[0]}, self.streamable_cache)
            if "error" in episode_x:
                continue
            episode_x = episode_x["Episodes"]
            for episode in episode_x:
                for key in episodes.keys():
                    if key.startswith(episode[1] + " ") or key == episode[1]:
                        episodes[key]["id"].append(episode[0])
                        if len(episode) == 3:
                            episodes[key]["title"].extend(episode[2])
                        break
                else:
                    episodes[episode[1]] = {"id": [episode[0]], "title": [], "name": episode[1]}
                    if len(episode) == 3:
                        episodes[episode[1]]["title"].extend(episode[2])
        return list(episodes.values())

    def __del__(self):
        self.database.shutdown()


def add_mapper(app: FastAPI, streamable_cache: Cacher):
    mapper = Mapper(streamable_cache)

    @app.get("/mapper/anime/{method}")
    async def stream_mapped(
            method: str,
            query: str = None,
            slug: str = None,
            episode_id: str = None,
            season_id: str = None,
            dub: str = None,
            title: str = None,
    ):
        if method.startswith("_"):
            return {"error": "Forbidden"}
        queryXs = {
            "query": query,
            "slug": slug,
            "episode_id": episode_id,
            "season_id": season_id,
            "dub": None if dub is None else dub.lower() == "true",
            "title": None if title is None else title
        }
        # Remove None values
        queryXs = {k: v for k, v in queryXs.items() if v is not None}
        res = {}
        if hasattr(mapper, method):
            dt = await caller(method, queryXs, streamable_cache, True)
            if not dt.get("error", False):
                res.update(await getattr(mapper, method)(dt))
        if not res:
            return {"error": "No results"}
        return res
    return mapper


class MapperUtils:
    def __init__(self):
        self.running = True

    @staticmethod
    def run_routine(routine, streamable_cache):
        import asyncio
        try:
            asyncio.run(Mapper(streamable_cache).home(routine))
        except RuntimeError:
            pass

    def run_mapper(self, streamable_cache, method, queryXs):
        import asyncio
        asyncio.run(self.perform_map_bg(streamable_cache, method, queryXs))

    @staticmethod
    async def perform_map_bg(streamable_cache, method, queryXs):
        mapper = Mapper(streamable_cache)
        if hasattr(mapper, method):
            dt = await caller(method, queryXs, streamable_cache, True)
            if not dt.get("error", False):
                await getattr(mapper, method)(dt)
        return True

    def create_map(self, streamable_cache: Cacher):
        from streamable.zoro import ZoroSite
        z = ZoroSite()
        for i in range(121, 184):
            if not self.running:
                break
            self.run_routine(z.recent(i), streamable_cache)

    def create_map_multithread(self, streamable_cache: Cacher, recent_cache: Cacher, thread_count=10):
        import threading
        from streamable.zoro import ZoroSite
        z = ZoroSite()
        ts = []
        for i in range(1, 184):
            while len(ts) > thread_count:
                for j in range(thread_count):
                    if not ts[j].is_alive():
                        del ts[j]
                        break
                if not self.running:
                    break
                time.sleep(1)
            recent = recent_cache.get("recent", {"page": i}, {})
            if not recent:
                recent = z.recent(i)
                recent_cache.set("recent", {"page": i}, {}, recent, 43200)
            if not self.running:
                break
            t = threading.Thread(target=self.run_routine, args=(recent, streamable_cache))
            t.start()
            ts.append(t)
        while ts:
            if not self.running:
                break
            if not ts[0].is_alive():
                del ts[0]
                time.sleep(1)
