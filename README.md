
# Podcastify-AI (Sarvam Edition)

A powerful **Text-to-Podcast** generation engine specifically designed for **Indian languages**. It transforms articles, research papers, and documents into engaging, natural-sounding audio conversations.

## 🚀 Features

- **Multilingual Support:** Generate podcasts in **Hindi**, **Telugu**, **Tamil**, and **English**.
- **Deep Understanding:** Uses **OpenAI GPT-4o** to analyze content, extracting technical details and nuances ("Deep Dive" mode).
- **Natural Conversations:** Scripts are written directly in the target language for conversational flow, not just translated.
- **Hyper-Realistic Audio:** Powered by **Sarvam AI's `bulbul:v3`** model for lifelike Indian voices.
- **Smart Ingestion:** 
  - **URLs:** Uses **Jina Reader** to extract clean content from web pages.
  - **Files:** Supports PDF, DOCX, TXT via LlamaIndex.

## 🛠 Architecture

1.  **Ingestion:** Jina Reader (Web) / LlamaIndex (Files)
2.  **Orchestration & Scripting:** FastAPI + OpenAI GPT-4o
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
# Optional: ANTHROPIC_API_KEY if using Claude for other tasks
```

**Run Server:**
```bash
uvicorn app.main:app --reload
```

### 2. Frontend Setup

```bash
cd ui
npm install
npm run dev
```

Visit `http://localhost:5173` to start creating podcasts!

## 📝 Usage

1.  **Paste a URL** (e.g., a news article or research paper) or **Upload a File**.
2.  Select your **Target Language** (e.g., Hindi).
3.  Choose **Detail Level**:
    - *Deep Dive:* For comprehensive coverage (10-15 mins).
    - *Brief Summary:* For quick updates (2-5 mins).
4.  Click **Generate Podcast**.

## 📄 License
MIT
