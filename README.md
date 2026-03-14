---
title: Cuteoff Analyzer
sdk: docker
app_port: 7860
---

# MHT-CET Cutoff PDF to Counseling Excel Converter

This project converts Maharashtra CAP round cutoff PDFs into a counseling-ready Excel workbook for educational counselors. It includes a FastAPI backend for PDF parsing and workbook generation, and a React + Tailwind frontend for upload, progress tracking, and download.

## Project Structure

```text
backend/
  app.py
  parser.py
  excel_writer.py
  city_district_map.py
  requirements.txt
  requirements-dev.txt
  tests/
frontend/
  src/
    App.jsx
    UploadSection.jsx
    ProgressSection.jsx
    DownloadSection.jsx
```

## Backend Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements-dev.txt
uvicorn backend.app:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

## Frontend Setup

```bash
cd frontend
npm.cmd install
npm.cmd run dev
```

The frontend will run at `http://127.0.0.1:5173` and proxy API requests to the FastAPI backend.

## Production Build

```bash
cd frontend
npm.cmd install
npm.cmd run build
```

After building, start FastAPI again. If `frontend/dist` exists, the backend will serve the compiled React app.

## Docker Deployment

Build and run the full app with Docker:

```bash
docker build -t cuteoff-analyzer .
docker run --rm -p 8000:7860 cuteoff-analyzer
```

The container builds the React frontend, copies `frontend/dist` into the image, and starts the FastAPI app on port `7860` by default.

## Hugging Face Spaces via GitHub

If you want Hugging Face to build and host the app for you, keep this repo on GitHub and use the included GitHub Actions workflow.

1. Create a new Hugging Face Space and choose `Docker` as the SDK.
2. In your GitHub repository, add a secret named `HF_TOKEN`.
3. In your GitHub repository, add variables named `HF_USERNAME` and `HF_SPACE_NAME`.
4. Push to the `main` branch. The workflow will mirror the repo to your Space.

The container build happens on Hugging Face, not on your laptop.

## Tests

```bash
pytest backend/tests
```

## Real PDF Validation

1. Place a real MHT-CET CAP cutoff PDF somewhere inside the workspace.
2. Run a first-pass parse against the first 10 pages before full conversion.
3. Confirm at least 5 complete college/branch rows, then run the full conversion.

## Notes

- The parser uses `pdfplumber`, not `PyPDF2`.
- Unsupported categories that are not part of the counseling workbook layout are parsed for robustness and omitted from the Excel export.
- Missing cutoff cells remain blank in the workbook.
