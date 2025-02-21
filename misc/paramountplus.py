import json
import re
from urllib.parse import urljoin

import click
import m3u8
import requests

from vinetrimmer.objects import Title, Tracks
from vinetrimmer.objects.tracks import AudioTrack, MenuTrack, TextTrack, VideoTrack
from vinetrimmer.services.BaseService import BaseService


class ParamountPlus(BaseService):
    """
    Service code for Paramount's Paramount+ streaming service (https://paramountplus.com).

    \b
    Authorization: Cookies
    Security: UHD@L3, doesn't care about releases.
    """

    ALIASES = ["PMTP", "paramountplus", "paramount+"]
    TITLE_RE = [
        r"^https?://(?:www\.)?paramountplus\.com/(?P<type>movies)/[a-z0-9_-]+/(?P<id>\w+)",
        r"^https?://(?:www\.)?paramountplus\.com/(?P<type>shows)/(?P<id>[a-zA-Z0-9_-]+)(/)?",
        r"^(?P<id>\d+)$",
    ]
    VIDEO_CODEC_MAP = {"H264": ["avc", "avc1"], "H265": ["hvc", "dvh", "hvc1", "hev1", "dvh1", "dvhe"]}
    AUDIO_CODEC_MAP = {"AAC": "mp4a", "AC3": "ac-3", "EC3": "ec-3"}

    @staticmethod
    @click.command(name="ParamountPlus", short_help="https://paramountplus.com")
    @click.argument("title", type=str, required=False)
    @click.option("-m", "--movie", is_flag=True, default=False, help="Title is a Movie.")
    @click.option(
        "-c", "--clips", is_flag=True, default=False, help="Download clips instead of episodes (for TV shows)"
    )
    @click.pass_context
    def cli(ctx: click.Context, **kwargs):
        return ParamountPlus(ctx, **kwargs)

    def __init__(self, ctx: click.Context, title: str, movie: bool, clips: bool):
        super().__init__(ctx)
        m = self.parse_title(ctx, title)
        self.movie = movie or m.get("type") == "movies"
        self.clips = clips

        self.vcodec = ctx.parent.params["vcodec"]
        self.acodec = ctx.parent.params["acodec"]
        self.range = ctx.parent.params["range_"]
        self.wanted = ctx.parent.params["wanted"]
        self.shorts = False

        ctx.parent.params["acodec"] = "EC3"

        if self.range != "SDR":
            # vcodec must be H265 for High Dynamic Range
            self.vcodec = "H265"

        self.configure()

    def get_titles(self):
        if self.movie:
            res = self.session.get(
                url=self.config[self.region]["movie"].format(title_id=self.title),
                params={
                    "includeTrailerInfo": "true",
                    "includeContentInfo": "true",
                    "locale": "en-us",
                    "at": self.config[self.region]["at_token"],
                },
            ).json()
            if not res["success"]:
                if res["message"] == "No movie found for contentId.":
                    raise self.log.exit(" - Unable to find movie. For TV shows, use the numeric ID.")
                else:
                    raise self.log.exit(f" - Failed to get title information: {res['message']}")

            title = res["movie"]["movieContent"]

            return Title(
                id_=title["contentId"],
                type_=Title.Types.MOVIE,
                name=title["title"],
                year=title["_airDateISO"][:4],  # todo: find a way to get year, this api doesnt return it
                original_lang="en",  # TODO: Don't assume
                source=self.ALIASES[0],
                service_data=title,
            )
        else:
            res = self.session.get(
                url=f"https://www.paramountplus.com/shows/{self.title}/xhr/episodes/page/0/size/99/xs/0/season/"
            ).json()
            show_id = next((x["content_id"] for x in res["result"]["data"]), None)
            if not show_id:
                raise self.log.exit("Content ID could not be found")

            res = self.session.get(
                url=self.config[self.region]["cbs"].format(show_id=show_id),
                params={"includeAllShowGroups": "true", "at": self.config[self.region]["at_token"]},
            ).json()
            cbs_id = next((x["cbsShowId"] for x in res["itemList"]), None)
            if not cbs_id:
                raise self.log.exit("CBS ID could not be found")

            # show_config
            sections = self.session.get(
                self.config[self.region]["shows"].format(title_id=cbs_id),
                params={
                    "platformType": "apps",
                    "begin": 0,
                    "rows": 1,
                    "locale": "en-us",
                    "at": self.config[self.region]["at_token"],
                },
            ).json()
            if not sections["success"]:
                raise self.log.exit(
                    f"Failed to load title metadata: {sections['message'] if sections['message'] else ''}"
                )

            title_section = next(
                (x["sectionId"] for x in sections["videoSectionMetadata"] if x["section_type"] == "Full Episodes"), None
            )

            seasons = sorted(
                self.session.get(
                    url=self.config[self.region]["seasons"].format(cbs_id),
                    params={"at": self.config[self.region]["at_token"]},
                ).json()["video_available_season"]["itemList"],
                key=lambda x: int(x["seasonNum"]),
            )

            episode_count = 0
            for season in seasons:
                episode_count += season["totalCount"]

            if not seasons:
                episode_count = len(sections["results"][0]["sectionItems"]["itemList"])
                seasons = [{"seasonNum": 1, "totalCount": episode_count}]

            episodes_ = []
            for season in seasons:
                if isinstance(season, list):
                    episodes_ += [sections["results"][0]["sectionItems"]["itemList"]]
                    continue

                season_info = self.session.get(
                    url=self.config[self.region]["section"].format(title_section),
                    params={
                        "rows": "999",
                        "params": "seasonNum={}".format(season["seasonNum"]),
                        "begin": "0",
                        "seasonNum": season["seasonNum"],
                        "locale": "en-us",
                        "at": self.config[self.region]["at_token"],
                    },
                ).json()
                if not season_info["success"]:
                    raise self.log.exit(
                        f"Failed to load title metadata: {season_info['message'] if season_info['message'] else ''}"
                    )

                episodes_.extend(season_info["sectionItems"]["itemList"])
            if not episodes_:
                raise self.log.exit("No episodes returned.")

            titles = []
            for episode in episodes_:
                titles.append(
                    Title(
                        id_=episode.get("contentId") or episode.get("content_id"),
                        type_=Title.Types.TV,
                        name=episode.get("seriesTitle") or episode.get("series_title"),
                        season=episode.get("seasonNum") or episode.get("season_number") or 0,
                        episode=episode["episodeNum"] if episode["fullEpisode"] else episode["positionNum"],
                        episode_name=episode["label"],
                        original_lang="en",  # TODO: Don't assume
                        source=self.ALIASES[0],
                        service_data=episode,
                    )
                )

            return titles

    def get_tracks(self, title: Title):
        assets = (
            ["DASH_CENC_HDR10"],
            [
                "HLS_AES",
                "DASH_LIVE",
                "DASH_CENC_HDR10",
                "DASH_TA",
                "DASH_CENC",
                "DASH_CENC_PRECON",
                "DASH_CENC_PS4",
            ],
        )
        for asset in assets:
            r = requests.Request(
                "GET",
                url=self.config["LINK_PLATFORM_URL"].format(video_id=title.id),
                params={
                    "format": "redirect",
                    "formats": "MPEG-DASH",
                    "assetTypes": "|".join(asset),
                    "manifest": "M3U",
                    "Tracking": "true",
                    "mbr": "true",
                },
            )
            req = self.session.send(self.session.prepare_request(r), allow_redirects=False)
            if req.ok:
                break
        else:
            raise ValueError(f"Manifest Error: {req.text}")

        mpd_url = req.headers.get('location')

        try:
            tracks: Tracks = Tracks.from_mpd(
                url=mpd_url.replace("cenc_precon_dash", "cenc_dash"),
                source=self.ALIASES[0],
                session=self.session,
            )
        except:
            tracks: Tracks = Tracks.from_mpd(
                url=mpd_url,
                source=self.ALIASES[0],
                session=self.session,
            )
        tracks.subtitles.clear()

        req = self.session.get(
            url=self.config["LINK_PLATFORM_URL"].format(video_id=title.id),
            params={
                "format": "redirect",
                "formats": "M3U",
                "assetTypes": "|".join(["HLS_FPS_PRECON"]),
                "manifest": "M3U",
                "Tracking": "true",
                "mbr": "true",
            },
        )
        hls_url = req.url

        tracks_m3u8 = Tracks.from_m3u8(
            m3u8.load(hls_url),
            source=self.ALIASES[0],
        )
        tracks.subtitles = tracks_m3u8.subtitles

        for track in tracks:
            # track.id = track.id
            if isinstance(track, VideoTrack):
                track.hdr10 = (
                    track.codec[:4] in ("hvc1", "hev1") and track.extra[0].attrib.get("codecs")[5] == "2"
                ) or (track.codec[:4] in ("hvc1", "hev1") and "HDR10plus" in track.url)

                track.dv = track.codec[:4] in ("dvh1", "dvhe")

            if isinstance(track, VideoTrack) or isinstance(track, AudioTrack):
                if self.shorts:
                    track.encrypted = False

            if isinstance(track, TextTrack):
                track.codec = "vtt"
                #if track.language.language == "en":
                #    track.sdh = True  # TODO: don't assume SDH

        if self.vcodec:
             tracks.videos = [x for x in tracks.videos if (x.codec or "")[:4] in self.VIDEO_CODEC_MAP[self.vcodec]]

        if self.acodec:
            tracks.audios = [x for x in tracks.audios if (x.codec or "")[:4] == self.AUDIO_CODEC_MAP[self.acodec]]

        return tracks

    def get_chapters(self, title: Title):
        chapters = []
        events = title.service_data.get("playbackEvents")
        events = {k: v for k, v in events.items() if v is not None}
        events = dict(sorted(events.items(), key=lambda item: item[1]))
        if not events:
            return chapters

        chapters_titles = {
            "endCreditChapterTimeMs": "Credits",
            "previewStartTimeMs": "Preview Start",
            "previewEndTimeMs": "Preview End",
            "openCreditEndTimeMs": "openCreditEnd",
            "openCreditStartTime": "openCreditStart",
        }

        for name, time_ in events.items():
            if isinstance(time_, (int, float)):
                chapters.append(
                    MenuTrack(
                        number=len(chapters) + 1,
                        title=chapters_titles.get(name),
                        timecode=MenuTrack.format_duration(time_ / 1000),
                    )
                )

        # chapters = sorted(chapters, key=self.converter_timecode)

        return chapters

    def certificate(self, **_):
        return None  # will use common privacy cert

    def license(self, challenge, title, **_):
        bearer_path = title.service_data.get("url") or title.service_data.get("href")
        if not bearer_path:
            raise ValueError("Error")

        r = self.session.post(
            url=self.config["license"],
            params={
                "CrmId": "cbsi",
                "AccountId": "cbsi",
                "SubContentType": "Default",
                "ContentId": title.service_data.get("contentId") or title.service_data.get("content_id"),
            },
            headers={"Authorization": f"Bearer {self.get_auth_bearer(bearer_path)}"},
            data=challenge,  # expects bytes
        )

        if r.headers["Content-Type"].startswith("application/json"):
            res = r.json()
            raise ValueError(res["message"])

        return r.content

    def configure(self):
        self.region = self.session.get("https://ipinfo.io/json").json()["country"]
        if self.region != "US":
            self.region = "INTL"

        self.session.headers.update(
            {
                "Accept-Language": "en-US,en;q=0.5",
                "Origin": "https://www.paramountplus.com",
            }
        )

        self.session.params = {
            "begin": "0",
            "rows": "9999",
            "locale": "en-us",
            "platformType": "apps",
            "at": self.config[self.region]["at_token"],
        }

        if not self.is_logged_in():
            raise ValueError("InvalidCookies")

        if not self.is_subscribed():
            raise ValueError("NotEntitled")

    # Service specific functions

    def get_prop(self, prop):
        res = self.session.get("https://www.paramountplus.com")
        prop_re = prop.replace(".", r"\.")
        search = re.search(rf"{prop_re} ?= ?[\"']?([^\"';]+)", res.text)
        if not search:
            raise ValueError("InvalidCookies")

        return search.group(1)

    def is_logged_in(self):
        return self.get_prop("CBS.UserAuthStatus") == "true"

    def is_subscribed(self):
        return self.get_prop("CBS.Registry.user.sub_status") == "SUBSCRIBER"

    def get_auth_bearer(self, path) -> str:
        r = self.session.get(urljoin("https://www.paramountplus.com", path))
        match = re.search(r'"Authorization": ?"Bearer ([^\"]+)', r.text)
        if not match:
            if not path.endswith("/*"):
                # Hack to get video player page when the API returns a wrong path
                return self.get_auth_bearer(re.sub(r"/[^/]+$", "/*", path))
            else:
                raise ValueError("Error")

        return match.group(1)

    def parse_movie_year(self, url):
        html_raw = self.session.get(url)

        if html_raw.status_code != 200:
            return None

        self.year = int(
            re.findall('"movie__air-year">[0-9]+<', html_raw.text)[0].replace('"movie__air-year">', "").replace("<", "")
        )

    def parse_show_id(self, url):
        html_raw = self.session.get(url)

        if html_raw.status_code != 200:
            self.log.exit("Could not parse Show Id.")

        show = json.loads('{"' + re.search('CBS.Registry.Show = {"(.*)"}', html_raw.text).group(1) + '"}')

        return str(show["id"])
