# VineTrimmer-PlayReady
A tool to download and remove DRM from streaming services. A version of an old fork of [devine](https://github.com/devine-dl/devine).
Modified to remove Playready DRM instead of Widevine.

## Features
 - Progress Bars for decryption ([mp4decrypt](https://github.com/chu23465/bentoOldFork)) (Shaka)
 - Refresh Token fixed for Amazon service
 - Reprovision .prd after a week
 - ISM manifest support (Microsoft Smooth Streaming) (Few features to be added)
 - N_m3u8DL-RE downloader support


## Usage
### Config

`vinetrimmer.yml` located within the `/vinetrimmer/` folder.

`decryptor:` either `mp4decrypt` or `packager`

(shaka-packager fails to decrypt files downloaded from MSS manifests)

`tag:` tag for your release group

CDM can be configured per service or per profile.

```
cdm:
    default: {text}
    Amazon: {text}
```

All other option can be left to defaults, unless you know what you are doing. 

### General Options

Usage: vt.cmd [OPTIONS] COMMAND [ARGS]...

Example : 
```bash
poetry run vt dl -al en -sl en --selected -q 2160 -r HDR -w S01E18-S01E25 AMZN -b CBR --ism 0IQZZIJ6W6TT2CXPT6ZOZYX396
```

Above command gets english subtitles + audio, selects the HDR + 4K track, gets episodes from S01E18 to S01E25 from Amazon with CBR bitrate, tries to force ISM and the title-ID is 0IQZZIJ6W6TT2CXPT6ZOZYX396


Options:
| Command line argument      | Description                                                                                   | Default Value                     |
|----------------------------|-----------------------------------------------------------------------------------------------|-----------------------------------|
|  -p, --profile TEXT        | Profile to use when multiple profiles are defined for a service.                              |  "default"                        |
|  -q, --quality TEXT        | Download Resolution                                                                           |  1080                             |
|  -v, --vcodec TEXT         | Video Codec                                                                                   |  H264                             |
|  -a, --acodec TEXT         | Audio Codec                                                                                   |  None                             |
|  -vb, --vbitrate INTEGER   | Video Bitrate                                                                                 |  Max                              |
|  -ab, --abitrate INTEGER   | Audio Bitrate                                                                                 |  Max                              |
|  -aa, --atmos              | Prefer Atmos Audio                                                                            |  False                            |
|  -r, --range TEXT          | Video Color Range `HDR`, `HDR10`, `DV`, `SDR`                                                 |  SDR                              |
|  -w, --wanted TEXT         | Wanted episodes, e.g. `S01-S05,S07`, `S01E01-S02E03`, `S02-S02E03`                            |  Default to all                   |
|  -al, --alang TEXT         | Language wanted for audio.                                                                    |  Defaults to original language    |
|  -sl, --slang TEXT         | Language wanted for subtitles.                                                                |  Defaults to original language    |
|  --proxy TEXT              | Proxy URI to use. If a 2-letter country is provided, it will try get a proxy from the config. |  None                             |
|  -A, --audio-only          | Only download audio tracks.                                                                   |  False                            |
|  -S, --subs-only           | Only download subtitle tracks.                                                                |  False                            |
|  -C, --chapters-only       | Only download chapters.                                                                       |  False                            |
|  -ns, --no-subs            | Do not download subtitle tracks.                                                              |  False                            |
|  -na, --no-audio           | Do not download audio tracks.                                                                 |  False                            |
|  -nv, --no-video           | Do not download video tracks.                                                                 |  False                            |
|  -nc, --no-chapters        | Do not download chapters tracks.                                                              |  False                            |
|  -ad, --audio-description  | Download audio description tracks.                                                            |  False                            |
|  --list                    | Skip downloading and list available tracks and what tracks would have been downloaded.        |  False                            |
|  --selected                | List selected tracks and what tracks are downloaded.                                          |  False                            |
|  --cdm                     | Override the CDM that will be used for decryption.                                            |  None                             |
|  --keys                    | Skip downloading, retrieve the decryption keys (via CDM or Key Vaults) and print them.        |  False                            |
|  --cache                   | Disable the use of the CDM and only retrieve decryption keys from Key Vaults. If a needed key is unable to be retrieved from any Key Vaults, the title is skipped.|  False  |
|  --no-cache                | Disable the use of Key Vaults and only retrieve decryption keys from the CDM.                 |  False                            |
|  --no-proxy                | Force disable all proxy use.                                                                  |  False                            |
|  -nm, --no-mux             | Do not mux the downloaded and decrypted tracks.                                               |  False                            |
|  --mux                     | Force muxing when using --audio-only/--subs-only/--chapters-only.                             |  False                            |
|  -?, -h, --help            | Show this message and exit.                                                                   |                                   |


COMMAND :-

| Alaias |  Command      | Service Link                               |
|--------|---------------|--------------------------------------------|
| AMZN   |  Amazon       | https://amazon.com, https://primevideo.com |
| ATVP   |  AppleTVPlus  | https://tv.apple.com                       |
| MAX    |  Max          | https://max.com                            |
| NF     |  Netflix      | https://netflix.com                        |
  
### Amazon Specific Options

Usage: vt.cmd AMZN [OPTIONS] [TITLE]

  Service code for Amazon VOD (https://amazon.com) and Amazon Prime Video (https://primevideo.com).

  Authorization: Cookies
  
  Security: 
  ```
  UHD@L1/SL3000
  FHD@L3(ChromeCDM)/SL2000
  SD@L3
  ```
  Maintains their own license server like Netflix, be cautious.
  
  Region is chosen automatically based on domain extension found in cookies.
  Prime Video specific code will be run if the ASIN is detected to be a prime video variant.
  Use 'Amazon Video ASIN Display' for Tampermonkey addon for ASIN
  https://greasyfork.org/en/scripts/381997-amazon-video-asin-display

  vt dl --list -z uk -q 1080 Amazon B09SLGYLK8


|  Command Line Switch                | Description                                                                                 |
|-------------------------------------|---------------------------------------------------------------------------------------------|
|  -b, --bitrate [CVBR|CBR|CVBR+CBR]  | Video Bitrate Mode to download in. CVBR=Constrained Variable Bitrate, CBR=Constant Bitrate. |
|  -c, --cdn TEXT                     | CDN to download from, defaults to the CDN with the highest weight set by Amazon.            |
|  -vq, --vquality [SD|HD|UHD]        | Manifest quality to request.                                                                |
|  -s, --single                       | Force single episode/season instead of getting series ASIN.                                 |
|  -am, --amanifest [CVBR|CBR|H265]   | Manifest to use for audio. Defaults to H265 if the video manifest is missing 640k audio.    |
|  -aq, --aquality [SD|HD|UHD]        | Manifest quality to request for audio. Defaults to the same as --quality.                   |
|  -ism, --ism                        | Set manifest override to SmoothStreaming. Defaults to DASH w/o this flag.                   |
|  -?, -h, --help                     | Show this message and exit.                                                                 |
  
## Proxy
I recommend [Windscribe](https://windscribe.com/). You can sign up, getting 10 GB of traffic credit every month for free. We use the VPN for everything except downloading video/audio. 
Tested so far on Amazon, AppleTVPlus, Max.

### Steps:
1. For each service, within get_tracks() function we do this below.
    ```python
    for track in tracks:
        track.needs_proxy = False
    ```
    
    This flag signals that this track does not need a proxy and a proxy will not be passed to downloader even if proxy given in CLI options.

2. Download Windscribe app and install it.

3. Go to `Options` -> `Connection` -> `Split Tunneling`. Enable it.
   
    Set `Mode` as `Inclusive`.

5. Go to `Options` -> `Connection` -> `Proxy Gateway`. Enable it. Select `Proxy Type` as `HTTP`.
   
    Copy the `IP` field (will look something like `192.168.0.141:9766`)

    Pass above copied to Vinetrimmer with the proxy flag like below.

    ```bash
    ...(other flags)... --proxy http://192.168.0.141:9766 .......
    ```

## Other

Activate venv then, to use programs in `scripts` folder use like below
```bash
poetry run python scripts/ParseKeybox.py
```
