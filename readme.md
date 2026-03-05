# 🏥 HealthNotes-to-FHIR (AI Agent Medical Coder)

An open-source pipeline and multi-agent system designed to translate unstructured healthcare notes (from both patients and healthcare professionals) into standardized ICD-10 codes and FHIR R4 resources.

This repository houses the entire lifecycle of the project: from our LLM multi-agent experimentation phase to the production-ready API and the interactive web chat demonstration.

## 📖 Overview

Clinical documentation is often unstructured, messy, and time-consuming to standardize. This project aims to automate the structuring of medical text using advanced AI agentic workflows.

**Core Objectives:**
*   **Multi-Agent Experimentation:** Evaluate different LLM agent frameworks (e.g., LangGraph, CrewAI) to synthesize, verify, and format clinical text into strict ICD-10 and FHIR R4 JSON structures.
*   **Bilingual NLP Capability:** Natively support unstructured clinical notes written in both English and Portuguese (leveraging multilingual LLMs and specialized medical embeddings).
*   **Production API:** Expose the most successful experimental pipeline as a highly available, free-to-use API protected by intelligent rate limiting.
*   **Interactive Chat UI:** Provide a lightweight, conversational web interface for users to test the translation service in real-time.

## 🏗️ Architecture & Repository Structure

This repository is built with a modular monorepo structure to separate research from production services.

```text
├── /experiments          # Jupyter notebooks, agent evaluations, and NLP benchmarks
│   ├── /data             
│   │   ├── /raw          # Original datasets (Git ignored)
│   │   ├── /processed    # Cleaned/transformed data (Git ignored)
│   │   ├── /samples      # Small anonymized sets for testing (Committed)
│   │   └── /specs        # FHIR specification reference files
│   ├── /agents           # Multi-agent workflow definitions (Coder, Reviewer, Synthesizer)
│   └── /evaluations      # Accuracy metrics for ICD-10 extraction and FHIR validation
├── /api                  # Production-level FastAPI application
│   ├── /routers          # API endpoints (e.g., /v1/translate)
│   ├── /services         # The "winning" agentic workflow from the experiments phase
│   └── /middleware       # Rate limiting (Redis), auth, and request validation
├── /web                  # React/Next.js frontend for the chat interface
│   ├── /components       # Chat UI, JSON payload viewer
│   └── /hooks            # API integration and state management
└── docker-compose.yml    # Orchestration for local development
```

## ✨ Features

*   **Multi-Agent Collaboration:** Utilizes a supervised agentic architecture (e.g., Extraction Agent -> Coding Agent -> Reviewer Agent) to ensure high-fidelity ICD-10 mapping and reduce LLM hallucinations.
*   **FHIR R4 Compliance:** Outputs strictly validated FHIR R4 JSON bundles (e.g., Patient, Condition, Observation, Encounter).
*   **Cross-Lingual Understanding:** Optimized for clinical nuances, abbreviations, and slang in both English and Portuguese healthcare contexts.
*   **Public Rate-Limited API:** A production-ready API gateway utilizing token-bucket rate limiting to offer the service freely while preventing abuse.
*   **Real-time Chat Interface:** A sleek, user-friendly web app allowing healthcare professionals and developers to paste notes and instantly converse with the translation agent.

## 🚀 Getting Started

### Prerequisites
*   Python 3.10+
*   Node.js 18+ (for the web UI)
*   Docker & Docker Compose (optional, for easy orchestration)
*   API Keys for the chosen LLM provider (e.g., OpenAI, Anthropic, or local inference endpoints)

### Local Development Setup

**1. Clone the repository**
```bash
git clone https://github.com/your-org/HealthNotes-to-FHIR.git
cd HealthNotes-to-FHIR
```

**2. Start the Production API (Backend)**
```bash
cd api
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set up your environment variables
cp .env.example .env

uvicorn main:app --reload --port 8000
```
*Note: Edit `.env` to add your LLM API keys and Redis URL (for rate limiting).*

**3. Start the Chat Interface (Frontend)**
```bash
cd ../web
npm install
npm run dev
```
Access the chat interface at `http://localhost:3000` and the API documentation (Swagger) at `http://localhost:8000/docs`.

## 🔌 API Usage (Preview)

The production API offers a straightforward endpoint for text translation. By default, the free tier is rate-limited to 50 requests per hour per IP.

**Endpoint:** `POST /api/v1/translate`

**Request:**
```bash
curl -X POST "https://api.yourdomain.com/v1/translate" \
     -H "Content-Type: application/json" \
     -d '{
           "text": "Paciente de 45 anos relata dor no peito irradiando para o braço esquerdo há 2 horas. Histórico de hipertensão.",
           "language": "pt"
         }'
```

**Response:**
```json
{
  "icd_10_codes": [
    {"code": "I20.9", "description": "Angina pectoris, unspecified"},
    {"code": "I10", "description": "Essential (primary) hypertension"}
  ],
  "fhir_bundle": {
    "resourceType": "Bundle",
    "type": "transaction",
    "entry": [
      // ... FHIR R4 Condition and Observation resources ...
    ]
  },
  "confidence_score": 0.92
}
```

## 🗺️ Roadmap

- [x] **Phase 1: Research & Experimentation**
  - Construct datasets of English and Portuguese unstructured clinical notes.
  - Test baseline LLMs vs. Multi-Agent architectures for ICD/FHIR extraction.
- [ ] **Phase 2: API Development**
  - Lock in the most performant agent pipeline.
  - Build the FastAPI backend with Redis-backed rate limiting.
  - Implement FHIR R4 schema validation via Pydantic.
- [ ] **Phase 3: Web Interface**
  - Develop the React-based chat UI.
  - Integrate real-time streaming responses and JSON rendering.
- [ ] **Phase 4: Production Deployment**
  - Containerize services.
  - Deploy to public-facing infrastructure with automated CI/CD.

## 🤝 Contributing

We welcome contributions from software engineers, data scientists, and healthcare professionals!

1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

Please read our `CONTRIBUTING.md` for details on our code of conduct and the process for submitting pull requests.

## ⚠️ Disclaimer

This software is for experimental and educational purposes only. The AI-generated ICD-10 codes and FHIR resources should never be used for clinical decision-making, official medical billing, or patient care without strict review by a certified medical coding professional or licensed healthcare provider. Do not submit actual Protected Health Information (PHI) or Personally Identifiable Information (PII) to public APIs.

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.