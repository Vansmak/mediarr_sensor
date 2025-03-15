"""Plex integration for Mediarr using TMDB images."""
import logging
import xml.etree.ElementTree as ET
import aiohttp
import re
import async_timeout
import voluptuous as vol
import aiofiles
from pathlib import Path
from datetime import datetime
from homeassistant.const import CONF_TOKEN, CONF_URL
import homeassistant.helpers.config_validation as cv
from ..common.const import CONF_MAX_ITEMS, DEFAULT_MAX_ITEMS
from ..common.tmdb_sensor import TMDBMediaSensor
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

PLEX_SCHEMA = {
    vol.Required(CONF_TOKEN): cv.string,
    vol.Required('tmdb_api_key'): cv.string,
    vol.Required(CONF_URL): cv.url,
    vol.Optional(CONF_MAX_ITEMS, default=DEFAULT_MAX_ITEMS): cv.positive_int,
    vol.Optional('language', default='en'): cv.string,  # Language parameter
}

class PlexMediarrSensor(TMDBMediaSensor):
    """Representation of a Plex recently added sensor using TMDB images."""

    def __init__(self, hass, session, config, sections):
        """Initialize the sensor."""
        super().__init__(session, config['tmdb_api_key'], config.get('language', 'en'))
        self.hass = hass  # Add hass reference
        self._base_url = config[CONF_URL].rstrip('/')
        self._token = config[CONF_TOKEN]
        self._max_items = config[CONF_MAX_ITEMS]
        self._name = "Plex Mediarr"
        self._sections = sections
        self._session = session
        self._state = 0
        self._attributes = {'data': []}
        self._available = True
        self._current_item_ids = set()  # For tracking current items

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID for the sensor."""
        return "plex_mediarr"

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes
    
    async def _enhanced_tmdb_search(self, title, year=None, media_type='movie'):
        """Enhanced TMDB search with multiple strategies."""
        
        
        # Try exact match first
        tmdb_id = await self._search_tmdb(title, year, media_type)
        if tmdb_id:
            return tmdb_id
            
        # Try without year suffix in title
        title_no_year = re.sub(r'\s*\(\d{4}\)\s*$', '', title).strip()
        if title_no_year != title:
            tmdb_id = await self._search_tmdb(title_no_year, year, media_type)
            if tmdb_id:
                return tmdb_id
        
        # Try removing any text in parentheses
        title_no_parens = re.sub(r'\s*\([^)]*\)\s*', ' ', title).strip()
        if title_no_parens != title and title_no_parens != title_no_year:
            tmdb_id = await self._search_tmdb(title_no_parens, year, media_type)
            if tmdb_id:
                return tmdb_id
        
        # Try first part of title (before colon)
        if ':' in title:
            first_part = title.split(':', 1)[0].strip()
            if len(first_part) > 3:  # Avoid too short titles
                tmdb_id = await self._search_tmdb(first_part, year, media_type)
                if tmdb_id:
                    return tmdb_id
        
        return None

    def _format_added_date(self, timestamp):
        """Format the added date from Unix timestamp."""
        try:
            if timestamp:
                dt = datetime.fromtimestamp(int(timestamp))
                return dt.strftime("%Y-%m-%d")
        except Exception as err:
            _LOGGER.error("Error formatting date: %s", err)
        return ""

    async def _fetch_recently_added(self, section_id):
        """Fetch recently added items from a Plex section."""
        url = f"{self._base_url}/library/sections/{section_id}/recentlyAdded"
        headers = {"X-Plex-Token": self._token}
        try:
            async with async_timeout.timeout(10):
                async with self._session.get(url, headers=headers) as response:
                    if response.status == 200:
                        xml_content = await response.text()
                        tree = ET.fromstring(xml_content)
                        videos = tree.findall(".//Video")
                        _LOGGER.debug("Found %d items in Plex section %s", len(videos), section_id)
                        return tree
                    else:
                        raise Exception(f"Failed to fetch recently added: {response.status}")
        except Exception as err:
            _LOGGER.error("Error fetching recently added: %s", err)
            return None
    async def _download_and_cache_image(self, url, item_id, image_type):
        """Download and cache an image from Plex."""
        try:
            headers = {"X-Plex-Token": self._token}
            
            async with async_timeout.timeout(10):
                async with self._session.get(url, headers=headers) as response:
                    if response.status == 200:
                        cache_dir = Path(self.hass.config.path("www/mediarr/cache"))
                        cache_dir.mkdir(parents=True, exist_ok=True)
                        
                        file_name = f"plex_{item_id}_{image_type}.jpg"
                        cached_path = cache_dir / file_name
                        
                        content = await response.read()
                        
                        # Use aiofiles for async file operations
                        async with aiofiles.open(cached_path, 'wb') as f:
                            await f.write(content)
                            
                        _LOGGER.debug("Successfully cached image for %s: %s", item_id, image_type)
                        return f"/local/mediarr/cache/{file_name}"
                    else:
                        _LOGGER.warning("Failed to download image %s for %s: %s", image_type, item_id, response.status)
            return None
        except Exception as err:
            _LOGGER.error("Error caching image %s for %s: %s", image_type, item_id, err)
            return None
        
    def _clean_unused_images(self, current_ids):
        """Clean up cached images that aren't in the current item list."""
        try:
            cache_dir = Path(self.hass.config.path("www/mediarr/cache"))
            if not cache_dir.exists():
                return

            for image_file in cache_dir.glob("plex_*.jpg"):
                item_id = image_file.stem.split('_')[1]
                if item_id not in current_ids:
                    try:
                        image_file.unlink()
                        _LOGGER.debug("Removed unused image: %s", image_file.name)
                    except Exception as err:
                        _LOGGER.error("Error removing image %s: %s", image_file.name, err)
        except Exception as err:
            _LOGGER.error("Error cleaning cached images: %s", err)

    async def _get_plex_images(self, item, item_id, is_show=False):
        """Get and cache images from Plex."""
        try:
            if is_show:
                thumb = item.get('grandparentThumb')
                art = item.get('grandparentArt')
            else:
                thumb = item.get('thumb')
                art = item.get('art')
                
            poster_url = backdrop_url = main_backdrop_url = None
            
            if thumb:
                full_thumb_url = f"{self._base_url}{thumb}?X-Plex-Token={self._token}"
                poster_url = await self._download_and_cache_image(full_thumb_url, item_id, "poster")
            
            if art:
                full_art_url = f"{self._base_url}{art}?X-Plex-Token={self._token}"
                backdrop_url = await self._download_and_cache_image(full_art_url, item_id, "backdrop")
                main_backdrop_url = backdrop_url
            
            return poster_url, backdrop_url, main_backdrop_url
        except Exception as err:
            _LOGGER.error("Error getting Plex images: %s", err)
            return None, None, None

    async def _process_item(self, item):
        """Process a single Plex item and get TMDB images."""
        try:
            added_at = item.get('addedAt', '0')
            added_date = self._format_added_date(added_at)
            is_episode = item.get('type') == 'episode'
            item_id = item.get('ratingKey', '')  # Use Plex rating key as unique ID
            
            # Keep track of item IDs for cache cleaning
            if item_id:
                self._current_item_ids.add(item_id)
                
            # Default empty images to None for cleaner handling
            poster_url = backdrop_url = main_backdrop_url = None
            
            if is_episode:
                show_title = item.get('grandparentTitle', '')
                tmdb_id = None
                
                # Try to get TMDB ID from Guid tags
                guid_list = item.findall('.//Guid')
                for guid in guid_list:
                    guid_str = guid.get('id', '')
                    if 'themoviedb://' in guid_str:
                        tmdb_id = guid_str.split('themoviedb://')[1].split('?')[0]
                        break
                
                if not tmdb_id:
                    tmdb_id = await self._enhanced_tmdb_search(show_title, None, 'tv')
                
                # Try TMDB images first
                if tmdb_id:
                    try:
                        poster_url, backdrop_url, main_backdrop_url = await self._get_tmdb_images(tmdb_id, 'tv')
                    except Exception as err:
                        _LOGGER.error("Error getting TMDB images for %s: %s", show_title, err)
                
                # Fallback to Plex images if needed
                if not poster_url or not backdrop_url or not main_backdrop_url:
                    plex_poster, plex_backdrop, plex_main = await self._get_plex_images(item, item_id, is_show=True)
                    
                    # Only use Plex images for the ones that are missing
                    if not poster_url and plex_poster:
                        poster_url = plex_poster
                    if not backdrop_url and plex_backdrop:
                        backdrop_url = plex_backdrop
                    if not main_backdrop_url and plex_main:
                        main_backdrop_url = plex_main

                return {
                    'title': str(show_title)[:100],
                    'episode': str(item.get('title', ''))[:100],
                    'release': self._format_date(item.get('originallyAvailableAt', '')),
                    'added': added_date,
                    'number': f"S{int(item.get('parentIndex', 0)):02d}E{int(item.get('index', 0)):02d}",
                    'runtime': str(int(item.get('duration', 0)) // 60000),
                    'genres': ', '.join(str(genre.get('tag', '')) for genre in item.findall('.//Genre'))[:50],
                    'poster': str(poster_url or ""),
                    'fanart': str(main_backdrop_url or backdrop_url or ""),
                    'banner': str(backdrop_url or ""),
                    'flag': 1,
                    'added_at': added_at
                }
            else:
                title = str(item.get('title', ''))
                year = item.get('year')
                
                tmdb_id = None
                guid_list = item.findall('.//Guid')
                for guid in guid_list:
                    guid_str = guid.get('id', '')
                    if 'themoviedb://' in guid_str:
                        tmdb_id = guid_str.split('themoviedb://')[1].split('?')[0]
                        break

                if not tmdb_id:
                    tmdb_id = await self._enhanced_tmdb_search(title, year, 'movie')

                # Try TMDB images first
                if tmdb_id:
                    try:
                        poster_url, backdrop_url, main_backdrop_url = await self._get_tmdb_images(tmdb_id, 'movie')
                    except Exception as err:
                        _LOGGER.error("Error getting TMDB images for %s: %s", title, err)
                
                # Fallback to Plex images if needed
                if not poster_url or not backdrop_url or not main_backdrop_url:
                    plex_poster, plex_backdrop, plex_main = await self._get_plex_images(item, item_id)
                    
                    # Only use Plex images for the ones that are missing
                    if not poster_url and plex_poster:
                        poster_url = plex_poster
                    if not backdrop_url and plex_backdrop:
                        backdrop_url = plex_backdrop
                    if not main_backdrop_url and plex_main:
                        main_backdrop_url = plex_main

                summary = str(item.get('summary', 'N/A'))
                if len(summary) > 97:
                    summary = summary[:97] + '...'

                return {
                    'title': title[:100],
                    'episode': summary,
                    'release': self._format_date(item.get('originallyAvailableAt', '')),
                    'added': added_date,
                    'number': str(year or ''),
                    'runtime': str(int(item.get('duration', 0)) // 60000),
                    'genres': ', '.join(str(genre.get('tag', '')) for genre in item.findall('.//Genre'))[:50],
                    'poster': str(poster_url or ""),
                    'fanart': str(main_backdrop_url or backdrop_url or ""),
                    'banner': str(backdrop_url or ""),
                    'flag': 1,
                    'added_at': added_at
                }

        except Exception as err:
            _LOGGER.error("Error processing item %s: %s", item.get('title', 'Unknown'), err)
            return None

    async def async_update(self):
        """Update sensor data."""
        try:
            recently_added = []
            card_json = []
            show_episodes = {}
            self._current_item_ids = set()
            for section_id in self._sections:
                try:
                    data = await self._fetch_recently_added(section_id)
                    if data is not None:
                        for item in data.findall(".//Video"):
                            processed_item = await self._process_item(item)
                            if processed_item:
                                if processed_item.get('number', '').startswith('S'):
                                    show_title = processed_item['title']
                                    if show_title not in show_episodes:
                                        show_episodes[show_title] = {
                                            **processed_item,
                                            'episodes': [processed_item['number']],
                                            'added_at': processed_item['added_at']
                                        }
                                    else:
                                        show_episodes[show_title]['episodes'].append(processed_item['number'])
                                        if int(processed_item['added_at']) > int(show_episodes[show_title]['added_at']):
                                            show_episodes[show_title]['added_at'] = processed_item['added_at']
                                            show_episodes[show_title]['episode'] = processed_item['episode']
                                            show_episodes[show_title]['number'] = processed_item['number']
                                else:
                                    recently_added.append(processed_item)

                except Exception as section_err:
                    _LOGGER.error("Error updating section %s: %s", section_id, section_err)

            # Process grouped shows
            for show_data in show_episodes.values():
                episode_count = len(show_data['episodes'])
                if episode_count > 1:
                    show_data['episode'] = f"{episode_count} new episodes ({show_data['number']})"
                del show_data['episodes']
                recently_added.append(show_data)

            # Sort by added date
            recently_added.sort(key=lambda x: int(x.get('added_at', 0)), reverse=True)
            card_json.extend(recently_added[:self._max_items])

            if not card_json:
                card_json.append({
                    'title_default': '$title',
                    'line1_default': '$episode',
                    'line2_default': '$release',
                    'line3_default': '$number - $rating - $runtime',
                    'line4_default': '$genres',
                    'icon': 'mdi:eye-off'
                })

            self._state = len(recently_added)
            self._attributes = {'data': card_json}
            self._available = True
            self._clean_unused_images(self._current_item_ids)
        except Exception as err:
            _LOGGER.error("Error updating Plex sensor: %s", err)
            self._state = 0
            self._attributes = {'data': []}
            self._available = False

    @classmethod
    async def create_sensors(cls, hass, config):
        """Create a single Plex sensor for all sections."""
        try:
            base_url = config[CONF_URL].rstrip('/')
            token = config[CONF_TOKEN]

            # Fetch sections
            url = f"{base_url}/library/sections"
            headers = {"X-Plex-Token": token, "Accept": "application/xml"}
            
            async with aiohttp.ClientSession() as session:
                async with async_timeout.timeout(10):
                    async with session.get(url, headers=headers) as response:
                        if response.status != 200:
                            raise Exception(f"Error fetching library sections: {response.status}")
                        xml_content = await response.text()

            # Parse XML
            root = ET.fromstring(xml_content)
            sections = [directory.get("key") for directory in root.findall(".//Directory") 
                    if directory.get("key")]

            # Pass hass as the first argument
            return [cls(hass, async_get_clientsession(hass), config, sections)]

        except Exception as error:
            _LOGGER.error("Error initializing Plex sensors: %s", error)
            return []

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Plex sensor."""
    sensors = await PlexMediarrSensor.create_sensors(hass, config)
    async_add_entities(sensors, True)