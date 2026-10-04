import os
from pathlib import Path

# Define the complete folder and file structure with initial content
structure = {
    ".env.example": (
        "DATABASE_URL=sqlite:///backend/output/gtfs_schedules.db\n"
        "OPENAI_API_KEY=your_key_here\n"
        "LOCAL_LLM_URL=http://localhost:11434\n"
    ),
    ".gitignore": (
        "node_modules/\n"
        ".venv/\n"
        "__pycache__/\n"
        "output/*.db\n"
        "output/*.json\n"
        ".env\n"
        ".DS_Store\n"
    ),
    "README.md": (
        "# Taranga AI (Zero-Data SMS & AI Bridge)\n\n"
        "Low-bandwidth travel guide and transit routing over GSM-7 and local SQLite/ChromaDB."
    ),

    # Android Gateway
    "android-gateway/build.gradle.kts": 'plugins { id("com.android.application") version "8.2.0" apply false }',
    "android-gateway/app/AndroidManifest.xml": (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<manifest xmlns:android=\"http://schemas.android.com/apk/res/android\">\n"
        "    <uses-permission android:name=\"android.permission.RECEIVE_SMS\" />\n"
        "    <uses-permission android:name=\"android.permission.INTERNET\" />\n"
        "</manifest>"
    ),
    "android-gateway/app/src/main/java/com/travelai/gateway/MainActivity.kt": (
        "package com.travelai.gateway\n\n"
        "import android.os.Bundle\n"
        "import androidx.appcompat.app.AppCompatActivity\n\n"
        "class MainActivity : AppCompatActivity() {\n"
        "    override fun onCreate(savedInstanceState: Bundle?) {\n"
        "        super.onCreate(savedInstanceState)\n"
        "        setContentView(android.R.layout.activity_list_item)\n"
        "    }\n"
        "}\n"
    ),
    "android-gateway/app/src/main/java/com/travelai/gateway/SmsReceiver.kt": "// BroadcastReceiver for capturing incoming cellular SMS stubs",
    "android-gateway/app/src/main/java/com/travelai/gateway/WebhookForwarder.kt": "// HTTP client payload forwarder to backend webhook API stubs",

    # Backend Core & Configs
    "backend/.dockerignore": "__pycache__\noutput/\n.env",
    "backend/.railwayignore": "output/*.db",
    "backend/Dockerfile": (
        "FROM python:3.11-slim\n"
        "WORKDIR /app\n"
        "COPY . .\n"
        "RUN pip install uv\n"
        "CMD [\"uv\", \"run\", \"uvicorn\", \"backend.src.api.main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]"
    ),
    "backend/pyproject.toml": (
        "[project]\n"
        'name = "travelai-backend"\n'
        'version = "0.1.0"\n'
        "dependencies = [\n"
        '    "fastapi>=0.110.0",\n'
        '    "uvicorn>=0.28.0",\n'
        '    "chromadb>=0.4.24",\n'
        '    "pandas>=2.2.0",\n'
        '    "pydantic>=2.6.0"\n'
        "]\n"
    ),
    "backend/uv.lock": "# UV lockfile placeholder",

    # Backend Outputs (Caches/JSONs)
    "backend/output/emergency_contacts.json": '{\n  "coastal_sos": "+8801700000000",\n  "tourist_police": "999"\n}',
    "backend/output/gtfs_bus_schedules.json": "[]",
    "backend/output/metrics.json": '{\n  "total_sms_processed": 0,\n  "bytes_saved": 0\n}',
    "backend/output/travel_faqs_vector_index.json": "{}",

    # Backend Source Modules (__init__ and placeholders)
    "backend/src/__init__.py": "",
    "backend/src/pipeline.py": "# Inbound SMS -> Router -> Translator -> GSM Enforcer -> Outbound pipeline",

    "backend/src/analysis/__init__.py": "",
    "backend/src/analysis/intent_classifier.py": "# Classifies SMS: Transit FAQ, Emergency SOS, or Operator Request",

    "backend/src/api/__init__.py": "",
    "backend/src/api/main.py": "# FastAPI application initialization root",
    "backend/src/api/schemas.py": "# Pydantic validation schemas",
    "backend/src/api/routes/__init__.py": "",
    "backend/src/api/routes/chat.py": "# Web operator live SSE streaming route",
    "backend/src/api/routes/emergency.py": "# SOS alert escalation endpoints",
    "backend/src/api/routes/metrics.py": "# SMS byte count & cost analytics endpoints",
    "backend/src/api/routes/schedules.py": "# Offline GTFS transit search endpoints",
    "backend/src/api/routes/sms.py": "# Android SMS Gateway incoming/outgoing webhook endpoints",
    "backend/src/api/routes/users.py": "# Phone number & session state mapping endpoints",

    "backend/src/gateway/__init__.py": "",
    "backend/src/gateway/payload_parser.py": "# Parses incoming SMS headers & phone numbers",
    "backend/src/gateway/sms_enforcer.py": "# 160-char GSM 7-bit & 140-byte strict payload truncation",

    "backend/src/rag/__init__.py": "",
    "backend/src/rag/chroma_store.py": "# ChromaDB vector store for WikiVoyage guide snippets",
    "backend/src/rag/embedder.py": "# Fast local embeddings engine",
    "backend/src/rag/prompts.py": "# Ultra-compact system prompts for low-token outputs",
    "backend/src/rag/retriever.py": "# Hybrid vector + GTFS schedule retriever",

    "backend/src/router/__init__.py": "",
    "backend/src/router/confidence_eval.py": "# Confidence scorer for Local AI responses",
    "backend/src/router/fallback.py": "# Local AI (Ollama/Phi-3) -> Frontier AI (GPT-4o) fallback router",

    "backend/src/translation/__init__.py": "",
    "backend/src/translation/translator.py": "# Auto-translation pipeline (NLLB / OpenAI)",
    "backend/src/translation/transliterator.py": "# Non-Latin script to GSM-7 Latin converter (Banglish/Hinglish)",

    # Backend Tests & Fixtures
    "backend/tests/__init__.py": "",
    "backend/tests/conftest.py": "# Pytest fixtures and configuration setup",
    "backend/tests/fixtures/gtfs_sample.json": "{}",
    "backend/tests/fixtures/sms_01_simple_faq.txt": "What is emergency transport?",
    "backend/tests/fixtures/sms_02_bangla_query.txt": "Chittagong bus time?",
    "backend/tests/fixtures/sms_03_emergency.txt": "SOS COASTAL FLOOD",
    "backend/tests/fixtures/sms_04_oversized.txt": "A" * 200,
    "backend/tests/fixtures/sms_05_web_reply.json": '{"status": "ok"}',
    "backend/tests/test_api.py": "# Test suite for FastAPI routes",
    "backend/tests/test_enforcer.py": "# Test suite for GSM-7 byte limitations",
    "backend/tests/test_rag.py": "# Test suite for ChromaDB retrieval",
    "backend/tests/test_router.py": "# Test suite for Local/Cloud fallback logic",
    "backend/tests/test_transliteration.py": "# Test suite for Indic script transliteration",

    # Data & Documentation
    "data/gtfs_schedules/README.md": "# GTFS Feed Datasets Directory",
    "data/wikivoyage_snippets/README.md": "# WikiVoyage Extracted Dumps Directory",
    "docs/architecture.md": "# System Diagram & SMS Gateway Sequence Walkthrough",
    "docs/pitch-guide.md": "# Hackathon Pitch Deck & Value Proposition Guide",
    "docs/technical-video-script.md": "# Technical Architecture Video Walkthrough Script",
    "framework-docs/next-js-llm.txt": "# Reference notes for Next.js SSE streaming implementations",
    "ideas_instructions/tech_instructions.txt": "# Core specifications and instructions",

    # Web-App Next.js Scaffold
    "web-app/.env.example": "NEXT_PUBLIC_API_URL=http://localhost:8000",
    "web-app/.gitignore": "node_modules/\n.next/\n",
    "web-app/README.md": "# Taranga AI Next.js Operator Dashboard",
    "web-app/eslint.config.mjs": "export default [];",
    "web-app/next.config.ts": "import type { NextConfig } from 'next';\nconst config: NextConfig = {};\nexport default config;",
    "web-app/package.json": '{\n  "name": "travelai-web",\n  "version": "0.1.0",\n  "private": true,\n  "dependencies": {\n    "next": "14.1.0",\n    "react": "18.2.0",\n    "react-dom": "18.2.0"\n  }\n}',
    "web-app/pnpm-lock.yaml": "# pnpm lockfile placeholder",
    "web-app/postcss.config.mjs": "export default {};",
    "web-app/tsconfig.json": '{\n  "compilerOptions": {\n    "target": "es5",\n    "lib": ["dom", "dom.iterable", "esnext"],\n    "allowJs": true,\n    "skipLibCheck": true,\n    "strict": true,\n    "forceConsistentCasingInFileNames": true,\n    "module": "esnext",\n    "moduleResolution": "node",\n    "resolveJsonModule": true,\n    "isolatedModules": true,\n    "jsx": "preserve"\n  }\n}',
    "web-app/vitest.config.ts": "// Vitest configuration setup",

    # Web-App Public Assets
    "web-app/public/favicon.ico": "",
    "web-app/public/feature-phone-frame.png": "",
    "web-app/public/globe.svg": "",
    "web-app/public/window.svg": "",

    # Web-App Source Code & Pages
    "web-app/src/__tests__/setup.ts": "// Test environment setup",
    "web-app/src/__tests__/step1-sms-webhook.test.tsx": "// Test step 1",
    "web-app/src/__tests__/step2-operator-chat.test.tsx": "// Test step 2",
    "web-app/src/__tests__/step3-phone-simulator.test.tsx": "// Test step 3",

    "web-app/src/app/(app)/favicon.ico": "",
    "web-app/src/app/(app)/globals.css": "@tailwind base;\n@tailwind components;\n@tailwind utilities;",
    "web-app/src/app/(app)/layout.tsx": "// Main app root layout",
    "web-app/src/app/(app)/page.tsx": "// Main Operator Dashboard Page",
    "web-app/src/app/(app)/analytics/page.tsx": "// SMS Byte Reduction & Cost Savings Metrics Page",
    "web-app/src/app/(app)/emergency/page.tsx": "// Live SOS & Rescue Monitoring Page",
    "web-app/src/app/(app)/feature-phone/page.tsx": "// Retro Feature Phone Dual-View Simulator Page",

    "web-app/src/components/dashboard/EmergencyAlertPanel.tsx": "// Emergency alert component",
    "web-app/src/components/dashboard/LiveMessageStream.tsx": "// Live message stream component",
    "web-app/src/components/dashboard/SmsByteMeter.tsx": "// SMS byte meter component",
    "web-app/src/components/layout/ChatDrawer.tsx": "// Chat drawer layout component",
    "web-app/src/components/layout/TopNav.tsx": "// Top navigation component",
    "web-app/src/components/simulator/FeaturePhoneDisplay.tsx": "// Feature phone frame simulation component",
    "web-app/src/components/ui/shader-animation.tsx": "// Shader animation UI component",

    "web-app/src/lib/api-client.ts": "// API client helper functions",
    "web-app/src/lib/utils.ts": "// Utility helper functions"
}


def create_project_structure():
    print("🚀 Initializing Taranga AI repository file structure...")
    for file_path, content in structure.items():
        path = Path(file_path)
        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write file content (even if empty string)
        path.write_text(content, encoding="utf-8")
        print(f"Created -> {file_path}")
    print("\n✅ All files and directories successfully created!")


if __name__ == "__main__":
    create_project_structure()