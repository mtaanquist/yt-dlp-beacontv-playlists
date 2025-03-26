import json
import re

from .common import InfoExtractor
from ..utils import (
    ExtractorError,
    parse_iso8601,
    traverse_obj,
)


class BeaconTvIE(InfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?beacon\.tv/content/(?P<id>[\w-]+)'

    _TESTS = [{
        'url': 'https://beacon.tv/content/welcome-to-beacon',
        'md5': 'b3f5932d437f288e662f10f3bfc5bd04',
        'info_dict': {
            'id': 'welcome-to-beacon',
            'ext': 'mp4',
            'upload_date': '20240509',
            'description': 'md5:ea2bd32e71acf3f9fca6937412cc3563',
            'thumbnail': 'https://cdn.jwplayer.com/v2/media/I4CkkEvN/poster.jpg?width=720',
            'title': 'Your home for Critical Role!',
            'timestamp': 1715227200,
            'duration': 105.494,
        },
    }, {
        'url': 'https://beacon.tv/content/re-slayers-take-trailer',
        'md5': 'd879b091485dbed2245094c8152afd89',
        'info_dict': {
            'id': 're-slayers-take-trailer',
            'ext': 'mp4',
            'title': 'The Re-Slayer’s Take | Official Trailer',
            'timestamp': 1715189040,
            'upload_date': '20240508',
            'duration': 53.249,
            'thumbnail': 'https://cdn.jwplayer.com/v2/media/PW5ApIw3/poster.jpg?width=720',
        },
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)

        content_data = traverse_obj(self._search_nextjs_data(webpage, video_id), (
            'props', 'pageProps', '__APOLLO_STATE__',
            lambda k, v: k.startswith('Content:') and v['slug'] == video_id, any))
        if not content_data:
            raise ExtractorError('Failed to extract content data')

        jwplayer_data = traverse_obj(content_data, (
            (('contentVideo', 'video', 'videoData'),
             ('contentPodcast', 'podcast', 'audioData')), {json.loads}, {dict}, any))
        if not jwplayer_data:
            if content_data.get('contentType') not in ('videoPodcast', 'video', 'podcast'):
                raise ExtractorError('Content is not a video/podcast', expected=True)
            if traverse_obj(content_data, ('contentTier', '__ref')) != 'MemberTier:65b258d178f89be87b4dc0a4':
                self.raise_login_required('This video/podcast is for members only')
            raise ExtractorError('Failed to extract content')

        return {
            **self._parse_jwplayer_data(jwplayer_data, video_id),
            **traverse_obj(content_data, {
                'title': ('title', {str}),
                'description': ('description', {str}),
                'timestamp': ('publishedAt', {parse_iso8601}),
            }),
        }

class BeaconTvSeriesIE(InfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?beacon\.tv/series/(?P<id>[\w-]+)'
    _TESTS = [{
        'url': 'https://beacon.tv/series/critical-cooldown',
        'info_dict': {
            'id': 'critical-cooldown',
            'title': 'Critical Cooldown',
        },
        'playlist_mincount': 1,
    }]

    def _real_extract(self, url):
        playlist_id = self._match_id(url)
        webpage = self._download_webpage(url, playlist_id)

        # Extract series title from NextJS data
        series_data = traverse_obj(self._search_nextjs_data(webpage, playlist_id), (
            'props', 'pageProps', '__APOLLO_STATE__',
            lambda k, v: k.startswith('Series:') and v.get('slug') == playlist_id, any))

        series_title = traverse_obj(series_data, 'title', default=playlist_id)

        # Search for video links in the webpage using standard _search_regex with findall=True
        entries = []

        # First pattern: with role="link" attribute
        video_paths = self._search_regex(
            r'<a[^>]+href="/content/([\w-]+)"', webpage,
            'video links', default='', flags=re.DOTALL)

        if video_paths:
            for video_path in re.findall(r'([\w-]+)', video_paths):
                video_url = f'https://beacon.tv/content/{video_path}'
                entries.append(self.url_result(
                    video_url, ie=BeaconTvIE.ie_key(), video_id=video_path))

        # Second pattern: simple href
        if not entries:
            video_paths = self._search_regex(
                r'href="/content/([\w-]+)"', webpage,
                'video links', default='')

            if video_paths:
                for video_path in re.findall(r'([\w-]+)', video_paths):
                    video_url = f'https://beacon.tv/content/{video_path}'
                    entries.append(self.url_result(
                        video_url, ie=BeaconTvIE.ie_key(), video_id=video_path))

        # If regex approach didn't find anything, try NextJS data extraction
        if not entries:
            contents = traverse_obj(self._search_nextjs_data(webpage, playlist_id), (
                'props', 'pageProps', '__APOLLO_STATE__',
                lambda k, v: k.startswith('Content:') and traverse_obj(v, ('series', '__ref')) == f'Series:{playlist_id}',
            ))

            for content in contents or []:
                video_id = content.get('slug')
                if video_id:
                    video_url = f'https://beacon.tv/content/{video_id}'
                    entries.append(self.url_result(
                        video_url, ie=BeaconTvIE.ie_key(), video_id=video_id))

        return self.playlist_result(entries, playlist_id, series_title)
