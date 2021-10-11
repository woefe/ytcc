# Installation

## From PyPi
```shell script
pip install ytcc
```
Or alternatively with [yt-dlp](https://github.com/yt-dlp/yt-dlp): `pip install ytcc[yt_dlp]`

## Arch Linux
Install [ytcc](https://aur.archlinux.org/packages/ytcc/) or [ytcc-git](https://aur.archlinux.org/packages/ytcc-git/) from the AUR.

## Debian / Ubuntu
```shell script
apt install ytcc
```

## NixOS
```shell script
nix-env -iA nixos.ytcc
```

## Void Linux
Install the [ytcc](https://voidlinux.org/packages/?arch=x86_64&q=ytcc) package.

## Gentoo
Note: this is maintained by [@EmRowlands](https://github.com/EmRowlands),
please report installation errors to the erowl-overlay issue tracker before the
main ytcc tracker.

Add the `erowl-overlay` using `eselect-repository` (or layman):

```
eselect repository add erowl-overlay git https://gitlab.com/EmRowlands/erowl-overlay.git
```

Install `net-misc/ytcc`. Currently (October 2020), ytcc v1 is stable and ytcc
v2 betas are `~arch`. A 9999 ebuild is also available.

## Without installation
You can start ytcc directly from the cloned repo, if all requirements are installed.

```shell script
./ytcc.py --help
```

Hard requirements:
- [Python 3.7](https://www.python.org/) or later
- [Click](https://click.palletsprojects.com/en/7.x/)
- [youtube-dl](https://github.com/ytdl-org/youtube-dl)
- [wcwidth](https://github.com/jquast/wcwidth)

Optional requirements:
- [ffmpeg](https://ffmpeg.org/) for youtube-dl's `.mp4` or `.mkv` merging
- [mpv](https://mpv.io/), if you want to play audio or video

Requirements for the ytccf.sh bash script:
- [fzf](https://github.com/junegunn/fzf) version 0.23.1 or newer
- Optionally, for thumbnail support
  - [curl](https://curl.se/)
  - Either [ueberzug](https://github.com/seebye/ueberzug) or [kitty](https://sw.kovidgoyal.net/kitty/).
