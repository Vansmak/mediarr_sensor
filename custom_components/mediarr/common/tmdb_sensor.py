"""TMDB-based media sensor for Mediarr."""
import logging
from abc import ABC, abstractmethod
import async_timeout
from datetime import datetime
from ..common.sensor import MediarrSensor

_LOGGER = logging.getLogger(__name__)
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p"

class TMDBMediaSensor(MediarrSensor, ABC):
    """Base class for TMDB-based media sensors."""
   
    def __init__(self, session, tmdb_api_key, language='en', filters=None):
        """Initialize the sensor."""
        super().__init__()
        self._session = session
        self._tmdb_api_key = tmdb_api_key
        self._language = language
        self._available = True
        self._cache = {}
       
        # Initialize default filters
        self._filters = {
            'language': language,
            'min_year': 0,
            'exclude_talk_shows': True,
            'exclude_genres': [10763, 10764, 10767],  # News, Reality, Talk shows
            'exclude_non_english': True
        }
       
        # Update with user-provided filters
        if filters:
            self._filters.update(filters)
   
    

    # In tmdb_sensor.py, update _format_date method
    def _format_date(self, date_str):
        """Format date string to YYYY-MM-DD format."""
        if not date_str or date_str == 'Unknown':
            return 'Unknown'
        try:
            # Remove any timezone info and clean the string
            date_str = str(date_str).split('T')[0].split('.')[0].strip()
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                return date_str
            except ValueError:
                return 'Unknown'
        except Exception:
            return 'Unknown'

    def is_talk_show(self, title):
        """Check if a show title appears to be a talk show or similar format."""
        if not self._filters.get('exclude_talk_shows', True):
            return False
            
        keywords = [
            'tonight show', 'late show', 'late night', 'daily show',
            'talk show', 'with seth meyers', 'with james corden',
            'with jimmy', 'with stephen', 'with trevor', 'news',
            'live with', 'watch what happens live', 'the view',
            'good morning', 'today show', 'kimmel', 'colbert',
            'fallon', 'ellen', 'conan', 'graham norton', 'meet the press',
            'face the nation', 'last week tonight', 'real time',
            'kelly and', 'kelly &', 'jeopardy', 'wheel of fortune',
            'daily mail', 'entertainment tonight', 'zeiten', 'schlechte'
        ]
        
        title_lower = title.lower()
        return any(keyword in title_lower for keyword in keywords)

    def should_include_item(self, item, media_type):
        """Apply filters to determine if an item should be included."""
        # Filter by year
        if media_type == 'tv' and 'first_air_date' in item and item['first_air_date']:
            try:
                year = int(item['first_air_date'].split('-')[0])
                if year < self._filters.get('min_year', 0):
                    return False
            except (ValueError, IndexError):
                pass
        elif media_type == 'movie' and 'release_date' in item and item['release_date']:
            try:
                year = int(item['release_date'].split('-')[0])
                if year < self._filters.get('min_year', 0):
                    return False
            except (ValueError, IndexError):
                pass

        # Filter by language
        if self._filters.get('exclude_non_english', True) and item.get('original_language') != 'en':
            return False

        # Filter by genre
        excluded_genres = self._filters.get('exclude_genres', [])
        if any(genre_id in excluded_genres for genre_id in item.get('genre_ids', [])):
            return False

        # Filter for TV talk shows
        if media_type == 'tv':
            title = item.get('name', '')
            if self.is_talk_show(title):
                return False

        return True
    
    async def _fetch_tmdb_data(self, endpoint, params=None):
        """Fetch data from TMDB API."""
        try:
            if not self._tmdb_api_key:
                _LOGGER.error("No TMDB API key provided")
                return None

            headers = {
                "Authorization": f"Bearer {self._tmdb_api_key}",
                "Accept": "application/json"
            }

            # Check if endpoint already contains query parameters
            if '?' in endpoint:
                url = f"{TMDB_BASE_URL}/{endpoint}&api_key={self._tmdb_api_key}"
            else:
                url = f"{TMDB_BASE_URL}/{endpoint}?api_key={self._tmdb_api_key}"
            
            if params:
                params = {k: str(v) if v is not None else "" for k, v in params.items()}
                # Don't add api_key to params as it's already in the URL
                async with async_timeout.timeout(10):
                    async with self._session.get(
                        url,
                        params=params,
                        headers=headers
                    ) as response:
                        if response.status == 200:
                            return await response.json()
                        elif response.status == 404:
                            _LOGGER.debug("TMDB resource not found: %s", url)
                            return None
                        else:
                            _LOGGER.error("TMDB API error: %s for URL: %s", response.status, url)
                            return None
            else:
                async with async_timeout.timeout(10):
                    async with self._session.get(
                        url,
                        headers=headers
                    ) as response:
                        if response.status == 200:
                            return await response.json()
                        elif response.status == 404:
                            _LOGGER.debug("TMDB resource not found: %s", url)
                            return None
                        else:
                            _LOGGER.error("TMDB API error: %s for URL: %s", response.status, url)
                            return None
        except Exception as err:
            _LOGGER.error("Error fetching TMDB data: %s", err)
            return None
    

    
    async def _get_tmdb_images(self, tmdb_id, media_type='movie'):
        """Get TMDB image URLs without language filtering."""
        if not tmdb_id:
            return None, None, None

        cache_key = f"images_{media_type}_{tmdb_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        try:
            # Just get all images without language filtering
            data = await self._fetch_tmdb_data(f"{media_type}/{tmdb_id}/images")
            
            poster_url = backdrop_url = main_backdrop_url = None
            
            if data:
                _LOGGER.debug("Image data for %s (%s): Posters: %d, Backdrops: %d", 
                            tmdb_id, media_type, len(data.get('posters', [])), len(data.get('backdrops', [])))
                
                # Get first available poster
                posters = data.get('posters', [])
                if posters:
                    poster_path = posters[0].get('file_path')
                    poster_url = f"{TMDB_IMAGE_BASE_URL}/w500{poster_path}" if poster_path else None
                
                # Get first and second available backdrops
                backdrops = data.get('backdrops', [])
                if backdrops:
                    # Sort by vote count for better quality
                    backdrops.sort(key=lambda x: x.get('vote_count', 0), reverse=True)
                    
                    backdrop_path = backdrops[0].get('file_path')
                    main_backdrop_path = backdrops[1].get('file_path') if len(backdrops) > 1 else backdrop_path
                    
                    backdrop_url = f"{TMDB_IMAGE_BASE_URL}/w780{backdrop_path}" if backdrop_path else None
                    main_backdrop_url = f"{TMDB_IMAGE_BASE_URL}/original{main_backdrop_path}" if main_backdrop_path else None
                
                # Use poster as fallback for backdrop if needed
                if poster_url and (not backdrop_url or not main_backdrop_url):
                    if not backdrop_url:
                        backdrop_url = poster_url
                    if not main_backdrop_url:
                        main_backdrop_url = poster_url
                    _LOGGER.debug("Using poster as backdrop fallback for %s", tmdb_id)

                _LOGGER.debug("Image URLs for %s: poster=%s, backdrop=%s, main_backdrop=%s", 
                            tmdb_id, poster_url is not None, backdrop_url is not None, main_backdrop_url is not None)

                result = (poster_url, backdrop_url, main_backdrop_url)
                self._cache[cache_key] = result
                return result
            
            return None, None, None
            
        except Exception as err:
            _LOGGER.error("Error getting TMDB images for %s: %s", tmdb_id, err)
            return None, None, None

    async def _search_tmdb(self, title, year=None, media_type='movie'):
        """Search for a title on TMDB."""
        if not title:
            return None
            
        try:
            cache_key = f"search_{media_type}_{title}_{year}_{self._language}"
            if cache_key in self._cache:
                return self._cache[cache_key]

            params = {
                "query": title,
                "language": self._language
            }
            if year:
                params["year"] = year
            
            endpoint = f"search/{media_type}"
            results = await self._fetch_tmdb_data(endpoint, params)
            
            if results and results.get("results"):
                tmdb_id = results["results"][0]["id"]
                self._cache[cache_key] = tmdb_id
                return tmdb_id
            
            return None
            
        except Exception as err:
            _LOGGER.error("Error searching TMDB for %s: %s", title, err)
            return None

    async def _get_tmdb_details(self, tmdb_id, media_type):
        """Fetch title and overview from TMDB."""
        try:
            if not tmdb_id:
                return None
                
            cache_key = f"details_{media_type}_{tmdb_id}_{self._language}"
            if cache_key in self._cache:
                return self._cache[cache_key]

            params = {"language": self._language}
            endpoint = f"{media_type}/{tmdb_id}"
            data = await self._fetch_tmdb_data(endpoint, params)
            
            if data:
                details = {
                    'title': data.get('title' if media_type == 'movie' else 'name', 'Unknown'),
                    'overview': data.get('overview', 'No description available.'),
                    'year': data.get('release_date' if media_type == 'movie' else 'first_air_date', '')[:4]
                }
                self._cache[cache_key] = details
                return details
                
            return None
        except Exception as err:
            _LOGGER.error("Error fetching TMDB details for %s: %s", tmdb_id, err)
            return None

    @abstractmethod
    async def async_update(self):
        """Update sensor state."""
        pass