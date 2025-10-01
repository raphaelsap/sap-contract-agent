# SAP Contract Agent

Streamlit application that extracts structure from contract PDFs and invoice spreadsheets, compares them with an LLM hosted on SAP BTP AI Core, and stores the results for review.

## Features
- OCR and structure extraction from PDFs using `unstructured`
- Spreadsheet normalisation to YAML via `pandas`
- LangGraph workflow that compares contract vs. invoice data and proposes next actions with SAP AI Core
- Streamlit UI with visibility into intermediate YAML and markdown outputs
- Persisted artefacts (`artefacts/`) and analysis outputs (`data/`)
- Ready for local execution and Cloud Foundry deployment

## Prerequisites
- Python 3.11
- System dependencies for `unstructured` OCR (Tesseract, Poppler); consult the [unstructured docs](https://unstructured-io.github.io/unstructured/) for installation steps on your OS
- SAP BTP AI Core deployment ID with access to the generative service

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
3. Copy `.env.example` to `.env` and populate with the SAP AI Core credentials (client id, secret, auth URL, API base, deployment id, resource group, scope).
   ```bash
   cp .env.example .env
   ```
4. Run the Streamlit UI.
   ```bash
   streamlit run streamlit_app.py
   ```
5. Upload a contract PDF and an invoice spreadsheet. The app stores originals in `artefacts/<run_id>/` and generated YAML/markdown in `data/<run_id>/`.

## Environment Variables
- `SAP_AICORE_CLIENT_ID`, `SAP_AICORE_CLIENT_SECRET`
- `SAP_AICORE_AUTH_URL` (`https://<identity-zone>.authentication.<region>.hana.ondemand.com`)
- `SAP_AICORE_API_BASE` (e.g. `https://api.ai.prod.eu-central-1.aws.ml.hana.ondemand.com`)
- `SAP_AICORE_DEPLOYMENT_ID` (target GPT deployment)
- `SAP_AICORE_RESOURCE_GROUP` (often `default`)
- `SAP_AICORE_SCOPE` (optional depending on tenant configuration)
- `SAP_AICORE_CHAT_COMPLETIONS_PATH` (override if your deployment exposes a non-default path)
- `DATA_STORAGE_PATH`, `ARTEFACT_STORAGE_PATH` (optional overrides for persistence folders)

## Cloud Foundry Deployment
1. Make sure the target org/space has access to the Python buildpack and that the AI Core credentials are available (user-provided service or environment variables).
2. If using a user-provided service, extract the credentials and set the environment variables expected by the app. Example:
   ```bash
   cf set-env sap-contract-agent SAP_AICORE_CLIENT_ID <client_id>
   cf set-env sap-contract-agent SAP_AICORE_CLIENT_SECRET <client_secret>
   cf set-env sap-contract-agent SAP_AICORE_AUTH_URL <auth_url>
   cf set-env sap-contract-agent SAP_AICORE_API_BASE <api_base>
   cf set-env sap-contract-agent SAP_AICORE_DEPLOYMENT_ID <deployment_id>
   cf set-env sap-contract-agent SAP_AICORE_RESOURCE_GROUP default
   cf set-env sap-contract-agent SAP_AICORE_SCOPE <scope>
   ```
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
│   │   ├── aicore_client.py
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
