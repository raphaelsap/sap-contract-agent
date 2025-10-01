# SAP Contract Agent

Streamlit application that extracts structure from contract PDFs and invoice spreadsheets, distils them into concise YAML summaries, and uses GPT-5 (via the OpenAI API) to clean the data, compare contract vs. invoice line items, generate a risk review, and provide a Spanish translation. All intermediate artefacts are persisted for auditability and re-use.

## Features
- OCR and structure extraction from PDFs using `unstructured`
- Spreadsheet normalisation to YAML via `pandas`
- Multi-step GPT-5 prompting: YAML clean-up, compliance analysis, contract risk briefing, and translation
- Streamlit UI with live visibility into extraction summaries and final recommendations
- Persisted artefacts (`artefacts/`) and analysis outputs (`data/`)
- Ready for local execution and Cloud Foundry deployment

## Prerequisites
- Python 3.11
- System dependencies for `unstructured` OCR (Tesseract, Poppler); consult the [unstructured docs](https://unstructured-io.github.io/unstructured/) for installation steps on your OS
- OpenAI API key with access to the GPT-5 model (or compatible equivalent)

## Local Setup
1. Create and activate a virtual environment.
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies.
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and populate with your OpenAI credentials (and optionally SAP AI Core details if you intend to switch back).
   ```bash
   cp .env.example .env
   ```
4. Run the Streamlit UI.
   ```bash
   streamlit run streamlit_app.py
   ```
5. Upload a contract PDF and an invoice spreadsheet. The app stores originals in `artefacts/<run_id>/` and generated YAML/markdown in `data/<run_id>/`.

## Environment Variables
- `OPENAI_API_KEY` (required)
- `OPENAI_API_BASE` (optional, defaults to `https://api.openai.com/v1`)
- `OPENAI_MODEL` (defaults to `gpt-5`)
- `DATA_STORAGE_PATH`, `ARTEFACT_STORAGE_PATH` (optional overrides for persistence folders)
- Optional legacy SAP AI Core variables are still read (`SAP_AICORE_*`) but unused in the default GPT-5 flow.

## Cloud Foundry Deployment
1. Make sure the target org/space has access to the Python buildpack and that the OpenAI credentials can be set as environment variables.
2. Set at least `OPENAI_API_KEY` (and optionally override `OPENAI_MODEL`).
3. Push the app.
   ```bash
   cf push
   ```
4. Access the route assigned by Cloud Foundry to interact with the Streamlit UI.

The deployment uses `Procfile` + `manifest.yml`; Cloud Foundry passes the port via `$PORT`, and Streamlit listens on that socket.

## Project Structure
```
.
├── app
│   ├── document_processing
│   │   ├── excel_parser.py
│   │   └── pdf_parser.py
│   ├── llm
│   │   ├── openai_client.py
│   │   └── workflow.py
│   ├── utils
│   │   ├── config.py
│   │   └── storage.py
│   └── service.py
├── artefacts/            # original uploads per run id
├── data/                 # YAML + markdown outputs per run id
├── streamlit_app.py      # Streamlit entry point
├── requirements.txt
├── manifest.yml
├── Procfile
├── runtime.txt
└── README.md
```

## Next Steps
- Expand LangGraph workflow with additional validation nodes (e.g., monetary checks)
- Add authentication around the Streamlit app if exposed publicly
- Integrate automatic regression tests for parsing logic using sample documents
