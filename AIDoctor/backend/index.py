import os
import shutil
import asyncio
import logging
import tempfile
import urllib.parse
from pathlib import Path
from typing import List, Dict, Any, Optional
from functools import partial

from dotenv import load_dotenv
# Load environment variables (searches for .env in parent directories automatically)
load_dotenv()

from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# RAG-Anything imports
from raganything import RAGAnything, RAGAnythingConfig
from lightrag import QueryParam
from lightrag.utils import EmbeddingFunc
from lightrag.llm.openai import openai_complete_if_cache, openai_embed

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("doctor_ai_api")

# Determine directories based on environment
IS_VERCEL = os.getenv("VERCEL") == "1"

if IS_VERCEL:
    UPLOAD_DIR = Path(tempfile.gettempdir()) / "uploads"
    WORKING_DIR = os.path.join(tempfile.gettempdir(), "rag_storage")
else:
    UPLOAD_DIR = Path("./uploads")
    WORKING_DIR = os.getenv("WORKING_DIR", "./rag_storage")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Helper: Parse Neon DB/PostgreSQL connection string
def parse_database_url():
    db_url = os.getenv("DATABASE_URL") or os.getenv("STORAGE_URL") or os.getenv("POSTGRES_URL")
    if not db_url:
        return
    
    logger.info("Parsing database URL for PostgreSQL configuration")
    try:
        parsed = urllib.parse.urlparse(db_url)
        os.environ["POSTGRES_HOST"] = parsed.hostname or "localhost"
        if parsed.port:
            os.environ["POSTGRES_PORT"] = str(parsed.port)
        else:
            os.environ["POSTGRES_PORT"] = "5432"
        os.environ["POSTGRES_USER"] = parsed.username or ""
        os.environ["POSTGRES_PASSWORD"] = parsed.password or ""
        os.environ["POSTGRES_DATABASE"] = parsed.path.lstrip("/") or ""
        os.environ["POSTGRES_DB"] = parsed.path.lstrip("/") or ""
        logger.info(f"PostgreSQL configured: host={os.environ['POSTGRES_HOST']}, db={os.environ['POSTGRES_DATABASE']}")
    except Exception as e:
        logger.error(f"Failed to parse database URL: {e}")

# Helper: Configure LLM & Embeddings based on env variables
def get_llm_funcs():
    llm_binding = os.getenv("LLM_BINDING", "openai").lower()
    llm_model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    vision_model = os.getenv("VISION_MODEL", "gpt-4o")
    
    api_key = os.getenv("LLM_BINDING_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    base_url = os.getenv("LLM_BINDING_HOST", "https://api.openai.com/v1")
    
    # Handle Gemini binding
    if llm_binding == "gemini":
        api_key = os.getenv("GEMINI_API_KEY", api_key)
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
        if not llm_model or llm_model.startswith("gpt"):
            llm_model = "gemini-1.5-flash"
        if not vision_model or vision_model.startswith("gpt"):
            vision_model = "gemini-1.5-flash"
            
    # Handle OpenRouter binding
    elif llm_binding == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY", api_key)
        base_url = "https://openrouter.ai/api/v1"
        if not llm_model or llm_model.startswith("gpt"):
            llm_model = "google/gemini-2.5-flash:free"
        if not vision_model or vision_model.startswith("gpt"):
            vision_model = "google/gemini-2.5-flash:free"
            
    # Handle Ollama binding
    elif llm_binding == "ollama":
        base_url = os.getenv("OLLAMA_HOST", "http://localhost:11434") + "/v1"
        api_key = "ollama"
        if not llm_model or llm_model.startswith("gpt"):
            llm_model = "llama3.2"
        if not vision_model or vision_model.startswith("gpt"):
            vision_model = "llama3.2"
            
    # Setup core LLM completion call
    async def llm_model_func(prompt, system_prompt=None, history_messages=[], **kwargs):
        temp = float(os.getenv("TEMPERATURE", "0"))
        timeout = int(os.getenv("TIMEOUT", "240"))
        return await openai_complete_if_cache(
            model=llm_model,
            prompt=prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            api_key=api_key,
            base_url=base_url,
            temperature=temp,
            timeout=timeout,
            **kwargs
        )
        
    # Setup VLM completion call for image processors
    async def vision_model_func(prompt, system_prompt=None, history_messages=[], image_data=None, messages=None, **kwargs):
        if messages:
            return await openai_complete_if_cache(
                model=vision_model,
                prompt="",
                system_prompt=None,
                history_messages=[],
                messages=messages,
                api_key=api_key,
                base_url=base_url,
                **kwargs
            )
        elif image_data:
            return await openai_complete_if_cache(
                model=vision_model,
                prompt="",
                system_prompt=None,
                history_messages=[],
                messages=[
                    {"role": "system", "content": system_prompt} if system_prompt else None,
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                api_key=api_key,
                base_url=base_url,
                **kwargs
            )
        else:
            return await llm_model_func(prompt, system_prompt, history_messages, **kwargs)
            
    # Setup Embedding call
    embed_binding = os.getenv("EMBEDDING_BINDING")
    if not embed_binding:
        if os.getenv("GEMINI_API_KEY"):
            embed_binding = "gemini"
        else:
            embed_binding = "openai"
    else:
        embed_binding = embed_binding.lower()
        
    embed_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
    embed_dim = int(os.getenv("EMBEDDING_DIM", "3072"))
    embed_base_url = os.getenv("EMBEDDING_BINDING_HOST", "https://api.openai.com/v1")
    embed_api_key = os.getenv("EMBEDDING_BINDING_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    
    if embed_binding == "gemini":
        embed_api_key = os.getenv("GEMINI_API_KEY", embed_api_key)
        embed_base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
        if not embed_model or embed_model.startswith("text-embedding-3") or embed_model == "text-embedding-3-large":
            embed_model = "text-embedding-004"
            embed_dim = 768
            
    elif embed_binding == "ollama":
        async def ollama_embedding_async(texts: List[str]) -> List[List[float]]:
            import ollama
            client = ollama.AsyncClient(host=os.getenv("OLLAMA_HOST", "http://localhost:11434"))
            response = await client.embed(model=embed_model, input=texts)
            return response.embeddings
            
        embedding_func = EmbeddingFunc(
            embedding_dim=embed_dim,
            max_token_size=8192,
            func=ollama_embedding_async
        )
        return llm_model_func, vision_model_func, embedding_func

    # Default OpenAI embedding function
    embedding_func = EmbeddingFunc(
        embedding_dim=embed_dim,
        max_token_size=8192,
        func=partial(
            openai_embed.func,
            model=embed_model,
            api_key=embed_api_key,
            base_url=embed_base_url
        )
    )
    
    return llm_model_func, vision_model_func, embedding_func

# Register a custom lightweight SimpleParser for environments without heavy PDF parsers
from raganything.parser import Parser, register_parser

class SimpleParser(Parser):
    def check_installation(self) -> bool:
        return True

    def parse_pdf(self, pdf_path: Path, output_dir=None, **kwargs) -> list:
        try:
            import pypdf
            reader = pypdf.PdfReader(str(pdf_path))
            content_list = []
            for page_idx, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    content_list.append({
                        "type": "text",
                        "text": text,
                        "page_idx": page_idx
                    })
            return content_list
        except Exception as e:
            logger.error(f"SimpleParser: Error parsing PDF: {e}")
            raise

    def parse_document(self, file_path: Any, **kwargs) -> list:
        file_path = Path(file_path)
        ext = file_path.suffix.lower()
        if ext == ".pdf":
            return self.parse_pdf(file_path, **kwargs)
        elif ext in self.TEXT_FORMATS:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    return [{"type": "text", "text": f.read(), "page_idx": 0}]
            except Exception as e:
                logger.error(f"SimpleParser: Error reading text file: {e}")
                raise
        else:
            return [{"type": "text", "text": f"Format {ext} parsing not implemented in SimpleParser", "page_idx": 0}]

try:
    register_parser("simple", SimpleParser)
    logger.info("Successfully registered custom SimpleParser")
except Exception as e:
    logger.error(f"Failed to register custom SimpleParser: {e}")

# Lazy loaded singleton RAGAnything instance
_rag_instance = None
_rag_lock = asyncio.Lock()

async def get_rag():
    global _rag_instance
    async with _rag_lock:
        if _rag_instance is None:
            # Parse connection URL
            parse_database_url()
            
            # Setup configuration
            config = RAGAnythingConfig(
                working_dir=WORKING_DIR,
                parser=os.getenv("PARSER", "simple"),
                parse_method=os.getenv("PARSE_METHOD", "auto"),
                enable_image_processing=os.getenv("ENABLE_IMAGE_PROCESSING", "true").lower() == "true",
                enable_table_processing=os.getenv("ENABLE_TABLE_PROCESSING", "true").lower() == "true",
                enable_equation_processing=os.getenv("ENABLE_EQUATION_PROCESSING", "true").lower() == "true",
            )
            
            # Obtain LLM & embed methods
            llm_model_func, vision_model_func, embedding_func = get_llm_funcs()
            
            # Check for PostgreSQL storage
            lightrag_kwargs = {}
            if os.getenv("POSTGRES_HOST"):
                logger.info("Initializing LightRAG with PGDocStatusStorage and other PostgreSQL adapters (using default file/memory graph storage)")
                lightrag_kwargs["kv_storage"] = "PGKVStorage"
                lightrag_kwargs["vector_storage"] = "PGVectorStorage"
                lightrag_kwargs["doc_status_storage"] = "PGDocStatusStorage"
                # Omit PGGraphStorage because Neon DB / standard cloud PG does not support the Apache AGE extension
                # We explicitly force NetworkXStorage to override any environment variables (like LIGHTRAG_GRAPH_STORAGE)
                lightrag_kwargs["graph_storage"] = "NetworkXStorage"
            
            _rag_instance = RAGAnything(
                config=config,
                llm_model_func=llm_model_func,
                vision_model_func=vision_model_func,
                embedding_func=embedding_func,
                lightrag_kwargs=lightrag_kwargs
            )
            
            # Ensure initialization is completed
            await _rag_instance._ensure_lightrag_initialized()
            
            # Patch all storage finalize methods to keep connection pool open
            if os.getenv("POSTGRES_HOST"):
                logger.info("Patching LightRAG storage finalize methods to maintain persistent PG connection pool")
                
                async def dummy_finalize(*args, **kwargs):
                    pass
                
                # Patch LightRAG storages
                for attr_name in dir(_rag_instance.lightrag):
                    try:
                        attr_val = getattr(_rag_instance.lightrag, attr_name, None)
                        if attr_val and hasattr(attr_val, "finalize") and callable(attr_val.finalize):
                            logger.info(f"Patching finalize for lightrag.{attr_name}")
                            attr_val.finalize = dummy_finalize
                    except Exception as e:
                        logger.warning(f"Failed to patch finalize for lightrag.{attr_name}: {e}")
                
                # Patch RAGAnything caches
                for cache_name in ["parse_cache", "multimodal_status_cache"]:
                    try:
                        cache_val = getattr(_rag_instance, cache_name, None)
                        if cache_val and hasattr(cache_val, "finalize") and callable(cache_val.finalize):
                            logger.info(f"Patching finalize for rag.{cache_name}")
                            cache_val.finalize = dummy_finalize
                    except Exception as e:
                        logger.warning(f"Failed to patch finalize for rag.{cache_name}: {e}")
            
        return _rag_instance


# FastAPI Setup
app = FastAPI(
    title="Doctor AI API",
    description="Backend API Gateway for RAG-Anything Trợ Lý Y Khoa",
    version="1.0"
)

# CORS Middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Models
class QueryRequest(BaseModel):
    query: str
    mode: str = "hybrid"

# Background task runner for processing files
async def process_uploaded_file(file_path: Path, filename: str):
    try:
        logger.info(f"Background task: Processing document {filename}...")
        rag = await get_rag()
        await rag.process_document_complete(str(file_path), file_name=filename)
        logger.info(f"Background task: Finished processing {filename}")
    except Exception as e:
        logger.error(f"Background task: Error processing {filename}: {e}", exc_info=True)


# 1. API: Upload document (POST /api/upload)
@app.post("/api/upload")
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    # Validate extension
    allowed_exts = {
        ".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md", ".png", ".jpg", ".jpeg"
    }
    file_path = Path(file.filename)
    ext = file_path.suffix.lower()
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Supported formats: {', '.join(allowed_exts)}"
        )
    
    # Save the file to temp location
    saved_path = UPLOAD_DIR / file.filename
    size_bytes = 0
    try:
        with open(saved_path, "wb") as buffer:
            # Read chunk by chunk to limit memory usage and check size limit (50MB)
            max_bytes = 50 * 1024 * 1024 # 50MB
            while chunk := await file.read(8192):
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    buffer.close()
                    saved_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File exceeds maximum allowed size of 50MB."
                    )
                buffer.write(chunk)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Error saving file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {str(e)}"
        )
    
    # Trigger background indexing
    background_tasks.add_task(process_uploaded_file, saved_path, file.filename)
    
    return {
        "success": True,
        "message": "File uploaded successfully. Indexing started.",
        "file_info": {
            "filename": file.filename,
            "size_bytes": size_bytes,
            "status": "processing"
        }
    }


# 2. API: Document list & status (GET /api/documents)
@app.get("/api/documents")
async def list_documents():
    try:
        rag = await get_rag()
        if not rag.lightrag or not rag.lightrag.doc_status:
            return {"documents": []}
            
        if hasattr(rag.lightrag.doc_status, "initialize"):
            await rag.lightrag.doc_status.initialize()
            
        try:
            docs_data, _ = await rag.lightrag.doc_status.get_docs_paginated(page=1, page_size=1000)
        finally:
            if hasattr(rag.lightrag.doc_status, "finalize"):
                await rag.lightrag.doc_status.finalize()
        
        doc_list = []
        for doc_id, doc_status_info in docs_data:
            if isinstance(doc_status_info, dict):
                status_str = doc_status_info.get("status", "unknown")
                file_path = doc_status_info.get("file_path", doc_id)
                uploaded_at = doc_status_info.get("created_at", "")
                error = doc_status_info.get("error_msg", "")
            else:
                status_str = getattr(doc_status_info, "status", "unknown")
                file_path = getattr(doc_status_info, "file_path", doc_id)
                uploaded_at = getattr(doc_status_info, "created_at", "")
                error = getattr(doc_status_info, "error_msg", "")
                if hasattr(status_str, "value"):
                    status_str = status_str.value
                    
            status_map = {
                "processing": "processing",
                "handling": "processing",
                "processed": "success",
                "success": "success",
                "failed": "failed"
            }
            mapped_status = status_map.get(str(status_str).lower(), "processing")
            
            doc_list.append({
                "filename": os.path.basename(file_path),
                "status": mapped_status,
                "error": error if mapped_status == "failed" else None,
                "uploaded_at": uploaded_at
            })
            
        return {"documents": doc_list}
    except Exception as e:
        logger.error(f"Error fetching document list: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query database statuses: {str(e)}"
        )


# 3. API: Medical assistant query (POST /api/query)
@app.post("/api/query")
async def query_rag(request: QueryRequest):
    fallback_response = "Tôi không tìm thấy thông tin y khoa này trong các tài liệu/bệnh án được tải lên của phòng khám. Vui lòng bổ sung thêm tài liệu chuyên môn liên quan."
    
    try:
        rag = await get_rag()
        mode = request.mode.lower()
        if mode not in ["hybrid", "naive", "local", "global", "mix", "bypass"]:
            mode = "hybrid"
            
        query_param = QueryParam(mode=mode)
        
        medical_system_prompt = (
            "You are a medical AI assistant. Your task is to answer the user's medical query based ONLY on the provided context "
            "(retrieved medical records, clinical guidelines, drug lists, etc.).\n\n"
            "Strict Rules:\n"
            "1. Only answer using the information directly found in the retrieved context. Do not use external knowledge or general LLM knowledge.\n"
            "2. Do not hallucinate or make up any medical information.\n"
            "3. If the retrieved context does not contain enough information to answer the question, or if the question is out of scope (e.g., weather, general news, or general knowledge not in the files), you MUST respond with this EXACT sentence, word-for-word, and absolutely nothing else:\n"
            f'"{fallback_response}"\n\n'
            "Do not add any preamble, explanation, or additional text if you cannot answer. Just output the fallback sentence."
        )
        
        logger.info(f"Executing query '{request.query[:50]}...' in mode '{mode}'")
        raw_result = await rag.lightrag.aquery_llm(
            request.query,
            param=query_param,
            system_prompt=medical_system_prompt
        )
        
        answer = ""
        if "llm_response" in raw_result:
            answer = raw_result["llm_response"].get("content") or ""
        
        chunks = raw_result.get("data", {}).get("chunks", [])
        
        if mode != "bypass" and len(chunks) == 0:
            logger.info("Zero context chunks retrieved. Returning strict fallback response.")
            return {
                "answer": fallback_response,
                "citations": []
            }
            
        citations = []
        for idx, chunk in enumerate(chunks):
            ref_id = chunk.get("reference_id") or str(idx + 1)
            file_path = chunk.get("file_path", "Tai_Lieu_Phong_Kham")
            content = chunk.get("content", "")
            
            citations.append({
                "id": ref_id,
                "source_file": os.path.basename(file_path),
                "snippet": content
            })
            
        answer_lower = answer.lower()
        if "không tìm thấy" in answer_lower or "xin lỗi" in answer_lower or "không thể trả lời" in answer_lower:
            answer = fallback_response
            citations = []
            
        return {
            "answer": answer.strip(),
            "citations": citations
        }
        
    except Exception as e:
        logger.error(f"Error querying RAGAnything: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while running query: {str(e)}"
        )

# Mount SPA frontend static files relative to this file
static_path = Path(__file__).parent.parent / "static"
if static_path.exists():
    app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static")
else:
    logger.warning(f"Static directory not found at {static_path}! SPA frontend will not be served.")
