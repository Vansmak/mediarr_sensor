"""Jellyseerr/Overseerr discovery features for Mediarr."""
import logging
from datetime import datetime
from ..common.tmdb_sensor import TMDBMediaSensor
import async_timeout

_LOGGER = logging.getLogger(__name__)

class SeerDiscoveryMediarrSensor(TMDBMediaSensor):
    """Seer sensor for discover/trending/popular."""
    
    def __init__(self, session, api_key, url, tmdb_api_key, max_items, content_type, media_type=None):
        """Initialize the sensor."""
        super().__init__(session, tmdb_api_key)
        self._seer_api_key = api_key
        self._url = url.rstrip('/')
        self._max_items = max_items
        self._content_type = content_type
        self._media_type = media_type
        # Customize name based on content type and media type
        if content_type in ["popular_movies", "popular_tv"]:
            self._name = f"Seer Mediarr Popular {'Movies' if media_type == 'movies' else 'TV'}"
        else:
            self._name = f"Seer Mediarr {content_type.title()}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        if self._content_type in ["popular_movies", "popular_tv"]:
            return f"seer_mediarr_{self._content_type}_{self._url}"
        return f"seer_mediarr_{self._content_type}_{self._url}"

    async def _fetch_media_list(self):
        """Fetch media list from Seer."""
        try:
            headers = {'X-Api-Key': self._seer_api_key}
            params = {}
            
            # Build the correct URL and parameters
            if self._content_type == "trending":
                url = f"{self._url}/api/v1/discover/trending"
            elif self._content_type == "popular_movies":
                url = f"{self._url}/api/v1/discover/movies"
                params["sortBy"] = "popularity.desc"
            elif self._content_type == "popular_tv":
                url = f"{self._url}/api/v1/discover/tv"
                params["sortBy"] = "popularity.desc"
            elif self._content_type == "discover":
                # For discover, use movies as default
                media_type = "movies"
                url = f"{self._url}/api/v1/discover/{media_type}"
            else:
                _LOGGER.error("Unknown content type: %s", self._content_type)
                return None
            
            _LOGGER.debug("Making request to URL: %s with params: %s", url, params)
            
            async with async_timeout.timeout(10):
                async with self._session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    _LOGGER.error("Failed request to %s with params %s, status: %s", url, params, response.status)
                    raise Exception(f"Failed to fetch {self._content_type}. Status: {response.status}")
                    
        except Exception as err:
            _LOGGER.error("Error fetching %s: %s", self._content_type, err)
            return None

    async def async_update(self):
        """Update the sensor."""
        try:
            all_items = []
            
            if self._content_type == "discover":
                # For discover, fetch both movies and TV
                for media_type in ['movies', 'tv']:
                    data = await self._fetch_media_list()
                    if data and data.get('results'):
                        for item in data['results']:
                            tmdb_id = item.get('id')
                            media_type = 'movie' if media_type == 'movies' else 'tv'
                            
                            details = await self._get_tmdb_details(tmdb_id, media_type)
                            if not details:
                                continue
                                
                            poster_url, backdrop_url, main_backdrop_url = await self._get_tmdb_images(tmdb_id, media_type)
                            
                            all_items.append({
                                'title': details['title'],
                                'overview': details['overview'][:100] + '...',
                                'year': details['year'],
                                'poster': str(poster_url or ""),
                                'fanart': str(main_backdrop_url or backdrop_url or ""),
                                'banner': str(backdrop_url or ""),
                                'release': details['year'],
                                'type': 'Movie' if media_type == 'movie' else 'TV Show',
                                'flag': 1
                            })
            else:
                # For trending and popular, fetch single type
                data = await self._fetch_media_list()
                if data and data.get('results'):
                    for item in data['results']:
                        media_type = 'movie' if self._content_type == 'popular_movies' else 'tv'
                        tmdb_id = item.get('id')
                        
                        details = await self._get_tmdb_details(tmdb_id, media_type)
                        if not details:
                            continue
                            
                        poster_url, backdrop_url, main_backdrop_url = await self._get_tmdb_images(tmdb_id, media_type)
                        
                        all_items.append({
                            'title': details['title'],
                            'overview': details['overview'][:100] + '...',
                            'year': details['year'],
                            'poster': str(poster_url or ""),
                            'fanart': str(main_backdrop_url or backdrop_url or ""),
                            'banner': str(backdrop_url or ""),
                            'release': details['year'],
                            'type': 'Movie' if media_type == 'movie' else 'TV Show',
                            'flag': 1
                        })

            # Sort and limit items
            all_items = all_items[:self._max_items]

            if not all_items:
                all_items.append({
                    'title_default': '$title',
                    'line1_default': '$type',
                    'line2_default': '$overview',
                    'line3_default': '$year',
                    'icon': 'mdi:movie-search'
                })

            self._state = len(all_items)
            self._attributes = {'data': all_items}
            self._available = True

        except Exception as err:
            _LOGGER.error("Error updating %s sensor: %s", self._content_type, err)
            self._state = 0
            self._attributes = {'data': []}
            self._available = False