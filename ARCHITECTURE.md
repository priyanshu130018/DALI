# DALI Voice Assistant Architecture

## Module Structure

- `main.py`: Application orchestration, initialization, wake-word loop, mode switching
- `services/`: External service integrations
  - `sarvam_service.py`: Wrapper over Sarvam chat/STT/TTS APIs
- `database/`: Persistence layer
  - `db_manager.py`: SQLite default with optional MySQL using env
- `utils/`: Configuration and helpers
  - `config.py`: Load and validate configuration and environment
- `models/`: Data models
  - `conversation.py`: Conversation dataclass
- `agents/`: Real-time agents
  - `realtime.py`: Async weather/news agent with caching and retries
- `offline/`: Offline components (Vosk, Rasa, PyTTSx3, wake word)
- `online/`: Existing Sarvam connector and network utilities

## Dependency Graph

- `main.py` → `utils.config`, `services.sarvam_service`, `agents.realtime`, `database.db_manager`, `offline.*`, `online.network_utils`
- `services.sarvam_service` → `online.cloud_connector`
- `agents.realtime` → `online.network_utils`, `requests`
- `database.db_manager` → `sqlite3` or `mysql.connector`
- `utils.config` → `dotenv`, `config.json`

## Data Flow

1. `main.py` loads config and validates environment via `utils.config`
2. On wake word, it captures audio and transcribes via Vosk or Sarvam (depending on online availability)
3. Commands are processed locally (time/date, weather/news via `agents.realtime`, app launch) or sent to Sarvam LLM via `services.sarvam_service`
4. Responses are spoken via PyTTSx3 or Sarvam TTS and logged in `database.db_manager`

## Environment Requirements

- `.env` supports:
  - `SARVAM_API_KEY` for online mode
  - `PICOVOICE_ACCESS_KEY` for wake word
  - `MYSQL_HOST`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB` for MySQL (optional)
  - `NEWSAPI_KEY` for headlines (optional)