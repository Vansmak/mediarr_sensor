Support This Project If you find this project helpful, please consider supporting it. Your contributions help maintain and improve the project. Any support is greatly appreciated! ❤️ https://buymeacoffee.com/vansmak Thank you for your support!


# Mediarr for Home Assistant (inspired by upcoming media card) https://github.com/Vansmak/mediarr-card
## Services
This integration provides services to interact with Overseerr/Jellyseerr. While the various trending/discover sensors and frontend card are optional, the base seer sensor is required to enable the services.

### Minimum Required Configuration just to have overseer\jellyseer request services from ha
To use the seer request services, add this to your configuration.yaml:

```yaml
mediarr:
  seer:
    url: your_seerr_url
    api_key: !secret seer_api_key
```
and for sensors:
```yaml
sensor:
  - platform: mediarr
    seer:
      url: your_seerr_url
      api_key: your_api_key
```      

## Installation

### HACS Installation
1. Open HACS
2. Go to "Integrations"
3. Click the three dots menu and select "Custom repositories"
4. Add this repository URL and select "Integration" as the category
5. Click "Add"
6. Find and install "Mediarr" from HACS
7. Restart Home Assistant


### Manual Installation
1. Download the latest  before hacs (can break)
2. Copy all contents from `custom_components/mediarr/` to `/config/custom_components/mediarr/`
   
4. Restart Home Assistant

## Configuration

### Step 1: Configure Sensors
Add one or more of the following sensors to your `configuration.yaml, sensors`:
## New addition, added more seer sensors
```yaml
sensor:
  - platform: mediarr
    seer: 
      url: localhost
      api_key: your_api_key
      max_items: 10
      tmdb_api_key: "your_tmdb_api_key" 
      trending: true # Optional     
      discover: true  # Optional
      popular_movies: true  # Optional
      popular_tv: true # Optional

    plex:  # Optional
      url: Plex url
      token: your_token
      max_items: 10
      tmdb_api_key: "your_tmdb_api_key"

    jellyfin:  # Optional
      url: jellyfin url
      token: your_api_key 
      max_items: 10
      tmdb_api_key: "your_tmdb_api_key"

    sonarr:  # Optional
      url: http://localhost:8989
      api_key: your_sonarr_api_key
      max_items: 10
      days_to_check: 60
     

    radarr:  # Optional
      url: http://localhost:7878
      api_key: your_radarr_api_key
      max_items: 10
      days_to_check: 60 #breaking change
      
    
    trakt:  # Optional
      client_id: "your_client_id"
      client_secret: "your_client_secret"
      tmdb_api_key: "your_tmdb_api_key"  # Required for posters
      trending_type: both  # Options: movies, shows, both
      max_items: 10
     
    
    tmdb:  # Optional
      api_key: "your_api_key"
      trending_type: all  # Options: movie, tv, all
      max_items: 10
      trending: true          # Default endpoint
      now_playing: true       # Optional
      upcoming: true          # Optional
      on_air: true            # Optional
      airing_today: false     # Optional
```
# Sensor Configuration
- **max_items**: Number of items to display (default: 10)
- **days_to_check**: Days to look ahead for upcoming content (Sonarr only, default: 60)
- **trending_type**: Content type to display for Trakt and TMDB

### Step 3: if you want a front-end, install Mediarr-card from https://github.com/Vansmak/mediarr-card
Add the Card

# Card Configuration
- All entity configurations are optional - use only what you need
- Media player entity enables playback control (coming soon)

## Getting API Keys

### Plex
1. Get your Plex token from your Plex account settings
2. More details at [Plex Support](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)

### Sonarr/Radarr
1. Go to Settings -> General
2. Copy your API key

### Trakt
1. Create an application at [Trakt API](https://trakt.tv/oauth/applications)
2. Get your client ID and secret

### TMDB
1. Create an account at [TMDB](https://www.themoviedb.org/)
2. Request an API key from your account settings

### Overseer\Jellyseer
1. Go to Settings -> General
2. Copy your API key
   
## Upcoming Features

## Contributors
Vansmak aka Vanhacked
FNXPT

## License
MIT
