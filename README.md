# Wavecell AI (Zero-Data SMS & AI to Bridge the Gap)

Low-bandwidth travel guide and transit routing over GSM-7 and local SQLite/ChromaDB.

### Project Tree for Repository

```text
travelai
├── .env.example
├── .gitignore
├── README.md
├── android-gateway                       # Native Android App (Relays cellular SIM SMS to backend API)
│   ├── build.gradle.kts
│   └── app
│       ├── AndroidManifest.xml
│       └── src
│           └── main
│               └── java
│                   └── com
│                       └── travelai
│                           └── gateway
│                               ├── MainActivity.kt
│                               ├── SmsReceiver.kt
│                               └── WebhookForwarder.kt
├── backend
│   ├── .dockerignore
│   ├── .railwayignore
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── output                            # Cached & pre-computed vector indexes / transit lookups
│   │   ├── emergency_contacts.json
│   │   ├── gtfs_bus_schedules.json
│   │   ├── metrics.json
│   │   └── travel_faqs_vector_index.json
│   ├── src
│   │   ├── __init__.py
│   │   ├── pipeline.py                   # Inbound SMS -> Router -> Translator -> GSM Enforcer -> Outbound
│   │   ├── analysis
│   │   │   ├── __init__.py
│   │   │   └── intent_classifier.py     # Classifies SMS: Transit FAQ, Emergency SOS, or Operator Request
│   │   ├── api
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── schemas.py
│   │   │   └── routes
│   │   │       ├── __init__.py
│   │   │       ├── emergency.py          # SOS alert escalation endpoints
│   │   │       ├── schedules.py          # Offline GTFS transit search
│   │   │     
│   │   ├── gateway
│   │   │   ├── __init__.py
│   │   │   ├── payload_parser.py         # Parses incoming SMS headers & phone numbers
│   │   │   └── sms_enforcer.py           # 160-char GSM 7-bit & 140-byte strict payload truncation
│   │   ├── rag
│   │   │   ├── __init__.py
│   │   │   ├── chroma_store.py           # ChromaDB vector store for WikiVoyage guide snippets
│   │   │   ├── embedder.py               # Fast local embeddings engine
│   │   │   ├── prompts.py                # Ultra-compact system prompts for low-token outputs
│   │   │   └── retriever.py              # Hybrid vector + GTFS schedule retriever
│   │   ├── router
│   │   │   ├── __init__.py
│   │   │   ├── confidence_eval.py        # Confidence scorer for Local AI responses
│   │   │   └── fallback.py               # Local AI (Ollama/Phi-3) -> Frontier AI (GPT-4o) fallback
│   │   └── translation                   # Non-Latin script to GSM-7 Latin converter (Banglish/Hinglish)
│   │── test_api.py
│   ├── test_enforcer.py
│   ├── test_rag.py
│   ├── test_router.py
│   └── test_transliteration.py
├── data
│   ├── weather/               # BMD/IMD cyclone warning codes & squall rules
│   ├── gis/                   # Maritime boundaries, EEZ, & 2G cell tower range vectors
│   ├── emergency/             # Coast Guard MRCC, Navy, & coastal hospital contacts
│   ├── LLM AI4Bharat IndicTrans / Samanantar Corpus to support hanglish banglish written language  
│   ├── wikivoyage_snippets    # Open travel guides dataset
│   └── README.md
├── next-js-llm.txt                   # Reference notes for Next.js SSE streaming
└── web-app                           # Next.js Operator Dashboard & Mock Phone View
    ├── .env.example
    ├── .gitignore
    ├── README.md
    ├── eslint.config.mjs
    ├── next.config.ts
    ├── package.json
    ├── pnpm-lock.yaml
    ├── postcss.config.mjs
    ├── tsconfig.json
    ├── vitest.config.ts
    ├── public
    │   ├── favicon.ico
    │   ├── feature-phone-frame.png
    │   ├── globe.svg
    │   └── window.svg
    └── src
        ├── app
        │   └── (app)
        │       ├── favicon.ico
        │       ├── globals.css
        │       ├── layout.tsx
        │       ├── page.tsx               # Main Operator Dashboard
        │       ├── analytics
        │       ├── emergency
        │       │   └── page.tsx           # Live SOS & Rescue Monitoring
        │       └── mock-phone
        │           └── page.tsx           # Retro Feature Phone Dual-View Simulator
        ├── components
        │   ├── dashboard
        │   │   ├── EmergencyAlertPanel.tsx
        │   │   ├── LiveMessageStream.tsx
        │   │   └── SmsByteMeter.tsx
        │   ├── layout
        │   │   ├── ChatDrawer.tsx
        │   │   └── TopNav.tsx
        │   ├── simulator
        │   │   └── FeaturePhoneDisplay.tsx
        │   └── ui
        │       └── shader-animation.tsx
        └── lib
            ├── api-client.ts
            └── utils.ts

1. Problem Statement
Because of OffGrid TourAI, offline travelers and remote tour operators will receive instant, multilingual travel navigation and emergency assistance **by** the moment they enter a cellular dead zone or disable data roaming **that they would otherwise** experience late, do worse, or fail to receive entirely; **we know because** over 60% of eco-tourists in remote regions disable data roaming to avoid massive fees or lose 3G/4G connectivity, leaving them completely isolated during transit crises and medical emergencies.

2. AI Capabilities of the Solution
 What the Tool Does with AI
Dual AI Fallback Engine:** Uses a lightweight **Local LLM** (Phi-3 / Llama-3 via Ollama) paired with **ChromaDB Vector RAG** to answer localized transit, schedule, and FAQ queries at zero API cost. If the query requires complex reasoning or signals an emergency, it escalates to a **Frontier Model** (GPT-4o).
Automated Translation & Transliteration:** Translates incoming native SMS messages (e.g., Bangla, French, Hindi) into English for the operator, and auto-transliterates output text back into Latin script (Banglish/Hinglish) to keep payload sizes small.

Why a Simpler Tool Will Not Work
** Plain SMS / Auto-Responders:** Cannot understand unstructured natural language queries, infer intent, or handle complex contextual questions like *"I missed my 3 PM bus and my foot is swollen, what do I do?"*
** A Spreadsheet / Static Database:** Requires exact keyword matches and cannot translate multi-lingual inputs or perform semantic vector searches.
** Web Search:** Completely useless without an active 3G/4G/5G mobile data plan or Wi-Fi connection.

#### Guardrails in Place

**GSM-7 Byte Enforcer:** Automatically calculates payload sizes. If non-Latin script triggers Unicode encoding (which drops single SMS limits from 160 characters down to 70), the guardrail forces automatic transliteration to Latin script to guarantee a single **140-byte / 160-character** transmission.
**Human-in-the-Loop Escalation:** High-risk queries (medical, safety, lost off-trail) bypass fully automated resolution and trigger live alerts on the tour operator’s Web Dashboard.

4. The Challenge/Gap Being Addressed
Where the Tool Sits in the User’s Day
For the Traveler (User 1):** Sits passively in their native SMS messaging app. They don't download anything or log in. When they lose internet or face a travel delay, they text the gateway number just like texting a friend.
For the Tour Operator (User 2):** Open on their laptop screen at the central office. It aggregates all active offline travelers into a single real-time channel, managing automated AI replies and flagging emergency cases.

Tech Stack Details

```
├── Frontend: Next.js 15, Tailwind CSS, TypeScript (Operator Dashboard & Feature Phone Simulator)
├── Mobile Gateway: Native Kotlin Android App (Intercepts SIM SMS & forwards via HTTP Webhook)
├── Backend Core: FastAPI (Python 3.11), Uvicorn, Pydantic
├── Local AI & Storage: Ollama (Phi-3 / Llama-3 8B), ChromaDB (Vector RAG), SQLite (Sessions/Logs)
├── Frontier AI: OpenAI API (GPT-4o) / Gemini API
└── Enforcer Pipeline: Custom Python GSM-7 Bitwise Byte & Character Counter + NLLB Transliteration

### 5. Your Take: What Localizing AI Development Means to You

> "To us, localizing AI development means **democratizing intelligence by adapting AI to existing infrastructure, rather than forcing vulnerable users to buy expensive hardware**.
> Silicon Valley builds AI for 5G smartphones, unlimited data plans, and high-spec web browsers. But in regions across South Asia and the global south, millions of travelers, farmers, and remote workers rely on basic cellular networks and feature phones. Localizing AI means engineering intelligent fallback routers, byte-level payload optimization, and regional language transliteration so that a farmer in Sajek or a trekker in Ladakh gets the exact same frontier intelligence as someone standing in San Francisco—over a standard 2G SMS."


| **1. The Built Solution (Small AI Fidelity)** 
| **2. Development Relevance and Impact** 
| **3. Data Grounding** 
| **4. Evidence It Works** 
| **5. Value Proposition for AI & Clarity** 
| **6. Scalability, Replicability & Next Steps** 
| **7. Human in the loop, Responsible AI, Data and Safety** 
---

       ### Criterion Breakdown & Evaluation

         [Artisanal Boat / Island Ferry]
          Basic Feature Phone / 2G GSM
                │
                │ (2G SMS Payload <= 140 Bytes)
                ▼
     [Coastal Cell Towers (GP/Robi/Airtel)]
                │
                ▼
     [Android SMS Gateway (In Port / Lighthouse)]
                │
                ▼
    ┌────────────────────────────────────────────────────────┐
    │                  WaveCellAI BACKEND ENGINE             │
    ├────────────────────────────────────────────────────────┤
    │ 1. Intent Classifier  --> Weather, Tide, Border, SOS   │
    │ 2. ChromaDB RAG       --> Tidal Charts, Cyclone Maps   │
    │ 3. SQLite DB          --> Waterway GTFS, Vessel Logs   │
    │ 4. GSM-7 Transliter  --> Banglish / Hinglish Conversion│
    └────────────────────────────────────────────────────────┘
                │                                    │
    (Standard Query)                               (SOS / Emergency)
                ▼                                    ▼
    [Auto 160-Char Response]             [Coast Guard / MRCC Dashboard]
    "High tide 14:30. Wind 12kt SE"      "RED ALERT: Vessel #401 adrift"

SELF JUDGEMENT:
My Main Focus Was from my lived experience in Maritime Use Case
1. Tide, Weather & Squall Advisory (Level 1 Local AI — $0 Cost)
2. Maritime International Line (IMBL) Guardrail
3. SOS Distress & Rescue Escalation (Human-in-the-Loop)

 (The MVP shows the potential for even better success rate.)




