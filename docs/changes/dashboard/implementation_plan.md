# Implementation Plan — Building Doctor AI (RAG-Anything Web App)

This plan details the implementation of a responsive, premium Single Page Web Application called **Doctor AI**, serving as an interactive interface for the **RAG-Anything** document indexing and question-answering framework. The application will run locally out of the box via `run_web.py`, and can be deployed serverlessly on Vercel utilizing Neon DB (PostgreSQL) for state preservation.

## User Review Required

> [!IMPORTANT]
> **Neon DB Integration & Graph Storage**
> We will configure the backend to use PostgreSQL/Neon DB for persistence when `POSTGRES_*` or a `DATABASE_URL` environment variable is defined in the `.env` file. We will configure LightRAG to use `PGKVStorage`, `PGVectorStorage`, `PGDocStatusStorage`, and `PGGraphStorage` (if supported by `lightrag-hku`) or standard PG tables. This is crucial for Vercel deployment, as Vercel functions are stateless and cannot write to a local directory across requests.

> [!WARNING]
> **LLM and Embedding Credentials**
> A `.env` file must be created with your target LLM api key and endpoint (e.g. OpenAI key, Gemini key, or Ollama local setup) to power the indexing and retrieval capabilities.

## Open Questions

> [!NOTE]
> **Which exact PostgreSQL graph storage does `lightrag-hku` expose?**
> Once dependency installation is complete, we will verify the exact class names. In `lightrag-hku`, PostgreSQL storage options include `PGKVStorage`, `PGVectorStorage`, `PGDocStatusStorage`, and `PGGraphStorage` or database-wide tables. We will fall back gracefully to file-based or SQLite storage if PostgreSQL settings are omitted, allowing developers to run the tool locally without setting up a PG database.

---

## Proposed Changes

### Backend Components

#### [NEW] [index.py](file:///d:/DoctorAI/api/index.py)
A FastAPI application that will serve as the backend endpoint, handling:
- **Initialization**: Configures and starts `RAGAnything` based on the `.env` configurations (LLM, Embeddings, and Database).
- **Upload Endpoint** (`POST /api/upload`): Receives files, saves them to a temp folder, and starts a background task using `BackgroundTasks` to invoke `process_document_complete()`.
- **Status Endpoint** (`GET /api/documents`): Returns all files processed or in-progress by reading entries from `lightrag.doc_status`.
- **Query Endpoint** (`POST /api/query`): Calls `aquery()` with the selected mode (hybrid, naive, local, global) and returns the text response along with citations.
- **Static files fallback**: Serves the SPA frontend for non-API requests.

#### [NEW] [run_web.py](file:///d:/DoctorAI/run_web.py)
A lightweight startup script in the workspace root:
- Runs the FastAPI app using `uvicorn` on port `9621` (default from config).
- Uses the `webbrowser` library to automatically open `http://localhost:9621` once the server is alive.

#### [NEW] [vercel.json](file:///d:/DoctorAI/vercel.json)
Deployment configuration for Vercel:
- Defines a Python serverless runtime builder for `api/index.py`.
- Configures URL routing to map API requests to the Python server and static files to Vercel edge.

---

### Frontend Components

#### [NEW] [index.html](file:///d:/DoctorAI/static/index.html)
The layout for the SPA:
- Sidebar (left column) containing:
  - A premium Glassmorphism drag-and-drop zone.
  - A file manager listing all uploaded documents and their real-time parsing statuses.
- Main Chat Window (right column) containing:
  - Message log showing user queries and assistant responses.
  - LLM configuration toggles (Query Mode: hybrid, naive, local, global).
  - Input form with text area.
- CDN resources: `marked.js` (Markdown parsing) and `KaTeX` (LaTeX formula rendering).

#### [NEW] [style.css](file:///d:/DoctorAI/static/style.css)
The look and feel of the web app:
- **Theme**: Premium Glassmorphism Dark Mode (sleek semi-transparent backdrops, subtle blurred elements, vibrant neon accent colors, harmonious borders).
- Layout: Responsive flexbox/grid layout (two columns on desktop, stackable on tablet/mobile).
- Custom loaders and micro-animations for message-sending, typing indications, file processing, and hover effects.

#### [NEW] [script.js](file:///d:/DoctorAI/static/script.js)
Frontend logic:
- Drag-and-drop file upload handler that streams files to `/api/upload`.
- Periodic polling (e.g. every 3–5 seconds) of `/api/documents` to update document list and parsing status.
- Async chat submission, displaying a typing placeholder while calling `/api/query`.
- Text formatter that renders Markdown using `marked.js` and LaTeX formulas using `KaTeX` before displaying messages.
- Citation parser: identifies references like `[1]` in the text and hooks click events that display a detailed popover/tooltip showing the source file name and matching snippet.

---

## Verification Plan

### Automated Tests
We will verify basic API routes by creating a mock test suite or using python shell scripts in `tests`:
- Verify `/api/documents` returns empty array initially.
- Mock the file upload to verify the background task triggers.
- Run `pytest` to ensure no existing tests are broken.

### Manual Verification
1. Run `python run_web.py` to start the app and open the browser.
2. Drag and drop a sample PDF (e.g. `docs/changes/dashboard/spec_pack.md` or a sample document).
3. Confirm the sidebar file list shows `Đang xử lý` (processing) and then `Thành công` (success) when done.
4. Enter a query inside the document scope (e.g., "Các yêu cầu của FastAPI là gì?") and verify the response renders with LaTeX/Markdown and citations.
5. Click a citation tag and check if the matching source text is shown.
6. Enter an out-of-scope question (e.g., "Hôm nay thời tiết thế nào?") and verify that the AI returns the exact fallback response defined in **BR-6**: *"Tôi không tìm thấy thông tin y khoa này trong các tài liệu/bệnh án được tải lên của phòng khám. Vui lòng bổ sung thêm tài liệu chuyên môn liên quan."*
