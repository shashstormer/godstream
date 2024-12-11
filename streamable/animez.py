from requestez import Session
from requestez.parsers import html
from config import Config


class AnimeEz:
    def __init__(self):
        self.session = Session()
        self.main_url = Config.StreamURLS.AnimeEz.anime_ez_url

    def source(self, episode_id):
        """
        Retrieve the source data for the given method value.
        """
        if episode_id.startswith("zeani"):
            episode_id = episode_id.replace("zeani", "", 1)
        else:
            return {"error": "Incorrect source"}
        source_url = f"{self.main_url}/{episode_id}"
        pg = html(self.session.get(source_url))
        sources = pg.select_one("#anime_player")
        if not sources:
            return {"error": "Unable to fetch sources"}
        m3u8_url = sources.select_one("iframe")['src']
        return {"sources": [{"url": m3u8_url.replace("/embed/", "/anime/"), "type": "m3u8", "isM3U8": True}]}
