# mediarr/discovery/tmdb.py
"""TMDB integration for Mediarr."""
import time
import logging
from ..common.sensor import MediarrSensor

_LOGGER = logging.getLogger(__name__)

TMDB_ENDPOINTS = {
    'trending': 'trending/all/week',
    'now_playing': 'movie/now_playing',
    'upcoming': 'movie/upcoming',
    'on_air': 'tv/on_the_air',
    'airing_today': 'tv/airing_today',
    'popular_movies': 'movie/popular',
    'popular_tv': 'tv/popular'
}

class TMDBMediarrSensor(MediarrSensor):
    def __init__(self, session, api_key, max_items, endpoint='trending', filters=None):
        super().__init__()
        
        self._session = session
        self._api_key = api_key
        self._max_items = max_items
        self._endpoint = endpoint
        self._name = f"TMDB Mediarr {endpoint.replace('_', ' ').title()}"
        
        self._filters = {
            'language': 'en',
            'min_year': 0,
            'exclude_talk_shows': True,
            'exclude_genres': [10763, 10764, 10767],
            'exclude_non_english': True,
            'hide_existing': True
        }
        
        if filters:
            self._filters.update(filters)
        
        self._library_tmdb_ids = set()
        self._library_titles = set()
        self._last_library_fetch = 0    

    @property
    def name(self):
        return self._name
        
    @property
    def unique_id(self):
        return f"tmdb_mediarr_{self._endpoint}"
        
    def should_include_item(self, item, media_type):
		    """Apply filters to determine if an item should be included."""
		    # Skip if no item
		    if not item:
		        return False
		    
		    # Get item basics
		    item_id = item.get('id')
		    title = item.get('title') if media_type == 'movie' else item.get('name', '')
		    
		    # Check if item exists in any library sensor
		    if self._filters.get('hide_existing', True):
		        for entity_id in self.hass.states.async_entity_ids('sensor'):
		            if any(source in entity_id for source in ['plex_mediarr', 'jellyfin_mediarr', 'sonarr_mediarr', 'radarr_mediarr']):
		                entity = self.hass.states.get(entity_id)
		                if entity and entity.attributes.get('data'):
		                    # Check if TMDB ID matches
		                    if str(item_id) in [str(lib_item.get('tmdb_id')) for lib_item in entity.attributes['data']]:
		                        _LOGGER.debug(f"Item {title} (ID: {item_id}) already exists in library")
		                        return False
		                    
		                    # More flexible title matching
		                    for lib_item in entity.attributes['data']:
		                        lib_title = lib_item.get('title') or lib_item.get('name') or ''
		                        # Remove episode details and extra info
		                        clean_lib_title = lib_title.split(' - ')[0].split(' (')[0]
		                        clean_tmdb_title = title.split(' - ')[0].split(' (')[0]
		                        
		                        if clean_lib_title.lower() == clean_tmdb_title.lower():
		                            _LOGGER.debug(f"Item {title} already exists in library (matched as {clean_lib_title})")
		                            return False
		    
		    # Existing filtering logic
		    lang = item.get('original_language', 'unknown')
		    
		    # Filter by year
		    year = None
		    if media_type == 'tv' and item.get('first_air_date'):
		        try:
		            year = int(item['first_air_date'].split('-')[0])
		            if year < self._filters.get('min_year', 0):
		                _LOGGER.debug(f"Item {title} rejected: year {year} < min_year {self._filters.get('min_year', 0)}")
		                return False
		        except (ValueError, IndexError, TypeError):
		            pass
		    elif media_type == 'movie' and item.get('release_date'):
		        try:
		            year = int(item['release_date'].split('-')[0])
		            if year < self._filters.get('min_year', 0):
		                _LOGGER.debug(f"Item {title} rejected: year {year} < min_year {self._filters.get('min_year', 0)}")
		                return False
		        except (ValueError, IndexError, TypeError):
		            pass
		
		    # Filter by language
		    if self._filters.get('exclude_non_english', True) and lang != 'en':
		        _LOGGER.debug(f"Item {title} rejected: language {lang} is not English")
		        return False
		
		    # Filter by genre
		    excluded_genres = self._filters.get('exclude_genres', [])
		    if excluded_genres and any(genre_id in excluded_genres for genre_id in item.get('genre_ids', [])):
		        _LOGGER.debug(f"Item {title} rejected: genre in excluded list {item.get('genre_ids', [])}")
		        return False
		
		    # Filter for TV talk shows
		    if media_type == 'tv' and self._filters.get('exclude_talk_shows', True):
		        if self.is_talk_show(title):
		            _LOGGER.debug(f"Item {title} rejected: identified as talk show")
		            return False
		
		    return True
		    
    async def _fetch_media_libraries(self, hass):
        tmdb_ids = set()
        
        try:
            for entity_id in hass.states.async_entity_ids('sensor'):
                if 'plex_mediarr' in entity_id or 'jellyfin_mediarr' in entity_id:
                    entity = hass.states.get(entity_id)
                    if entity and entity.attributes.get('data'):
                        for item in entity.attributes['data']:
                            if item.get('tmdb_id'):
                                tmdb_ids.add(str(item['tmdb_id']))
                
                elif 'radarr_mediarr' in entity_id:
                    entity = hass.states.get(entity_id)
                    if entity and entity.attributes.get('data'):
                        for item in entity.attributes['data']:
                            if item.get('tmdb_id'):
                                tmdb_ids.add(str(item['tmdb_id']))
                
                elif 'sonarr_mediarr' in entity_id:
                    entity = hass.states.get(entity_id)
                    if entity and entity.attributes.get('data'):
                        for item in entity.attributes['data']:
                            if item.get('tmdb_id'):
                                tmdb_ids.add(str(item['tmdb_id']))
            
            _LOGGER.debug(f"Found {len(tmdb_ids)} media items in libraries")
            return tmdb_ids
            
        except Exception as e:
            _LOGGER.error(f"Error fetching media libraries: {e}")
            return set()  
        
    def is_talk_show(self, title):
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
    
    def _get_media_type(self, item):
        if self._endpoint in ['now_playing', 'upcoming', 'popular_movies']:
            return 'movie'
        elif self._endpoint in ['on_air', 'airing_today', 'popular_tv']:
            return 'tv'
        return item.get('media_type', 'movie')
    
    async def async_update(self):
        try:
            hass = self.hass if hasattr(self, 'hass') else None
            
            current_time = time.time()
            if hass and hasattr(self, '_last_library_fetch'):
                if current_time - self._last_library_fetch > 3600 and self._filters.get('hide_existing', True):
                    self._library_tmdb_ids = await self._fetch_media_libraries(hass)
                    self._last_library_fetch = current_time
            else:
                self._last_library_fetch = 0
                if hass and self._filters.get('hide_existing', True):
                    self._library_tmdb_ids = await self._fetch_media_libraries(hass)
                    self._last_library_fetch = current_time
            
            headers = {
                'Authorization': f'Bearer {self._api_key}',
                'accept': 'application/json'
            }
            
            results = []
            
            if self._endpoint == 'popular_tv':
                endpoints = ['tv/popular', 'trending/tv/week', 'tv/top_rated']
                
                for endpoint in endpoints:
                    for page in range(1, 3):
                        params = {'language': self._filters.get('language', 'en-US'), 'page': page}
                        
                        _LOGGER.debug(f"Fetching TV data from endpoint: {endpoint}, page: {page}")
                        
                        async with self._session.get(
                            f"https://api.themoviedb.org/3/{endpoint}",
                            headers=headers,
                            params=params
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                if 'results' in data:
                                    for item in data.get('results', []):
                                        if not self.should_include_item(item, 'tv'):
                                            continue
                                        
                                        title = item.get('name', '')
                                        
                                        results.append({
                                            'title': title,
                                            'type': 'show',
                                            'year': self._get_year(item, 'tv'),
                                            'overview': item.get('overview', ''),
                                            'poster': f"https://image.tmdb.org/t/p/w500{item.get('poster_path')}" if item.get('poster_path') else None,
                                            'backdrop': f"https://image.tmdb.org/t/p/original{item.get('backdrop_path')}" if item.get('backdrop_path') else None,
                                            'tmdb_id': item.get('id'),
                                            'popularity': item.get('popularity'),
                                            'vote_average': item.get('vote_average')
                                        })
            else:
                params = {'language': self._filters.get('language', 'en-US')}
                endpoint_url = TMDB_ENDPOINTS.get(self._endpoint, TMDB_ENDPOINTS['trending'])
                
                async with self._session.get(
                    f"https://api.themoviedb.org/3/{endpoint_url}",
                    headers=headers,
                    params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'results' in data:
                            for item in data.get('results', []):
                                media_type = self._get_media_type(item)
                                
                                if media_type not in ['movie', 'tv']:
                                    continue
                                    
                                if not self.should_include_item(item, media_type):
                                    continue
                                
                                title = item.get('title') if media_type == 'movie' else item.get('name')
                                
                                results.append({
                                    'title': title,
                                    'type': 'movie' if media_type == 'movie' else 'show',
                                    'year': self._get_year(item, media_type),
                                    'overview': item.get('overview', ''),
                                    'poster': f"https://image.tmdb.org/t/p/w500{item.get('poster_path')}" if item.get('poster_path') else None,
                                    'backdrop': f"https://image.tmdb.org/t/p/original{item.get('backdrop_path')}" if item.get('backdrop_path') else None,
                                    'tmdb_id': item.get('id'),
                                    'popularity': item.get('popularity'),
                                    'vote_average': item.get('vote_average')
                                })
                    else:
                        raise Exception(f"Failed to fetch TMDB {self._endpoint}. Status: {response.status}")
            
            unique_results = []
            seen_ids = set()
            for item in results:
                if item['tmdb_id'] not in seen_ids:
                    seen_ids.add(item['tmdb_id'])
                    unique_results.append(item)
            
            _LOGGER.debug(f"Found {len(unique_results)} items for {self._endpoint} after filtering")
            
            filtered_results = [item for item in unique_results if item['tmdb_id'] != 137228]
            
            self._state = len(filtered_results)
            self._attributes = {'data': filtered_results[:self._max_items]}
            self._available = True

        except Exception as err:
            _LOGGER.error(f"Error updating TMDB sensor: {err}")
            self._state = 0
            self._attributes = {'data': []}
            self._available = False

    def _get_year(self, item, media_type):
        if media_type == 'movie':
            date = item.get('release_date', '')
        else:
            date = item.get('first_air_date', '')
        return date.split('-')[0] if date else ''