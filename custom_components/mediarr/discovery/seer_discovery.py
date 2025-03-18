"""Jellyseerr/Overseerr discovery features for Mediarr."""
import logging
import asyncio
from datetime import datetime
from ..common.tmdb_sensor import TMDBMediaSensor
import async_timeout

_LOGGER = logging.getLogger(__name__)

# In seer_discovery.py
class SeerDiscoveryMediarrSensor(TMDBMediaSensor):
    """Seer sensor for discover/trending/popular."""
    
    def __init__(self, session, api_key, url, tmdb_api_key, max_items, content_type, media_type=None, filters=None):
        """Initialize the sensor."""
        # Initialize TMDBMediaSensor with tmdb_api_key
        super().__init__(session, tmdb_api_key)
        
        self._seer_api_key = api_key
        self._url = url.rstrip('/')
        self._max_items = max_items
        self._content_type = content_type
        self._media_type = media_type
        
        # Initialize default filters
        self._filters = {
            'language': 'en',
            'min_year': 0,
            'exclude_talk_shows': True,
            'exclude_genres': [10763, 10764, 10767],  # News, Reality, Talk shows
            'exclude_non_english': True
        }
        
        # Update with user-provided filters
        if filters:
            self._filters.update(filters)
        
        # Customize name based on content type and media type
        if content_type in ["popular_movies", "popular_tv"]:
            self._name = f"Seer Mediarr Popular {'Movies' if media_type == 'movies' else 'TV'}"
        else:
            self._name = f"Seer Mediarr {content_type.title()}"
            
    def should_include_item(self, item, media_type):
        """Apply filters to determine if an item should be included."""
        # Skip if no item
        if not item:
            return False
           
        # Filter by year
        year = None
        if media_type == 'tv' and item.get('first_air_date'):
            try:
                year = int(item['first_air_date'].split('-')[0])
            except (ValueError, IndexError, TypeError):
                pass
        elif media_type == 'movie' and item.get('release_date'):
            try:
                year = int(item['release_date'].split('-')[0])
            except (ValueError, IndexError, TypeError):
                pass
               
        if year and year < self._filters.get('min_year', 0):
            return False
            
        # Filter by language
        if self._filters.get('exclude_non_english', True) and item.get('original_language') != 'en':
            return False
            
        # Filter by genre
        excluded_genres = self._filters.get('exclude_genres', [])
        if excluded_genres and any(genre_id in excluded_genres for genre_id in item.get('genre_ids', [])):
            return False
            
        # Filter for TV talk shows
        if media_type == 'tv' and self._filters.get('exclude_talk_shows', True):
            title = item.get('name', '') or item.get('title', '')
            if self.is_talk_show(title):
                return False
                
        return True
       
    def is_talk_show(self, title):
        """Check if a show title appears to be a talk show or similar format."""
        if not self._filters.get('exclude_talk_shows', True) or not title:
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

    async def _fetch_media_list(self, media_type=None):
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
                # Use provided media_type or default to movies
                media_type = media_type or "movies"
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
    async def _fetch_all_requests(self):
        """Fetch all current requests from Overseerr/Jellyseerr."""
        try:
            url = f"{self._url}/api/v1/request"
            headers = {"X-Api-Key": self._seer_api_key}
            params = {"take": 100, "skip": 0}  # Adjust take value as needed
            all_requests = set()

            async with async_timeout.timeout(10):
                async with self._session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('results'):
                            for request in data['results']:
                                if request.get('media'):
                                    tmdb_id = request['media'].get('tmdbId')
                                    if tmdb_id:
                                        all_requests.add(str(tmdb_id))
            
            return all_requests
        except Exception as err:
            _LOGGER.error("Error fetching all requests: %s", err)
            return set()

    async def _process_media_items(self, data, media_type, requested_ids):
        """Process media items in parallel with filtering."""
        if not data or not data.get('results'):
            _LOGGER.debug("No data or results to process for %s", media_type)
            return []

        filtered_count = 0
        requested_count = 0
        detail_failure_count = 0
        success_count = 0
        
        async def process_item(item):
            nonlocal filtered_count, requested_count, detail_failure_count, success_count
            
            try:
                tmdb_id = str(item.get('id'))
                if not tmdb_id:
                    _LOGGER.debug("Item has no TMDB ID")
                    return None
                    
                if tmdb_id in requested_ids:
                    requested_count += 1
                    _LOGGER.debug("Item %s already requested, skipping", tmdb_id)
                    return None
                
                # Apply filters
                if not self.should_include_item(item, media_type):
                    filtered_count += 1
                    _LOGGER.debug("Item %s filtered out by criteria", tmdb_id)
                    return None

                details = await self._get_tmdb_details(tmdb_id, media_type)
                if not details:
                    detail_failure_count += 1
                    _LOGGER.debug("Failed to get TMDB details for %s", tmdb_id)
                    return None

                poster_url, backdrop_url, main_backdrop_url = await self._get_tmdb_images(tmdb_id, media_type)
                
                success_count += 1
                return {
                    'title': details['title'],
                    'overview': details['overview'][:100] + '...' if details.get('overview') else 'No overview available',
                    'year': details['year'],
                    'poster': str(poster_url or ""),
                    'fanart': str(main_backdrop_url or backdrop_url or ""),
                    'banner': str(backdrop_url or ""),
                    'release': details['year'],
                    'type': 'Movie' if media_type == 'movie' else 'TV Show',
                    'flag': 1,
                    'id': tmdb_id
                }
            except Exception as err:
                _LOGGER.error("Error processing item %s: %s", tmdb_id if 'tmdb_id' in locals() else 'unknown', err)
                return None

        # Process items in parallel
        _LOGGER.debug("Processing %d items for %s", len(data['results']), media_type)
        tasks = [process_item(item) for item in data['results']]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        exceptions = [r for r in results if isinstance(r, Exception)]
        if exceptions:
            _LOGGER.error("Got %d exceptions during processing", len(exceptions))
            for exc in exceptions[:3]:  # Log first 3 exceptions
                _LOGGER.error("Exception: %s", exc)
        
        # Filter out None values and exceptions
        processed_results = [item for item in results if item is not None and not isinstance(item, Exception)]
        
        _LOGGER.debug("Processing summary for %s: %d items total, %d already requested, %d filtered out, "
                    "%d failed to get details, %d successful", 
                    media_type, len(data['results']), requested_count, filtered_count, 
                    detail_failure_count, success_count)
        
        return processed_results

    async def async_update(self):
        """Update the sensor."""
        try:
            # Fetch all current requests first
            requested_ids = await self._fetch_all_requests()
            _LOGGER.debug("Fetched %d requested IDs from Seer", len(requested_ids))
            
            all_items = []
            
            if self._content_type == "discover":
                # Fetch both movies and TV
                for media_type in ['movies', 'tv']:
                    _LOGGER.debug("Fetching %s data from Seer for discover", media_type)
                    data = await self._fetch_media_list(media_type)
                    
                    if data and 'results' in data:
                        _LOGGER.debug("Received %d %s items from Seer", len(data['results']), media_type)
                        # Debug the first item to see its structure
                        if data['results']:
                            _LOGGER.debug("Sample item structure: %s", data['results'][0])
                    else:
                        _LOGGER.debug("No %s data or no results received from Seer", media_type)
                    
                    _LOGGER.debug("Processing %s items through filters", media_type)
                    processed_items = await self._process_media_items(
                        data,
                        'movie' if media_type == 'movies' else 'tv',
                        requested_ids
                    )
                    _LOGGER.debug("After filtering: %d %s items remaining", len(processed_items), media_type)
                    all_items.extend(processed_items)
            else:
                # Fetch single type (trending, popular movies, or popular TV)
                _LOGGER.debug("Fetching %s data from Seer", self._content_type)
                data = await self._fetch_media_list()
                
                if data and 'results' in data:
                    _LOGGER.debug("Received %d items from Seer for %s", len(data['results']), self._content_type)
                    # Debug the first item to see its structure
                    if data['results']:
                        _LOGGER.debug("Sample item structure: %s", data['results'][0])
                else:
                    _LOGGER.debug("No data or no results received from Seer for %s", self._content_type)
                
                media_type = 'movie' if self._content_type == 'popular_movies' else 'tv'
                _LOGGER.debug("Processing %s items through filters", self._content_type)
                processed_items = await self._process_media_items(data, media_type, requested_ids)
                _LOGGER.debug("After filtering: %d items remaining", len(processed_items))
                all_items.extend(processed_items)

            # Ensure max_items limit is respected
            all_items = all_items[:self._max_items]
            _LOGGER.debug("Final number of items after max_items limit: %d", len(all_items))

            if not all_items:
                _LOGGER.warning("No items passed filters for %s, using fallback", self._content_type)
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
