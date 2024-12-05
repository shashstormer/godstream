from requestez import Session
from requestez.parsers import html
from config import Config
import base64
from extractors import DailyMotion, FileMoon, OkRu

cards_url_remap = {
    "shrouding-the-heavens": "shrounding-the-heavens"
}


class KhorSite:
    def __init__(self):
        self.session = Session()
        self.main_url = Config.StreamURLS.AnimeKhor.khor_url
        self.extractors = {
            "okru": OkRu(),
            "dailymotion": DailyMotion(),
            "filemoon": FileMoon(),
        }

    def _cards(self, search_page):
        """
        Extracts cards from the search page of an anime website.

        Parameters:
            search_page (BeautifulSoup): The parsed HTML of the search results page.

        Returns:
            list: A list of dictionaries, each representing a card with details.
        """
        cards = []
        search_page = html(search_page)
        try:
            # Locate the cards within the search page
            results = search_page.find_all("article", {"class": "bs"})

            for result in results:
                try:
                    # Extract title
                    title_element = result.find("h2")
                    title = self._clean(title_element.get_text())

                    # Extract anime details page URL
                    page_url_element = result.find("a")
                    page_url = page_url_element['href']
                    khor_id = page_url_element['rel'][0] if 'rel' in page_url_element.attrs else None

                    # Extract status and type
                    statuses = result.find("div", {"class": "limit"}).find_all("div")
                    try:
                        status_element = statuses[3].find("span")
                    except IndexError:
                        status_element = statuses[2].find("span")
                    status = status_element.get_text() if status_element else "Unknown"
                    if status == "Hiatus":
                        status = "Ongoing"

                    type_ = statuses[-1].find_all("span")[-1].get_text() if (
                            (len(statuses) > 1) and (len(statuses[-1].find_all("span")) > 1)) else "Unknown"

                    # Extract cover image
                    img_element = result.find("img")
                    img = img_element['src'] if img_element else "Unknown"
                    url = page_url.replace(self.main_url, "").split("-episodes-")[0].split("-episode-")[0]
                    if not url.strip("/").startswith("anime/"):
                        url = "anime/" + cards_url_remap.get(url, url)
                    # Compile card details
                    card_details = {
                        "title": title,
                        "image": img,
                        "url": url,
                        "category": type_,
                        ("status" if "ep" not in status.lower() else "latest_episode"): status,
                        "khor_id": khor_id,
                    }
                    cards.append(card_details)
                except Exception as e:
                    print(f"Error processing result: {e}")
                    continue
        except Exception as e:
            print(f"Error extracting cards: {e}")

        return cards

    @staticmethod
    def _clean(value):
        value = value.replace("-", " ")
        for i in list("(!%@$^&*/\\'\"}[]\'’{:;.,?<>~`=+-*#)"):
            value = value.replace(i, "")
        value = value.strip(" ")
        return value

    @staticmethod
    def _decode_utf8(encoded_string):
        """
            Decodes a UTF-8 encoded string into readable text.

            Args:
                encoded_string (str): The encoded string.

            Returns:
                str: The decoded string.
            """
        try:
            # Convert the encoded string to bytes and decode
            decoded_string = encoded_string.encode('latin1').decode('utf-8')
            return decoded_string
        except UnicodeDecodeError:
            return encoded_string
        except UnicodeEncodeError:
            print(f"Encode Error: {encoded_string}")
            return encoded_string

    def home(self):
        try:
            response = self.session.get(f"{self.main_url}")
            data = self._cards(response)
            return {"Newest Chinese": data}
        except Exception as e:
            print(e)
            return {"error": "Unable to fetch home data"}

    def search(self, query: str, page: int = 1):
        try:
            url = f'{self.main_url}page/{page}/?s={query.replace(" ", "+")}'
            response = self.session.get(url)
            results = self._cards(response)
            return {"Search Results Khor": results}
        except Exception as e:
            print(e)
            return {"error": "Unable to perform search"}

    def details(self, slug: str):
        if not slug.strip("/").startswith("anime/"):
            return {"error": "Unable to fetch details"}
        url = f'{self.main_url}/{slug}/'
        response = self.session.get(url)
        soup = html(response)
        main_details = soup.select_one('div[class="bixbox animefull"]')
        if main_details is None:
            return {"error": "Unable to fetch details"}
        dets = {}
        img = main_details.select_one('img')['src'] if main_details.select_one('img') else ""
        title = main_details.select_one('h1[class="entry-title"]').get_text().split("[")[
            0].split("(")[0].strip() if main_details.select_one('h1[class="entry-title"]') else ""
        titles = [self._decode_utf8(i.strip()) for i in
                  main_details.select_one('span[class="alter"]').get_text().split(",")] if main_details.select_one(
            'span[class="alter"]') else []
        dets["image"] = img
        dets["title"] = title
        dets["titles"] = titles
        if title not in titles:
            titles.append(title)
        det_items = main_details.select_one('div[class="spe"]').select('span')
        for child in det_items:
            det_name = child.select_one('b')
            if not det_name:
                continue
            det_name = det_name.get_text().replace(":", "").strip("\n").strip(" ").strip(
                "\n").strip(" ")
            det_value = child.get_text().replace(det_name, "").replace(":", "").strip("\n").strip(" ").strip(
                "\n").strip(" ")
            det_name = det_name.lower()
            dets[det_name] = det_value
        gnrs = main_details.select_one('div[class="genxed"]')
        if gnrs:
            genres = []
            for genre in gnrs.select('a'):
                genres.append([genre['href'], genre.get_text()])
            dets['khor_genre'] = genres
        desc = soup.select_one('div[class="entry-content"][itemprop="description"]')
        desc = desc.get_text().strip("\n").strip() if desc else ""
        dets["description"] = desc
        dets["seasons"] = [[slug, title, img]]
        return dets

    def episodes(self, season_id):
        if not season_id.strip("/").startswith("anime/"):
            return {"error": "Unable to fetch details"}
        url = f'{self.main_url}/{season_id}/'
        response = self.session.get(url)
        eps = self._parse_episodes(response)
        ep_l = []
        # ({'EP 1': {'episode url': 'https://animekhor.org/close-combat-mage-jin-zhan-fashi-episode-1-subtitles-english-indonesian/', 'release date': 'November 20, 2023'}, 'EP 2': {'episode url': 'https://animekhor.org/close-combat-mage-jin-zhan-fashi-episode-2-subtitles-english-indonesian/', 'release date': 'November 20, 2023'}, 'EP 3': {'episode url': 'https://animekhor.org/close-combat-mage-jin-zhan-fashi-episode-3-subtitles-english-indonesian/', 'release date': 'November 20, 2023'}, 'EP 4': {'episode url': 'https://animekhor.org/close-combat-mage-jin-zhan-fashi-episode-4-subtitles-english-indonesian/', 'release date': 'November 23, 2023'}, 'EP 5': {'episode url': 'https://animekhor.org/close-combat-mage-jin-zhan-fashi-episode-5-subtitles-english-indonesian/', 'release date': 'November 23, 2023'}, 'EP 6': {'episode url': 'https://animekhor.org/close-combat-mage-jin-zhan-fashi-episode-6-subtitles-english-indonesian/', 'release date': 'November 23, 2023'}, 'EP 7': {'episode url': 'https://animekhor.org/close-combat-mage-jin-zhan-fashi-episode-7-subtitles-english-indonesian/', 'release date': 'November 30, 2023'}, 'EP 8': {'episode url': 'https://animekhor.org/close-combat-mage-jin-zhan-fashi-episode-8-subtitles-english-indonesian/', 'release date': 'December 7, 2023'}, 'EP 9': {'episode url': 'https://animekhor.org/close-combat-mage-jin-zhan-fashi-episode-9-subtitles-english-indonesian/', 'release date': 'December 14, 2023'}, 'EP 10': {'episode url': 'https://animekhor.org/close-combat-mage-jin-zhan-fashi-episode-10-subtitles-english-indonesian/', 'release date': 'December 21, 2023'}, 'EP 11': {'episode url': 'https://animekhor.org/close-combat-mage-jin-zhan-fashi-episode-11-subtitles-english-indonesian/', 'release date': 'January 5, 2024'}, 'EP 12': {'episode url': 'https://animekhor.org/close-combat-mage-jin-zhan-fashi-episode-12-subtitles-english-indonesian/', 'release date': 'January 5, 2024'}, 'EP 13': {'episode url': 'https://animekhor.org/close-combat-mage-jin-zhan-fashi-episode-13-subtitles-english-indonesian/', 'release date': 'January 11, 2024'}, 'EP 14': {'episode url': 'https://animekhor.org/close-combat-mage-jin-zhan-fashi-episode-14-subtitles-english-indonesian/', 'release date': 'January 28, 2024'}, 'EP 15': {'episode url': 'https://animekhor.org/close-combat-mage-jin-zhan-fashi-episode-15-subtitles-english-indonesian/', 'release date': 'January 28, 2024'}, 'EP 16': {'episode url': 'https://animekhor.org/close-combat-mage-jin-zhan-fashi-episode-16-subtitles-english-indonesian/', 'release date': 'February 1, 2024'}, 'EP 17': {'episode url': 'https://animekhor.org/close-combat-mage-jin-zhan-fashi-episode-17-subtitles-english-indonesian/', 'release date': 'February 13, 2024'}, 'EP 18': {'episode url': 'https://animekhor.org/close-combat-mage-jin-zhan-fashi-episode-18-subtitles-english-indonesian/', 'release date': 'February 15, 2024'}, 'EP 19': {'episode url': 'https://animekhor.org/close-combat-mage-jin-zhan-fashi-episode-19-subtitles-english-indonesian/', 'release date': 'February 22, 2024'}, 'EP 20': {'episode url': 'https://animekhor.org/close-combat-mage-jin-zhan-fashi-episode-20-subtitles-english-indonesian/', 'release date': 'February 29, 2024'}}, '1', '20')
        # raise ValueError("Testing")
        kys = list(eps[0].keys())
        for k in kys:
            ep_l.append([eps[0][k]['episode url'].replace(self.main_url, ""), k.replace("EP", "Episode")])
        return {"Episodes": ep_l}

    @staticmethod
    def _parse_episodes(page):
        """
        main key "episode urls"
        """
        page = html(page)
        epi = {}
        i = page.find_all("div", {"class": "lastend"})[0].find_all("div", {"class": "inepcx"})
        start = \
            i[0].find_all("span")[1].get_text().replace("Episode ", "").replace("Episodes ", "").replace(" to ",
                                                                                                         "-").split(
                "-")[0]
        # end = i[1].find_all("span")[1].get_text().replace("Episode ", "").replace("Episodes ", "").replace(" to ", "-").split("-")[-1]
        eps_lis = page.find_all("div", {"class": "eplister"})[0].find_all("ul")[0].find_all("li")
        eps_lis.reverse()
        last_epno = 0
        sc = 0
        prev_season = ""
        epno_prev = 0
        ep_no = "Unknown"
        for i in eps_lis:
            ep_d = i.find_all("a")[0]
            ep_url = ep_d['href']
            ep_d = ep_d.find_all("div")
            ep_no = ep_d[0].get_text().replace(" to ", "-")
            if "S" not in ep_no:
                last_epno = ep_no.split("EP ")[-1].split("-")[-1]
            if "S" in ep_no:
                # season_ = ep_no.split(" ")[0] + " E"
                season_ = ep_no.split("E")[0].strip(" ")
                if prev_season != season_:
                    last_epno = epno_prev
                    prev_season = season_
                new_ = ep_no.replace(season_, "").replace("E", "").strip(" ").split("-")
                add = []
                newer = ""
                for k in new_:
                    k = int(k) + int(last_epno)
                    k = str(k)
                    add.append(k)
                for k in add:
                    newer += "-"
                    newer += k
                ep_no = newer[1:]
                if sc == 0:
                    prev_season = season_
                    last_epno = ep_no.split("EP ")[-1].split("-")[-1]
                    sc += 1
            epno_prev = ep_no.split("-")[-1]
            release_date = ep_d[2].get_text()
            epi["EP " + ep_no] = {"episode url": ep_url, "release date": release_date}
        return epi, start.split("[")[0].strip(" "), ep_no.split("-")[-1].split("[")[0].strip(" ")

    def source(self, episode_id):
        if not episode_id.strip("/"):
            return {"error": "Unable to fetch details"}
        url = f'{self.main_url}/{episode_id}/'
        response = self.session.get(url)
        eps = self._parse_sources(response)
        for source, url in eps.items():
            try:
                m3u8 = self.extractors[source].source(url, "https://animekhor.org")
                print([source, url], m3u8)
                if m3u8:
                    return m3u8
            except Exception as e:
                print([source, url], e)
        # return {"error": "Unable to fetch source"}
        raise ValueError("Testing")

    @staticmethod
    def _decodeX(string):
        return html(base64.b64decode(string).decode("utf-8"))

    def _parse_sources(self, page):
        page = html(page)
        sources = {}
        sourcesX = page.find_all("select", {"class": "mirror"})[0].find_all("option")
        for source in sourcesX:
            if source.get_text() != "Select Video Server":
                text = source.get_text().lower()
                source = self._decodeX(source['value'])
                try:
                    source = str(source.find_all("iframe")[0]['src'])
                except AttributeError:
                    source = ["none"]
                if "ok.ru" in text:
                    if source.startswith("//"):
                        source = "https:" + source
                    sources['okru'] = source
                # elif "VidPlayer" in text:
                #     sources['dailymotion'] = source
                elif "fembed" in text:
                    sources['fembed'] = source
                elif "StreamLare" in text:
                    sources['streamLare'] = source
                elif "streamsb" in text:
                    sources['streamsb'] = source
                elif "doodstream" in text:
                    sources['dodostream'] = source
                elif "daily" in source:
                    sources['dailymotion'] = source
                elif "rumble" in source:
                    sources['rumble'] = source
                elif "filemoon" in source:
                    sources['filemoon'] = source
                elif "silk" in source:
                    sources['silk'] = source
                elif "abyss" in text:
                    sources['abyss'] = source
                else:
                    print(text, source)
        return sources
