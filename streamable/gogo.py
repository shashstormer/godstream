from requestez import Session
from requestez.parsers import html, reg_replace
from config import Config
from extractors.gogo import Gogo
# main_url = Config.StreamURLS.GogoURLS.gogo_url
main_url = Config.StreamURLS.GogoURLS.alternate_domains[0]
recent_possibilities = Config.StreamURLS.GogoURLS.recent_possibilities
recent_url = Config.StreamURLS.GogoURLS.recent_url
alternate_domains = Config.StreamURLS.GogoURLS.alternate_domains
episodes_url = Config.StreamURLS.GogoURLS.episodes_url
trending_url = Config.StreamURLS.GogoURLS.trending_url
trending_id = Config.StreamURLS.GogoURLS.trending_id
popular_url = Config.StreamURLS.GogoURLS.popular_url
tv_page_url = Config.StreamURLS.GogoURLS.tv_page_url
movie_page_url = Config.StreamURLS.GogoURLS.movie_page_url


class GogoSite:
    def __init__(self):
        self.session = Session()

    def home(self, redirected_code=None):
        dt = {}
        if redirected_code is None:
            r_typ = recent_possibilities["type"]
            for typ in r_typ:
                try:
                    merge_data = self._cards(self.session.get(recent_url.format("1", typ)))
                    if merge_data == [[], []]:
                        raise ValueError("No Value")
                except Exception as e:
                    print(e)
                    return self.home(redirected_code="1")
                merged = []
                merged.extend(merge_data[0])
                merged.extend(merge_data[1])
                dt[r_typ[typ]] = merged
        elif redirected_code is not None:
            try:
                merge_data = self._cards(self.session.get(f"{main_url}/home.html"))
            except Exception as e:
                print(e)
                try:
                    merge_data = self._cards(self.session.get(alternate_domains[0]))
                except Exception as e2:
                    print(e2)
                    return {"alert": "selected source is down"}
            merged = []
            merged.extend(merge_data[0])
            merged.extend(merge_data[1])
            dt["Recent Subbed"] = merged
        return dt

    @staticmethod
    def _cards(page_content):
        page_content = html(page_content)
        items = page_content.select_one("ul[class='items']")
        data = [[], []]
        if items is None:
            return data
        for item in items.select("li"):
            image = item.select_one("img")["src"]
            a = item.select_one("a")
            title = a["title"]
            link = a["href"].split("-episode-")[0]
            link = "/category" + link if not link.startswith("/category/") else link
            typ = "DUB" if link.endswith("-dub") else "SUB"
            to_append = {
                "image": image,
                "url": link,
                "title": title,
                "type": typ,
                "rating": "?"
            }
            released_year = item.select_one("p[class='released']")
            if released_year:
                to_append["released_year"] = (
                    released_year.get_text().replace("Released:", "").replace("\n", "").replace("\t", "")
                    .strip(" "))
            data[0 if typ == "SUB" else 1].append(to_append)
        return data

    def search(self, query: str, page: int = 1):
        method_value = query
        if method_value.startswith("/"):
            method_value = method_value[1:]
        url = f"{main_url}/search.html?keyword={method_value.replace(' ', '%20')}&page={page}"
        try:
            dt = self.session.get(url)
        except Exception as e:
            print(e)
            dt = self.session.get(url.replace(main_url, alternate_domains[0]))
        results = self._cards(dt)
        dt = {}
        if results[0]:
            dt["Search Results Subbed"] = results[0]
        if results[1]:
            dt["Search Results Dubbed"] = results[1]
        return dt

    def details(self, slug, d=0):
        if (not slug.startswith("category/")) and (not slug.startswith("/category/")):
            return {"error": "Unable to fetch details"}
        if d > 3:
            return {"error": "Unable to fetch details"}
        slug = slug.replace("/category/category/", "/category/", 1)
        ori_val = slug
        if ori_val.startswith("/"):
            ori_val = ori_val[1:]
        method_value = "/" + slug if not slug.startswith("/") else slug
        if method_value.startswith("https://"):
            method_value = reg_replace("(https://[^/]+)", "", method_value)
        try:
            pg = self.session.get(main_url + (method_value[:-1] if method_value.endswith('/') else method_value))
        except Exception as e:
            print(e)
            pg = self.session.get(
                main_url + (method_value[:-1] if method_value.endswith('/') else method_value).replace(main_url,
                                                                                                       alternate_domains[
                                                                                                           0]))
        try:
            pg = html(pg)
            # srs = method_value.replace("/category", "")
            season_id = pg.select_one("input[id='movie_id']")["value"]
            container_main = pg.select_one('div[class="anime_info_body_bg"]')
            ret = {}
            title = reg_replace("\n|&nbsp;", "", container_main.select_one("h1").get_text())
            ret["title"] = title
            ret["image"] = container_main.select_one("img")["src"]
            details = container_main.select("p[class='type']")
            for det in details:
                tit = det.select_one("span").get_text().replace(":", "").strip(" ").lower().split(" ")[0]
                if tit == "type":
                    x = det.select_one("a")
                    x = x["title"] if x else ""
                    ret["released"] = x
                if tit == "plot":
                    ret["description"] = det.get_text().replace(":", "", 1).replace("Plot Summary", "").replace(
                        "\n", "").strip(" ")
                if tit == "genre":
                    ret["genre"] = [[i["href"], i["title"]] for i in det.select("a")]
                if tit == "released":
                    ret["year"] = det.get_text().replace("Released", "").replace(":", "").replace("\n",
                                                                                                  "").strip(
                        " ")
                if tit == "status":
                    x = det.select_one("a")
                    x = x.get_text() if x else ""
                    ret["time_seasons"] = x
                if tit == "other":
                    ret["titles"] = [i.strip(" ") for i in
                                               det.get_text().replace("Other name", "").replace(":",
                                                                                                "").replace(
                                                   "\n",
                                                   "").strip(
                                                   " ").split(";")][::-1]
            if len(ret.get("titles", [])) == 0:
                ret["titles"] = [ret["title"]]
            ret["episodes_count"] = pg.select("ul[id='episode_page']")[0].select("a[class*='active']")[0][
                'ep_end']
            ret["seasons"] = [[season_id, ret['title'], ret['image']]]
        except Exception as e:
            try:
                print("E4DCQ: ", e)
                search_term = ori_val.replace("category/", "", 1).replace("-dub", "", 1).replace("-", " ").replace(
                    "api/gogo/details/category/", "")
                results = self.search(search_term)
                results_check = f"Search Results {'S' if '-dub' not in ori_val else 'D'}ubbed"
                for result in results[results_check]:
                    if result["url"].startswith(f"/{ori_val}") or result["url"].replace("-tv-", "").startswith(
                            f"/{ori_val}"):
                        return self.details(result["url"], d=d+1)
                else:
                    return {"Status": "Error Please Search for this title and watch"}
            except (KeyError,):
                return {"error": "Unable to fetch details"}
        return ret

    def episodes(self, season_id: str, redirected_code=None):
        srs_id = season_id.split("/")[-1]
        try:
            int(srs_id)
        except (TypeError, ValueError):
            return {"error": "Unable to fetch episodes"}
        url = episodes_url.format(srs_id)
        new = False
        dt = "False"
        try:
            dt, new = (self.session.get(url), True)
        except Exception as e:
            print(e)
            redirected_code = "1"
        if new and redirected_code is None:
            dn = []
            dt = html(dt)
            a_s = dt.select("a")
            for a in a_s:
                try:
                    nm = a.select_one("div[class='name']").get_text().replace("EP", "Episode")
                except AttributeError:
                    return {"error": "Unable to fetch episodes"}
                href = a["href"].replace("/", "", 1)
                dn.append([href.strip(" "), nm])
            dt = dn
        elif redirected_code is not None:
            dt = [[season_id.split("/")[-2] + "-episode-" + str(i + 1), f"Episode {i + 1}"] for i in range(
                int(self.details(season_id.replace("/episodes/", "/details/category/").replace(srs_id, ""))[
                        "episodes_count"]))]
        if not dt:
            return {"error": "Unable to fetch episodes"}
        return {"Episodes": dt}

    def trending(self, timeline="week"):
        url = trending_url.format(trending_id.get(timeline, 1))
        dt = self.session.get(url)
        dt = html(dt)
        dt = [{"title": i["title"], "url": i["href"],
               "released_ep_count": i.select_one("p[class*='reaslead']").get_text().replace("Episode",
                                                                                            "").replace(
                   ":", "").strip(" ") if i.select_one("p[class*='reaslead']") is not None else ""}
              for i in dt.select("a")]
        return dt

    def popular(self, page=1):
        url = popular_url.format(page)
        dt, new = self.session.get(url), True
        if new:
            dt = html(dt)
            data = []
            for item in dt.select_one('div[class="added_series_body popular"]').select("li"):
                data_item = {}
                a = item.select("a")
                for a in a.copy():
                    if a.select_one("div") is not None:
                        a = a
                        break
                else:
                    continue
                data_item["url"] = a["href"]
                data_item["title"] = a["title"]
                data_item["image"] = a.select_one("div")["style"].split("'")[1]
                data_item["genres"] = []
                for genre in item.select("p[class='genres']")[0].select("a"):
                    data_item["genres"].append(genre["title"].lower())
                data.append(data_item)
            dt = data
        return dt

    def tv(self):
        dt = self.session.get(tv_page_url)
        dt = self._cards(dt)
        dt = {"Newly Added Tv": dt[0]}
        return dt

    def movie(self):
        dt = self.session.get(movie_page_url)
        dt = self._cards(dt)
        dt = {"Newly Added Movies": dt[0]}
        return dt

    @staticmethod
    def source(episode_id):
        if ("-episode-" not in episode_id) or len([char for char in episode_id.split("-")[-1] if char.isalpha()]) > 0:
            return {"error": "Incorrect source"}
        extractor = Gogo()
        # try:
        return extractor.source(episode_id)
        # except Exception as e:
        #     print("Source Extraction Error: ", e)
        # return {"error": "Could not fetch sources"}


if __name__ == "__main__":
    g = GogoSite()
    print(g.home())
    print(g.search("the cockpit"))
    print(g.trending())
    print(g.popular())
    print(g.details("/category/the-cockpit"))
    eps = g.episodes("9282")
    print(eps)
    print(Gogo().source(eps[0][0]))
