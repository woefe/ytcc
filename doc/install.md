# Installation
## From PyPi
```shell script
pip install ytcc
```

## Arch Linux
Install [ytcc-git](https://aur.archlinux.org/packages/ytcc-git/) from the AUR.
The [ytcc](https://aur.archlinux.org/packages/ytcc/) package will be upgraded to version 2.0.0, when it has a stable release.

## Gentoo
Note: this is maintained by [@EmRowlands](https://github.com/EmRowlands),
please report installation errors to the erowl-overlay issue tracker before the
main ytcc tracker.

Add the `erowl-overlay` using `eselect-repository` (or layman):

```
eselect repository add erowl-overlay git https://gitlab.com/EmRowlands/erowl-overlay.git
```

Install `net-misc/ytcc`. Currently (October 2020), ytcc v1 is stable and ytcc
v2 betas are `~arch`. A 9999 ebuild is also avaliable.

## Without installation
You can start ytcc directly from the cloned repo, if all requirements are installed.

```shell script
./ytcc.py --help
```

Hard requirements:
- [Python 3.7](https://www.python.org/)
- [Click](https://click.palletsprojects.com/en/7.x/),
- [youtube-dl](https://github.com/ytdl-org/youtube-dl)
- [wcwidth](https://github.com/jquast/wcwidth)

Optional requirements:
- [ffmpeg](https://ffmpeg.org/) for youtube-dl's `.mp4` or `.mkv` merging
- [mpv](https://mpv.io/), if you want to play audio or video
