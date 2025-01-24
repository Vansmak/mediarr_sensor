Support This Project If you find this project helpful, please consider supporting it. Your contributions help maintain and improve the project. Any support is greatly appreciated! ❤️ https://buymeacoffee.com/vansmak Thank you for your support!


# Mediarr for Home Assistant (inspired by upcoming media card)

A comprehensive media management card and integration for Home Assistant that brings together your media servers, management tools, and discovery services in one place.

## Features

- **Media Server Integration**
  - Plex: View recently added content
  - Coming Soon: Jellyfin and Emby support

- **Media Management**
  - Sonarr: View upcoming TV shows and episodes
  - Radarr: Track upcoming movie releases

- **Media Discovery**
  - Trakt: Browse popular TV shows and movies
  - TMDB: Explore trending content (configurable for TV, movies, or both)

## Screenshots


![VIEW](https://github.com/user-attachments/assets/e5eda74d-e50b-4dde-9985-45282dc99a51)


![Screenshot 2025-01-21 at 14-51-50 mediarr – Home Assistant](https://github.com/user-attachments/assets/4c73b44a-680a-42ea-8d2b-0d96806fb1c6)

## Installation

### HACS Installation
1. Open HACS
2. Go to "Integrations"
3. Click the three dots menu and select "Custom repositories"
4. Add this repository URL and select "Integration" as the category
5. Click "Add"
6. Find and install "Mediarr" from HACS
7. Restart Home Assistant
8. Add to Resources:
   - Go to Settings -> Dashboards -> Resources
   - Click "Add Resource"
   - Enter URL: `/hacsfiles/ha-mediarr/mediarr-card.js`
   - Select "JavaScript Module"
   - Click "Create"


### Manual Installation
1. Download the latest release
2. Copy all contents from `custom_components/mediarr/` to `/config/custom_components/mediarr/`
3. Copy `www/community/mediarr-card/mediarr-card.js` to `/config/www/community/mediarr-card/`
4. Restart Home Assistant

## Configuration

### Step 1: Configure Sensors
Add one or more of the following sensors to your `configuration.yaml`:

```yaml
sensor:
  - platform: mediarr
    plex:  # Optional
      host: localhost
      port: 32400
      token: your_plex_token
      max_items: 10
    
    sonarr:  # Optional
      url: http://localhost:8989
      api_key: your_sonarr_api_key
      max_items: 10
      days_to_check: 60
    
    radarr:  # Optional
      url: http://localhost:7878
      api_key: your_radarr_api_key
      max_items: 10

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
```
### Step 2: Add to Resources
1. Go to Settings -> Dashboards -> Resources
2. Click "Add Resource"
3. Enter URL: `/hacsfiles/ha-mediarr/mediarr-card.js`
4. Select "JavaScript Module"
5. Click "Create"
   
### Step 3: Add the Card
Add the card to your dashboard:  (may need to clear cache)

```yaml
type: custom:mediarr-card
plex_entity: sensor.plex_mediarr
sonarr_entity: sensor.sonarr_mediarr
radarr_entity: sensor.radarr_mediarr
trakt_entity: sensor.trakt_mediarr
tmdb_entity: sensor.tmdb_mediarr
media_player_entity: media_player.your_plex_player  # Optional
```

## Options

### Sensor Configuration
- **max_items**: Number of items to display (default: 10)
- **days_to_check**: Days to look ahead for upcoming content (Sonarr only, default: 60)
- **trending_type**: Content type to display for Trakt and TMDB

### Card Configuration
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

## Upcoming Features

- Jellyfin and Emby support
- Direct Plex playback functionality
- Library status indicators for Trakt/TMDB content
- Integration with Sonarr/Radarr for direct addition of new content

## Contributors
Vansmak aka Vanhacked

## License
MIT
