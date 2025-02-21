import base64
import hashlib
import hmac
import json
import os
import time
import uuid
import click
import m3u8
from urllib.request import urlopen, Request

from vinetrimmer.config import directories
from vinetrimmer.objects import Title, Tracks
from vinetrimmer.services.BaseService import BaseService


class Hotstar(BaseService):
    """
    Service code for Star India's Hotstar (aka Disney+ Hotstar) streaming service (https://hotstar.com).

    \b
    Authorization: Credentials
    Security: UHD@L3, doesn't seem to care about releases.

    \b
    Tips: - The library of contents can be viewed without logging in at https://hotstar.com
          - The homepage hosts domestic programming; Disney+ content is at https://hotstar.com/id/disneyplus
    """

    ALIASES = ["HS", "Hotstar"]
    TITLE_RE = r"^(?:https?://(?:www\.)?hotstar\.com/[a-z0-9/-]+/)(?P<id>\d+)"

    @staticmethod
    @click.command(name="Hotstar", short_help="https://hotstar.com")
    @click.argument("title", type=str, required=False)
    @click.option("-rg", "--region", default="id", type=click.Choice(["in", "id", "th"], case_sensitive=False),
                  help="Account region")
    @click.pass_context
    def cli(ctx, **kwargs):
        return Hotstar(ctx, **kwargs)

    def __init__(self, ctx, title, region):
        super().__init__(ctx)
        self.parse_title(ctx, title)
        self.region = region.lower()
        if "/movies/" in title:
            self.movie = True
        else:
            self.movie = False

        assert ctx.parent is not None
        self.vcodec = ctx.parent.params["vcodec"]
        self.acodec = ctx.parent.params["acodec"] or "EC3"
        self.range = ctx.parent.params["range_"]
        self.hdrdv = None

        #self.log.info(self.title)
        #self.log.info(self.range)
        #self.log.info(self.vcodec)
        #self.log.info(self.hdrdv)
        
        self.profile = ctx.obj.profile

        self.device_id = None
        self.hotstar_auth = None
        self.token = None
        self.license_api = None

        self.configure()

    def get_titles(self):
        headers = {
            "Accept": "*/*",
            "Accept-Language": "en-GB,en;q=0.5",
            "hotstarauth": self.hotstar_auth,
            "X-HS-UserToken": self.token,
            "X-HS-Platform": self.config["device"]["platform"]["name"],
            "X-HS-AppVersion": self.config["device"]["platform"]["version"],
            "X-Country-Code": self.region,
            "x-platform-code": "PCTV"
        }
        if self.movie:
            params = {
                "contentId": self.title,
            }
        else:
            params = {
                "contentId": self.title,
                "tao": "0",
                "tas": "700",
            }
        r = self.session.get(
            url=self.config["endpoints"]["movie_title"] if self.movie else self.config["endpoints"]["tv_title"],
            headers=headers,
            params=params,
        )
        try:
            res = r.json()["body"]["results"]["item"]
            #self.log.info(r.json())
        except json.JSONDecodeError:
            raise ValueError(f"Failed to load title manifest: {res.text}")

        self.content_type = res["assetType"]
        
        self.lang = res["langObjs"][0]["iso3code"]
        #self.log.info(self.lang)

        if res["assetType"] == "MOVIE":
            return Title(
                id_=res.get("contentId"),
                type_=Title.Types.MOVIE,
                name=res["title"],
                year=res["year"],
                original_lang=res["langObjs"][0]["iso3code"],
                source=self.ALIASES[0],
                service_data=res,
            )
        else:
            try:
                re = self.session.get(
                    url=self.config["endpoints"]["tv_episodes"],
                    headers=headers,
                    params={
                        "eid": res.get("contentId"),
                        "etid": "2",
                        "tao": "0",
                        "tas": res["episodeCnt"],
                    },
                )
                res = re.json()["body"]["results"]["assets"]["items"]
            except:
                res = r.json()["body"]["results"]["trays"]["items"][0]["assets"]["items"]
            return [Title(
                id_=x.get("contentId"),
                type_=Title.Types.TV,
                name=x.get("showShortTitle"),
                year=x.get("year"),
                season=x.get("seasonNo"),
                episode=x.get("episodeNo"),
                episode_name=x.get("title"),
                original_lang=x["langObjs"][0]["iso3code"],
                source=self.ALIASES[0],
                service_data=x
            ) for x in res]

    def get_playback(self, content_id, range):
        if self.vcodec == "H265":
            quality = "4k"
            video_code = "h265\",\"dvh265"
        else:
            quality = "fhd"
            video_code = "h264"
        r = self.session.get(
            url=self.config["endpoints"]["manifest"],  # .format(id=title.service_data["contentId"]),
            params={
                "content_id": content_id,
                "filters": f"content_type={self.content_type}",
                "client_capabilities": "{\"package\":[\"dash\",\"hls\"],\"container\":[\"fmp4br\",\"fmp4\"],\"ads\":[\"non_ssai\",\"ssai\"],\"audio_channel\":[\"atmos\",\"dolby51\",\"stereo\"],\"encryption\":[\"plain\",\"widevine\"],\"video_codec\":[\"" + video_code + "\"],\"ladder\":[\"tv\",\"full\"],\"resolution\":[\"" + quality + "\"],\"true_resolution\":[\"" + quality + "\"],\"dynamic_range\":[\"" + range + "\"]}",
                "drm_parameters": "{\"widevine_security_level\":[\"SW_SECURE_DECODE\",\"SW_SECURE_CRYPTO\"],\"hdcp_version\":[\"HDCP_V2_2\",\"HDCP_V2_1\",\"HDCP_V2\",\"HDCP_V1\"]}"
            },
            headers={
                "user-agent": "Disney+;in.startv.hotstar.dplus.tv/23.08.14.4.2915 (Android/13)",
                "hotstarauth": self.hotstar_auth,
                "x-hs-usertoken": self.token,
                "x-hs-device-id": self.device_id,
                "x-hs-client": "platform:androidtv;app_id:in.startv.hotstar.dplus.tv;app_version:23.08.14.4;os:Android;os_version:13;schema_version:0.0.970",
                "x-hs-platform": "androidtv",
                "content-type": "application/json",
            },
        ).json()

        try:
            playback = r['success']['page']['spaces']['player']['widget_wrappers'][0]['widget']['data']['player_config'][
                'media_asset']['primary']
            # self.log.info(playback)    
        except:
            #self.log.info(r['success']['page']['spaces']['player']['widget_wrappers'][0]['widget']['data']['player_config']['media_asset'])
            self.log.info(f'Error: {str(r["error"]["error_message"])}')
            self.log.exit(f' - {str(r["error"]["error_message"])}')

        if playback == {}:
            #self.log.info(json.dumps(r, indent=4))
            # sendvtLog('Error: Wanted format is not available!')
            self.log.exit(" - Wanted playback set is unavailable for this title!")

        return playback

    def get_tracks(self, title):
        if self.hdrdv:
            tracks = Tracks()

            session_hdr = self.session
            session_dv = self.session

            playback_hdr = self.get_playback(title.service_data["contentId"], range='hdr10')
            playback_dv = self.get_playback(title.service_data["contentId"], range='dv')

            mpd_url_hdr = playback_hdr['content_url'].split('?')[0]
            mpd_url_dv = playback_dv['content_url'].split('?')[0]

            if 'widevine' in playback_hdr['playback_tags']:
                self.license_api = playback_hdr["license_url"]

            if 'vod-cf' in mpd_url_hdr:
                data_hdr = session_hdr.get(playback_hdr['content_url'])
                cookies_hdr = data_hdr.cookies.get_dict()
                cookies_hdr_ = f"hdntl={cookies_hdr['hdntl']}; CloudFront-Key-Pair-Id={cookies_hdr['CloudFront-Key-Pair-Id']}; CloudFront-Policy={cookies_hdr['CloudFront-Policy']}; CloudFront-Signature={cookies_hdr['CloudFront-Signature']}"
                session_hdr.headers.update({'cookie': cookies_hdr_})
            else:
                session_hdr.proxies.update(
                    {'all': 'http://150.230.141.229:3128'})
                data_hdr = session_hdr.get(playback_hdr['content_url'])
                cookies_hdr = data_hdr.cookies.get_dict()
                cookies_hdr_ = f"hdntl={cookies_hdr['hdntl']}"
                session_hdr.headers.update({'cookie': cookies_hdr_})

            tracks_hdr = Tracks.from_mpd(
                url=mpd_url_hdr,
                data=data_hdr.text,
                session=session_hdr,
                source=self.ALIASES[0],
            )
            for track in tracks_hdr.videos:
                if not track.hdr10:
                    track.hdr10 = True

            if 'vod-cf' in mpd_url_dv:
                data_dv = session_dv.get(playback_dv['content_url'])
                cookies_dv = data_dv.cookies.get_dict()
                cookies_dv_ = f"hdntl={cookies_dv['hdntl']}; CloudFront-Key-Pair-Id={cookies_dv['CloudFront-Key-Pair-Id']}; CloudFront-Policy={cookies_dv['CloudFront-Policy']}; CloudFront-Signature={cookies_dv['CloudFront-Signature']}"
                session_dv.headers.update({'cookie': cookies_dv_})
            else:
                session_dv.proxies.update(
                    {'all': 'http://150.230.141.229:3128'})
                data_dv = session_dv.get(playback_dv['content_url'])
                cookies_dv = data_dv.cookies.get_dict()
                cookies_dv_ = f"hdntl={cookies_dv['hdntl']}"
                session_dv.headers.update({'cookie': cookies_dv_})

            tracks_dv = Tracks.from_mpd(
                url=mpd_url_dv,
                data=data_dv.text,
                session=session_dv,
                source=self.ALIASES[0],
            )
            tracks.add(tracks_hdr, warn_only=True)
            tracks.add(tracks_dv, warn_only=True)
            for track in tracks:
                track.needs_proxy = True
            return tracks
        else:
            range = 'sdr'
            if self.range == 'HDR10':
                range = 'hdr10'
            elif self.range == 'DV':
                range = 'dv'

            playback = self.get_playback(title.service_data["contentId"], range)
            #self.log.info(playback)

            if 'widevine' in playback['playback_tags']:
                self.license_api = playback["license_url"]

            if 'vod-cf' in playback['content_url']:
                mpd_url = playback['content_url'].split('?')[0]
                datax = self.session.get(playback['content_url'])
                data = datax.text
                cookies = datax.cookies.get_dict()
                cookies_ = f"hdntl={cookies['hdntl']}; CloudFront-Key-Pair-Id={cookies['CloudFront-Key-Pair-Id']}; CloudFront-Policy={cookies['CloudFront-Policy']}; CloudFront-Signature={cookies['CloudFront-Signature']}"
                self.session.headers.update({'cookie': cookies_})
            else:
                mpd_url = playback['content_url']
                r = Request(playback["content_url"])
                r.add_header(
                    "user-agent",
                    "Disney+;in.startv.hotstar.dplus.tv/23.08.14.4.2915 (Android/13)",
                )
                r1 = urlopen(r)
                cookie = ""
                cookies = r1.info().get_all("Set-Cookie")
                if cookies is not None:
                    for cookiee in cookies:
                        cookie += cookiee.split(";")[0] + ";"
                    #self.log.info(cookie)
                self.session.headers = {
                    "cookie": cookie,
                    "user-agent": "Disney+;in.startv.hotstar.dplus.tv/23.08.14.4.2915 (Android/13)",
                }
                data = r1.read()
                #self.log.info(data)
                if ".m3u8" in mpd_url:
                    data = data.decode("utf-8")

            self.log.info(mpd_url)

            if ".mpd" in mpd_url:
                tracks = Tracks.from_mpd(
                    url=mpd_url,
                    data=data,
                    session=self.session,
                    source=self.ALIASES[0],
                )
            else:
                tracks = Tracks.from_m3u8(
                    master=m3u8.loads(data, uri=mpd_url),
                    source=self.ALIASES[0]
                )

            for track in tracks:
                track.needs_proxy = True

            for track in tracks.videos:
                if self.range == "HDR10":
                    if not track.hdr10:
                        track.hdr10 = True
                track.language = self.lang
                
            for track in tracks.audios:
                if track.language == "und":
                    track.language = self.lang

            return tracks

    def get_chapters(self, title):
        return []

    def certificate(self, **_):
        return None  # will use common privacy cert

    def license(self, challenge, **_):
        return self.session.post(
            url=self.license_api,
            data=challenge  # expects bytes
        ).content

    # Service specific functions

    def configure(self):
        self.session.headers.update({
            "Origin": "https://www.hotstar.com",
            "Referer": f"https://www.hotstar.com/{self.region}"
        })
        self.log.info("Logging into Hotstar")
        self.hotstar_auth = self.get_akamai()
        self.log.info(f" + Calculated HotstarAuth: {self.hotstar_auth}")
        if self.cookies:
            self.device_id = self.session.cookies.get("deviceId")
            self.log.info(f" + Using Device ID: {self.device_id}")
        else:
            self.device_id = str(uuid.uuid4())
            self.log.info(f" + Created Device ID: {self.device_id}")
        self.token = self.get_token()
        self.log.info(" + Obtained tokens")

    @staticmethod
    def get_akamai():
        enc_key = b"\x05\xfc\x1a\x01\xca\xc9\x4b\xc4\x12\xfc\x53\x12\x07\x75\xf9\xee"
        st = int(time.time())
        exp = st + 12000
        res = f"st={st}~exp={exp}~acl=/*"
        res += "~hmac=" + hmac.new(enc_key, res.encode(), hashlib.sha256).hexdigest()
        return res

    def get_token(self):
        token_cache_path = self.get_cache("token_{profile}.json".format(profile=self.profile))
        if os.path.isfile(token_cache_path):
            with open(token_cache_path, encoding="utf-8") as fd:
                token = json.load(fd)
            if token.get("exp", 0) > int(time.time()):
                # not expired, lets use
                self.log.info(" + Using cached auth tokens...")
                return token["uid"]
            else:
                # expired, refresh
                self.log.info(" + Refreshing and using cached auth tokens...")
                return self.save_token(self.refresh(token["uid"], token["sub"]["deviceId"]), token_cache_path)
        # get new token
        if self.cookies:
            token = self.session.cookies.get("sessionUserUP", None, 'www.hotstar.com', '/' + self.region)
        else:
            raise self.log.exit(f" - Please add cookies")
            # token = self.login()
        return self.save_token(token, token_cache_path)

    @staticmethod
    def save_token(token, to):
        # Decode the JWT data component
        data = json.loads(base64.b64decode(token.split(".")[1] + "===").decode("utf-8"))
        data["uid"] = token
        data["sub"] = json.loads(data["sub"])

        os.makedirs(os.path.dirname(to), exist_ok=True)
        with open(to, mode="w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=4))

        return token

    def refresh(self, user_id_token, device_id):
        json_data = {
            'deeplink_url': f'/{self.region}?client_capabilities=%7B%22ads%22%3A%5B%22non_ssai%22%5D%2C%22audio_channel%22%3A%5B%22stereo%22%5D%2C%22container%22%3A%5B%22fmp4%22%2C%22ts%22%5D%2C%22dvr%22%3A%5B%22short%22%5D%2C%22dynamic_range%22%3A%5B%22sdr%22%5D%2C%22encryption%22%3A%5B%22widevine%22%2C%22plain%22%5D%2C%22ladder%22%3A%5B%22web%22%2C%22tv%22%2C%22phone%22%5D%2C%22package%22%3A%5B%22dash%22%2C%22hls%22%5D%2C%22resolution%22%3A%5B%22sd%22%2C%22hd%22%5D%2C%22video_codec%22%3A%5B%22h264%22%5D%2C%22true_resolution%22%3A%5B%22sd%22%2C%22hd%22%2C%22fhd%22%5D%7D&drm_parameters=%7B%22hdcp_version%22%3A%5B%22HDCP_V2_2%22%5D%2C%22widevine_security_level%22%3A%5B%22SW_SECURE_DECODE%22%5D%2C%22playready_security_level%22%3A%5B%5D%7D',
            'app_launch_count': 1,
        }
        r = self.session.post(
            url=self.config["endpoints"]["refresh"],
            headers={
                'x-hs-usertoken': user_id_token,
                'X-HS-Platform': self.config["device"]["platform"]["name"],
                'X-Country-Code': self.region,
                'X-HS-Accept-language': 'eng',
                'X-Request-Id': str(uuid.uuid4()),
                'x-hs-device-id': device_id,
                'X-HS-Client-Targeting': f'ad_id:{device_id};user_lat:false',
                'X-HS-Client': 'platform:web;app_version:23.06.23.3;browser:Firefox;schema_version:0.0.911',
            },
            json=json_data
        )
        #self.log.info(r.json())
        for cookie in self.cookies:
            if cookie.name == 'sessionUserUP' and cookie.path == f"/{self.region}" and cookie.domain == 'www.hotstar.com':
                cookie.value = r.headers["x-hs-usertoken"]
        for x in self.ALIASES:
            cookie_file = os.path.join(directories.cookies, x.lower(), f"{self.profile}.txt")
            if not os.path.isfile(cookie_file):
                cookie_file = os.path.join(directories.cookies, x, f"{self.profile}.txt")
            if os.path.isfile(cookie_file):
                self.cookies.save(cookie_file, ignore_discard=True, ignore_expires=True)
                break
        return r.headers["x-hs-usertoken"]

    def login(self):
        """
        Log in to HOTSTAR and return a JWT User Identity token.
        :returns: JWT User Identity token.
        """
        if self.credentials.username == "username" and self.credentials.password == "password":
            logincode_url = f"https://api.hotstar.com/{self.region}/aadhar/v2/firetv/{self.region}/users/logincode/"
            logincode_headers = {
                "Content-Length": "0",
                "User-Agent": "Hotstar;in.startv.hotstar/3.3.0 (Android/8.1.0)"
            }
            logincode = self.session.post(
                url=logincode_url,
                headers=logincode_headers
            ).json()["description"]["code"]
            print(f"Go to tv.hotstar.com and put {logincode}")
            logincode_choice = input('Did you put as informed above? (y/n): ')
            if logincode_choice.lower() == 'y':
                res = self.session.get(
                    url=logincode_url + logincode,
                    headers=logincode_headers
                )
            else:
                self.log.exit(" - Exited.")
                raise
        else:
            res = self.session.post(
                url=self.config["endpoints"]["login"],
                json={
                    "isProfileRequired": "false",
                    "userData": {
                        "deviceId": self.device_id,
                        "password": self.credentials.password,
                        "username": self.credentials.username,
                        "usertype": "email"
                    },
                    "verification": {}
                },
                headers={
                    "hotstarauth": self.hotstar_auth,
                    "content-type": "application/json"
                }
            )
        try:
            data = res.json()
        except json.JSONDecodeError:
            self.log.exit(f" - Failed to get auth token, response was not JSON: {res.text}")
            raise
        if "errorCode" in data:
            self.log.exit(f" - Login failed: {data['description']} [{data['errorCode']}]")
            raise
        return data["description"]["userIdentity"]