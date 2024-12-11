import os
from dotenv import load_dotenv

load_dotenv()

mongo_url = os.getenv("MONGO_URL", "")
is_local = os.getenv("IS_LOCAL", "false") == "true"
cors_proxy_url = os.getenv("CORS_PROXY_URL", "")
enable_cors_proxy = os.getenv('ENABLE_CORS_PROXY', "") == "true"


class GogoURLS:
    gogo_url = "https://anitaku.bz"
    alternate_domains = ["https://gogoanime3.cc/", "https://www9.gogoanimes.fi", ]
    ajax_url = "https://ajax.gogocdn.net"
    recent_url = "%s/ajax/page-recent-release.html?page={}&type={}" % ajax_url
    episodes_url = "%s/ajax/load-list-episode?ep_start=0&ep_end=10000&id={}" % ajax_url
    popular_url = "%s/ajax/page-recent-release-ongoing.html?page={}" % ajax_url
    trending_url = "%s/anclytic-ajax.html?id={}" % ajax_url
    movie_page_url = f"{gogo_url}/anime-movies.html"
    tv_page_url = f"{gogo_url}/new-season.html"
    trending_id = {"week": 1, "month": 2, "all": 3}
    recent_possibilities = {"type": {"1": "Latest Subbed", "2": "Latest Dubbed", "3": "Latest Chinese"}}


class ZoroURLS:
    zoro_url = "https://hianime.to"


class PrimeWire:
    prime_url = "https://www.primewire.tf/"


class MyAnimeList:
    mal_url = "https://myanimelist.net/"
    sitemap_url = "https://myanimelist.net/about/sitemap"
    search_url = "https://myanimelist.net/anime.php?q=%s&cat=%s"
    anime_search = "https://myanimelist.net/anime.php?q=%s&cat=anime"


class AnimeKhor:
    khor_url = "https://animekhor.org/"
    search_url = f"{khor_url}?s="
    search_url_page = f"{khor_url}page/%s/?s="


class AnimeEz:
    anime_ez_url = "https://animez.org/"


class Config:
    mongo_url = mongo_url
    is_local = is_local
    enable_cors_proxy = enable_cors_proxy
    cors_proxy_url = cors_proxy_url

    class StreamURLS:
        class GogoURLS(GogoURLS):
            pass

        class ZoroURLS(ZoroURLS):
            pass

        class PrimeWire(PrimeWire):
            pass

        class MyAnimeList(MyAnimeList):
            pass

        class AnimeKhor(AnimeKhor):
            pass

        class AnimeEz(AnimeEz):
            pass
