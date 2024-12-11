from fastapi import FastAPI
from streamable.animez import AnimeEz
from streamable.gogo import GogoSite
from streamable.zoro import ZoroSite
from streamable.khor import KhorSite
from database.cacher import Cacher

# List of streaming site objects
sites = [
    AnimeEz(),
    ZoroSite(),
    GogoSite(),
    KhorSite(),
]


def cache_conditions(site, method, queryXs):
    if isinstance(site, AnimeEz):
        return False
    if method in []:
        return False
    else:
        pass
    return True


async def caller(method, queryXs, cache_store, internal=False):
    res = {}
    nf = 0
    for site in sites:
        # Check if the site has the requested method
        if hasattr(site, method):
            caches_res = False
            if cache_conditions(site, method, queryXs):
                caches_res = cache_store.get("GET", queryXs, {"site": str(type(site)), "method": method})
            if caches_res:
                site_result = caches_res
            else:
                # try:
                # Dynamically call the method
                site_result = getattr(site, method)(**queryXs)
            # print(f"Response from {site}: {site_result}")
            # Exclude results with specific errors
            if site_result.get("error") not in [
                "Unable to fetch details",
                "Unable to fetch episodes",
                "Incorrect source",
                "Unable to perform search"
            ]:
                res.update(site_result)
            else:
                if site_result.get("error") not in ["Unable to fetch details", ]:
                    # print(f"Response from {site}: {site_result}")
                    pass
            # cache_store.set("GET", queryXs, {"site": str(type(site))}, site_result, 29030400)
            if cache_conditions(site, method, queryXs):
                cache_store.set("GET", queryXs, {"site": str(type(site)), "method": method}, site_result, 604800)
        else:
            nf += 1
        # except Exception as e:
        #     print(f"Error calling {method} on {site}: {e}")
        # res.update({"error": "An internal error occurred"})
    if nf > 1:
        if internal:
            if not res:
                return queryXs
    # print("Final Result: ", res)
    if not res:
        return {"error": "No results", "nf": nf}
    return res


def add_streamable(app: FastAPI, cache_store: Cacher):
    @app.get("/stream/{method}")
    async def stream(
            method: str,
            query: str = None,
            slug: str = None,
            episode_id: str = None,
            season_id: str = None,
            dub: str = None,
            page: int = None,
    ):
        # Disallow methods starting with '_'
        if method.startswith("_"):
            return {"error": "Forbidden"}
        # Construct query parameters dictionary
        queryXs = {
            "query": query,
            "slug": slug,
            "episode_id": episode_id,
            "season_id": season_id,
            "dub": None if dub is None else dub.lower() == "true",
            "page": page,
        }
        # Remove None values
        queryXs = {k: v for k, v in queryXs.items() if v is not None}
        resp = await caller(method, queryXs, cache_store)
        return resp
