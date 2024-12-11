from requestez import Session
from requestez.parsers import html, load, reg_compile
from extractors.megacloud import MegaCloud
from config import Config


class ZoroSite:
    def __init__(self):
        self.session = Session()
        self.main_url = Config.StreamURLS.ZoroURLS.zoro_url

    def home(self):
        try:
            response = self.session.get(f"{self.main_url}/home")
            data = self._cards(response)
            return {"Latest Release": data[:12], "Newly Added": data[12:24], "Top Upcoming": data[24:]}
        except Exception as e:
            print(e)
            return {"error": "Unable to fetch home data"}

    def recent(self, page):
        url = f'{self.main_url}/recently-updated?page={page}'
        response = self.session.get(url)
        results = self._cards(response, skip=4)
        return {"Search Results": results}

    def search(self, query: str, page: int = 1):
        try:
            url = f'{self.main_url}/search?keyword={query.replace(" ", "%20")}&page={page}'
            response = self.session.get(url)
            results = self._cards(response)
            return {"Search Results": results}
        except Exception as e:
            print(e)
            return {"error": "Unable to perform search"}

    def details(self, slug: str):
        slug = slug.lstrip("/").lstrip("watch/").strip("/")
        if "/" in slug:
            return {"error": "Unable to fetch details"}
        # try:
        else:
            url = f"{self.main_url}/{slug}"
            response = self.session.get(url)
            details = self._parse_details(response, slug)
            return details
        # except Exception as e:
        #     print(e)
        #     return {"error": "Unable to fetch details"}

    def episodes(self, season_id: str):
        season_id = season_id.split("-")
        if len(season_id) == 1:
            return {"error": "Unable to fetch episodes"}
        season_id = season_id[-1]
        try:
            int(season_id)
            url = f"{self.main_url}/ajax/v2/episode/list/{season_id}"
            response = self.session.get(url)
            episodes = self._parse_episodes(response)
            return {"Episodes": episodes}
        except Exception as e:
            print(e)
            return {"error": "Unable to fetch episodes"}

    def trending(self):
        try:
            response = self.session.get(f"{self.main_url}/trending")
            data = self._cards(response)
            return {"Trending": data}
        except Exception as e:
            print(e)
            return {"error": "Unable to fetch trending data"}

    def popular(self):
        try:
            response = self.session.get(f"{self.main_url}/popular")
            data = self._cards(response)
            return {"Popular": data}
        except Exception as e:
            print(e)
            return {"error": "Unable to fetch popular data"}

    def _cards(self, page_content, skip=0):
        soup = html(page_content)
        results = []
        result_items = soup.select('.film_list-wrap > div.flw-item')
        if skip > 0:
            result_items = result_items[skip:]
        for item in result_items:
            id_item = item.select_one('div:nth-child(1) > a.film-poster-ahref')['href'].split('/')[1].split('?')[0]
            title = item.select_one('div.film-detail > h3.film-name > a.dynamic-name')['title']
            type_item = item.select_one(
                'div:nth-child(2) > div:nth-child(2) > span:nth-child(1)').get_text().upper()
            image = item.select_one('div:nth-child(1) > img.film-poster-img')['data-src']
            url = self.main_url + item.select_one('div:nth-child(1) > a').get('href')
            ep_sub = item.select_one('.tick-item.tick-sub')
            ep_dub = item.select_one('.tick-item.tick-dub')
            ep_total = item.select_one('.tick-item.tick-eps')
            duration = item.select_one('.fdi-item.fdi-duration')
            ep_sub = ep_sub.get_text() if ep_sub else 0
            ep_dub = ep_dub.get_text() if ep_dub else 0
            ep_total = ep_total.get_text() if ep_total else 0
            duration = duration.get_text() if duration else ''
            results.append({
                'id': id_item,
                'title': title,
                'type': type_item,
                'image': image,
                'url': url.replace(self.main_url, '').split("?", 1)[0].strip("/watch"),
                'subbed': ep_sub,
                'dubbed': ep_dub,
                'total': ep_total,
                'duration': duration,
                'rating': '?'
            })
        return results

    @staticmethod
    def _parse_details(page_content, slug):
        soup = html(page_content)
        # print(page_content)
        details = {}
        title = soup.select_one('[class="film-name dynamic-name"]')
        details['title'] = title.get_text()
        details['age_rating'] = soup.select_one('[class="tick-item tick-pg"]').get_text().strip()
        details['quality'] = soup.select_one('[class="tick-item tick-quality"]').get_text().strip()
        details['sub'] = soup.select_one('[class="tick-item tick-sub"]').get_text().strip()
        dub = soup.select_one('[class="tick-item tick-dub"]')
        if dub:
            dub = dub.get_text().strip()
            try:
                dub = int(dub)
                sub = int(details['sub'])
                details['sub'] = sub
                if dub > sub:
                    details['dub'] = 0
                else:
                    details['dub'] = dub
            except (TypeError, ValueError):
                details['dub'] = 0
        else:
            details["dub"] = 0
        details['episodes'] = soup.select_one('[class="tick-item tick-eps"]').get_text().strip()
        details['type'] = None
        details["image"] = soup.select_one('[class="film-poster-img"]')['src'].strip()
        details["titles"] = []
        details["titles"].append(title["data-jname"])
        details["titles"].append(title.get_text().strip())
        overview_items = soup.select("[class='item item-title']")
        for item in overview_items:
            head = item.select_one('[class="item-head"]').get_text().strip(":").strip().lower()
            name = item.select_one('[class="name"]').get_text().strip()
            details[head] = name
            if head == "japanese":
                details["titles"].append(name)
        details["description"] = soup.select_one('[class="item item-title w-hide"]').select_one(
            "[class='text']").get_text().strip()
        gnrs = soup.select_one('[class="item item-list"]')
        details["genres"] = [i["title"].lower() for i in (gnrs.select("a") if gnrs else [])]
        details["seasons"] = [
            [i["href"], i.get_text().strip(), i.select_one('[class="season-poster"]')["style"][22:-2]] for i in
            soup.select('[class="os-item"]')]
        if not details["seasons"]:
            details["seasons"] = [[slug, details['title'], details['image']]]
        details["anilist_id"] = reg_compile(r'\"anilist_id\"\:\"(\d+)"').findall(page_content)
        if details["anilist_id"]:
            details["anilist_id"] = details["anilist_id"][0]
        else:
            details["anilist_id"] = None
        details["mal_id"] = reg_compile(r'\"mal_id\"\:\"(\d+)"').findall(page_content)
        if details["mal_id"]:
            details["mal_id"] = details["mal_id"][0]
        else:
            details["mal_id"] = None
        return details

    @staticmethod
    def _parse_episodes(page_content):
        soup = html(load(page_content)['html'])
        episodes = []  # [[slug, name]...]
        ep_items = soup.select("a[class*='ep-item']")
        for ep in ep_items:
            names = ep.select_one('[class="ep-name e-dynamic-name"]')
            name1 = "Episode " + ep["data-number"]
            name2 = ep["title"]
            if name1 != name2:
                name = f"{name1} : {name2}"
            else:
                name = name1
            episodes.append(["zoro"+ep["data-id"], name, [names["data-jname"], names['title']]])
        return episodes

    def source(self, episode_id, dub=False):
        if not episode_id.startswith("zoro"):
            return {"error": "Incorrect source"}
        episode_id = episode_id.strip("zoro")
        method_value = episode_id.split("/")[-1]
        sources_url = f"{self.main_url}/ajax/v2/episode/servers?episodeId=" + method_value  # 117058
        sources_data = self.session.get(sources_url)
        data_ids = reg_compile(r"data\-type\=\\\"([^\\+]+)[^d]+data\-id\=\\\"([^\\]+)").findall(sources_data)
        data_id = ""
        for source in data_ids:
            if dub:
                if source[0] == "dub":
                    data_id = source[1]
                    break
            else:
                if source[0] == "sub":
                    data_id = source[1]
                    break
                if source[0] == "raw":
                    data_id = source[1]
                    break
            if source[0] not in ["sub", "dub"]:
                print(source)
        if not data_id:
            return {"error": "SOURCES or DUB Not Found"}
        embed_url = f"{self.main_url}/ajax/v2/episode/sources?id=" + data_id  # 1089826
        embed_data = load(self.session.get(embed_url))
        embed_url = embed_data['link']
        extractor = MegaCloud(self.session)
        video_urls = extractor.extract(embed_url)
        return video_urls


if __name__ == "__main__":
    g = ZoroSite()
    # print(g.home())
    # print(g.search("the cockpit"))
    # print(g.details("/the-missing-8-18146"))
    # print(g.details("/demon-slayer-kimetsu-no-yaiba-hashira-training-arc-19107"))
    eps = g.episodes("19107")
    # eps = g.episodes("18146")
    print(eps)
    print(ZoroSite().source("124260"))
# g = ZoroSite()
# print(g.details("/the-missing-8-18146"))
