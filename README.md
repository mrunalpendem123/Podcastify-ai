# Create-to-Listen (Sarvam)

Creation-first conversational podcast generator for Indian languages.

## What’s Included
- `backend/`: FastAPI orchestration pipeline with staged adapters
- `ui/`: Creation-first React UI (drag-drop, progress, player)

## Quick Start (Dev)

### Backend
```bash
cd /Users/mrunalpendem/Documents/New\ project/sarvam/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# optional ML pipeline (CrewAI, Podcastfy)
pip install -r requirements-ml.txt
export SARVAM_API_KEY="your_key_here"
# optional (CrewAI / Claude)
export ANTHROPIC_API_KEY="your_key_here"
export CREWAI_ENABLED="true"
export CREWAI_MODEL="anthropic/claude-3-5-sonnet-20241022"
uvicorn app.main:app --reload
```

### UI
```bash
cd /Users/mrunalpendem/Documents/New\ project/sarvam/ui
npm install
npm run dev
```

## Notes
- The pipeline stages are stubbed but structured to swap in real adapters:
  - LlamaIndex (ingestion + summarization)
  - CrewAI (conversational rewrite)
  - Sarvam Bulbul V3 (TTS)
  - Podcastfy (assembly)
- Replace stage implementations in `backend/app/stages/` as you integrate each system.
- If dependency resolution is slow, install the core requirements first, then the ML requirements.
