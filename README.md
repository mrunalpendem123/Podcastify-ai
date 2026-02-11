
# Podcastify-AI (Sarvam Edition)

A powerful **Text-to-Podcast** generation engine specifically designed for **Indian languages**. It transforms articles, research papers, and documents into engaging, natural-sounding audio conversations.

## 🚀 Features

- **Multilingual Support:** Generate podcasts in **Hindi**, **Telugu**, **Tamil**, **English**, and **Hinglish (Gen Z)**.
- **Flexible LLM Providers:** Use **OpenAI GPT-4o** or **Google Gemini** for scripting.
- **Deep Understanding:** Deep Dive scripts are lengthened and more detailed for 10–15 minute episodes.
- **Natural Conversations:** Two-voice scripts are written in a conversational style (no “Host:” / “Guest:” callouts in the audio).
- **Hyper-Realistic Audio:** Powered by **Sarvam AI's `bulbul:v3`** model for lifelike Indian voices.
- **TTS-Friendly Output:** Acronyms and tech terms are normalized for better pronunciation (e.g., “SLMs”, “LLMs”).
- **Smart Ingestion:**
  - **URLs:** Uses **Jina Reader** to extract clean content from web pages.
  - **Files:** Supports PDF, DOCX, TXT via LlamaIndex.

## 🛠 Architecture

1.  **Ingestion:** Jina Reader (Web) / LlamaIndex (Files)
2.  **Orchestration & Scripting:** FastAPI + OpenAI GPT-4o or Google Gemini
3.  **TTS:** Sarvam AI (Bulbul V3)
4.  **Frontend:** React + Vite

## ⚡️ Quick Start

### 1. Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Configuration (`backend/.env`):**
Create a `.env` file in the `backend/` directory:
```env
SARVAM_API_KEY="your_sarvam_key"
OPENAI_API_KEY="your_openai_key"
GEMINI_API_KEY="your_gemini_key"
# Optional: ANTHROPIC_API_KEY if using Claude for other tasks
```

**Run Server:**
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 2. Frontend Setup

```bash
cd ui
npm install
npm run dev -- --host 127.0.0.1 --port 5174
```

Visit `http://127.0.0.1:5174` to start creating podcasts!

## 📝 Usage

1.  **Paste a URL** (e.g., a news article or research paper) or **Upload a File**.
2.  Select your **Target Language** (e.g., Hindi or Hinglish Gen Z).
3.  Choose **Detail Level**:
    - *Deep Dive:* For comprehensive coverage (10-15 mins).
    - *Brief Summary:* For quick updates (2-5 mins).
4.  Click **Generate Podcast**.

## 📄 License
MIT
