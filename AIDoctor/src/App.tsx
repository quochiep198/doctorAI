import { useState, useEffect, useRef } from 'react';
import type { FormEvent, MouseEvent } from 'react';
import { marked } from 'marked';
import katex from 'katex';

// Types
interface DocumentItem {
  id?: string;
  filename: string;
  status: 'processing' | 'success' | 'failed';
  error: string | null;
  uploaded_at: string;
}

interface Citation {
  id: string;
  source_file: string;
  snippet: string;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  isThinking?: boolean;
  isError?: boolean;
}

interface PopoverState {
  visible: boolean;
  sourceFile: string;
  snippet: string;
  top: number;
  left: number;
}

export default function App() {
  // States
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [tempDocs, setTempDocs] = useState<DocumentItem[]>([]);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      text: 'Chào Bác sĩ, tôi là **Doctor AI**. Hãy tải lên các tài liệu y khoa (bệnh án bệnh nhân, danh mục thuốc phòng khám, phác đồ điều trị...) và đặt câu hỏi để tôi tra cứu thông tin y khoa chính xác.'
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [queryMode, setQueryMode] = useState('hybrid');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isInitialLoadingDocs, setIsInitialLoadingDocs] = useState(true);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [activeCitations, setActiveCitations] = useState<Record<string, Citation>>({});
  const [popover, setPopover] = useState<PopoverState>({
    visible: false,
    sourceFile: '',
    snippet: '',
    top: 0,
    left: 0
  });

  // Refs
  const fileInputRef = useRef<HTMLInputElement>(null);
  const chatMessagesRef = useRef<HTMLDivElement>(null);

  // Fetch document list
  const fetchDocuments = async (isInitial = false) => {
    try {
      const res = await fetch('/api/documents');
      if (!res.ok) {
        if (isInitial) setIsInitialLoadingDocs(false);
        return;
      }
      const data = await res.json();
      if (data.documents) {
        setDocuments(data.documents);
        
        // Remove completed temp items if they now exist in fetched list
        setTempDocs(prev => 
          prev.filter(td => !data.documents.some((d: DocumentItem) => d.filename === td.filename))
        );
      }
    } catch (err) {
      console.error('Error fetching documents:', err);
    } finally {
      if (isInitial) setIsInitialLoadingDocs(false);
    }
  };

  // Initial load and polling
  useEffect(() => {
    fetchDocuments(true);
    const interval = setInterval(() => fetchDocuments(false), 4000);
    return () => clearInterval(interval);
  }, []);

  // Scroll to bottom on new messages
  useEffect(() => {
    if (chatMessagesRef.current) {
      chatMessagesRef.current.scrollTop = chatMessagesRef.current.scrollHeight;
    }
  }, [messages]);

  // Click outside citation popover to close it
  useEffect(() => {
    const handleGlobalClick = (e: globalThis.MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('.citation-popover') && !target.closest('.citation-ref')) {
        setPopover(prev => prev.visible ? { ...prev, visible: false } : prev);
      }
    };
    document.addEventListener('click', handleGlobalClick);
    return () => document.removeEventListener('click', handleGlobalClick);
  }, []);

  // Combined documents view
  const allDocuments = [
    ...tempDocs,
    ...documents.filter(d => !tempDocs.some(td => td.filename === d.filename))
  ];

  // File Upload Handlers
  const triggerFileInput = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      handleFilesUpload(e.target.files);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files) {
      handleFilesUpload(e.dataTransfer.files);
    }
  };

  const handleFilesUpload = async (files: FileList) => {
    if (!files || files.length === 0) return;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      
      const newTempDoc: DocumentItem = {
        filename: file.name,
        status: 'processing',
        error: null,
        uploaded_at: new Date().toISOString()
      };
      
      // Prepend temp processing item
      setTempDocs(prev => [newTempDoc, ...prev]);

      const formData = new FormData();
      formData.append('file', file);

      try {
        const res = await fetch('/api/upload', {
          method: 'POST',
          body: formData
        });
        
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || 'Upload thất bại');
        }
        
        // Remove file from temp queue and refresh document list
        setTempDocs(prev => prev.filter(d => d.filename !== file.name));
        fetchDocuments();
      } catch (err: any) {
        console.error(`Error uploading ${file.name}:`, err);
        setTempDocs(prev => prev.map(d => {
          if (d.filename === file.name) {
            return {
              ...d,
              status: 'failed',
              error: err.message || 'Lỗi upload'
            };
          }
          return d;
        }));
      }
    }
  };

  // Delete Document Handler
  const handleDeleteDocument = async (doc: DocumentItem) => {
    if (!doc.id) return;

    if (!window.confirm(`Bạn có chắc chắn muốn xóa tài liệu "${doc.filename}" khỏi cơ sở dữ liệu y khoa của phòng khám không?`)) {
      return;
    }

    setIsDeleting(true);

    try {
      const res = await fetch(`/api/documents/${encodeURIComponent(doc.id)}`, {
        method: 'DELETE',
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Xóa thất bại');
      }

      // Optimistically remove the document from local state
      setDocuments(prev => prev.filter(d => d.id !== doc.id));
      
      // Refresh documents
      await fetchDocuments(false);
    } catch (err: any) {
      console.error(`Error deleting document ${doc.filename}:`, err);
      alert(`Lỗi khi xóa tài liệu: ${err.message}`);
    } finally {
      setIsDeleting(false);
    }
  };

  // Chat Submission
  const handleChatSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const query = inputValue.trim();
    if (!query) return;

    setInputValue('');

    const userMessageId = `user-${Date.now()}`;
    const assistantMessageId = `assistant-${Date.now()}`;

    // 1. Add User Message
    setMessages(prev => [
      ...prev,
      { id: userMessageId, role: 'user', text: query }
    ]);

    // 2. Add Thinking Message
    setMessages(prev => [
      ...prev,
      { id: assistantMessageId, role: 'assistant', text: '', isThinking: true }
    ]);

    try {
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, mode: queryMode })
      });

      const data = await res.json();
      
      if (!res.ok) {
        throw new Error(data.detail || 'Query failed');
      }

      // Update active citations
      if (data.citations) {
        const newCitations = { ...activeCitations };
        data.citations.forEach((cit: Citation) => {
          newCitations[cit.id] = cit;
        });
        setActiveCitations(newCitations);
      }

      // Replace Thinking Message with actual response
      setMessages(prev => 
        prev.map(m => m.id === assistantMessageId ? {
          ...m,
          text: data.answer,
          isThinking: false
        } : m)
      );

    } catch (err: any) {
      console.error('Query error:', err);
      // Replace Thinking Message with error response
      setMessages(prev => 
        prev.map(m => m.id === assistantMessageId ? {
          ...m,
          text: `<span style="color: var(--accent-red)"><i class="fa-solid fa-triangle-exclamation"></i> Có lỗi xảy ra: ${err.message}</span>`,
          isThinking: false,
          isError: true
        } : m)
      );
    }
  };

  // Click on citation in chat container
  const handleChatContainerClick = (e: MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;
    const citationRef = target.closest('.citation-ref');
    if (!citationRef) return;

    const refId = citationRef.getAttribute('data-ref-id');
    if (!refId) return;

    const citation = activeCitations[refId];
    if (citation) {
      const rect = citationRef.getBoundingClientRect();
      let top = window.scrollY + rect.bottom + 8;
      let left = window.scrollX + rect.left - 10;
      
      // Bounds check if popover goes offscreen
      const popoverWidth = 320;
      if (left + popoverWidth > window.innerWidth) {
        left = window.innerWidth - popoverWidth - 16;
      }

      setPopover({
        visible: true,
        sourceFile: citation.source_file,
        snippet: citation.snippet,
        top,
        left
      });
      
      e.stopPropagation();
    }
  };

  // Formatter for LaTeX + Markdown + Citations
  const renderFormattedContent = (text: string) => {
    if (!text) return '';
    
    // 1. Render Block LaTeX $$ ... $$
    let formatted = text.replace(/\$\$([\s\S]+?)\$\$/g, (match, formula) => {
      try {
        return `<div class="katex-block">${katex.renderToString(formula.trim(), { displayMode: true, throwOnError: false })}</div>`;
      } catch (e) {
        return match;
      }
    });
    
    // 2. Render Inline LaTeX $ ... $
    formatted = formatted.replace(/\$([\s\S]+?)\$/g, (match, formula) => {
      try {
        return `<span class="katex-inline">${katex.renderToString(formula.trim(), { displayMode: false, throwOnError: false })}</span>`;
      } catch (e) {
        return match;
      }
    });

    // 3. Render Markdown
    try {
      const parsed = marked.parse(formatted);
      formatted = typeof parsed === 'string' ? parsed : (parsed as any).toString();
    } catch (err) {
      console.error('Markdown parse error:', err);
    }

    // 4. Render Citations [1], [2], [doc-xxx] -> make clickable
    formatted = formatted.replace(/\[([a-zA-Z0-9\._-]+)\]/g, (_, refId) => {
      return `<span class="citation-ref" data-ref-id="${refId}">[${refId}]</span>`;
    });

    return formatted;
  };

  // Helper for document item icons
  const getDocIcon = (filename: string) => {
    const filenameLower = filename.toLowerCase();
    if (filenameLower.endsWith('.pdf')) return 'fa-file-pdf';
    if (filenameLower.endsWith('.docx') || filenameLower.endsWith('.doc')) return 'fa-file-word';
    if (filenameLower.endsWith('.xlsx') || filenameLower.endsWith('.xls')) return 'fa-file-excel';
    if (filenameLower.endsWith('.pptx') || filenameLower.endsWith('.ppt')) return 'fa-file-powerpoint';
    if (/\.(png|jpg|jpeg|gif|webp)$/.test(filenameLower)) return 'fa-file-image';
    return 'fa-file-lines';
  };

  return (
    <div className="app-container">
      {/* Top Navigation / Header */}
      <header className="app-header">
        <div className="header-logo">
          <i className="fa-solid fa-heart-pulse logo-icon"></i>
          <h1>DOCTOR AI — TRỢ LÝ Y KHOA</h1>
        </div>
        <div className="header-actions">
          <button className="settings-btn" onClick={() => setIsSettingsOpen(true)}>
            <i className="fa-solid fa-gear"></i> Cấu hình
          </button>
        </div>
      </header>

      {/* Main Workspace: Split columns */}
      <main className="app-workspace">
        {/* Sidebar: Document upload and status */}
        <aside className="sidebar-column">
          <div className="column-header">
            <div>
              <i className="fa-solid fa-folder-open"></i>{' '}
              <h2>HỒ SƠ & TÀI LIỆU Y KHOA</h2>
            </div>
          </div>
          
          {/* Drag and Drop Zone */}
          <div 
            className={`upload-zone ${isDragOver ? 'dragover' : ''}`}
            onClick={triggerFileInput}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <input 
              type="file" 
              ref={fileInputRef} 
              onChange={handleFileChange} 
              multiple 
              style={{ display: 'none' }} 
            />
            <i className="fa-solid fa-cloud-arrow-up upload-icon"></i>
            <p className="upload-title">Kéo & Thả file vào đây</p>
            <p className="upload-subtitle">hoặc nhấn để chọn từ máy tính</p>
            <p className="upload-hint">PDF, Word, Excel, TXT, MD, Hình ảnh (tối đa 50MB)</p>
          </div>
          
          {/* Upload Progress / File Status List */}
          <div className="document-list-container">
            <h3>TÀI LIỆU PHÒNG KHÁM ĐÃ TẢI LÊN</h3>
            <div className="document-list">
              {isInitialLoadingDocs ? (
                <div className="loading-docs-state">
                  <i className="fa-solid fa-spinner spinner-icon"></i>
                  <p>Đang tải tài liệu phòng khám...</p>
                </div>
              ) : allDocuments.length === 0 ? (
                <div className="empty-docs-state">
                  <i className="fa-solid fa-file-medical"></i>
                  <p>Chưa có tài liệu nào được tải lên</p>
                </div>
              ) : (
                allDocuments.map((doc, idx) => (
                  <div className="doc-item" key={`${doc.filename}-${idx}`}>
                    <div className="doc-info">
                      <i className={`fa-solid ${getDocIcon(doc.filename)} doc-icon`}></i>
                      <span className="doc-name" title={doc.filename}>{doc.filename}</span>
                    </div>
                    <div className="doc-actions">
                      {doc.status === 'success' && (
                        <span className="status-indicator success">
                          <i className="fa-solid fa-circle-check"></i> Thành công
                        </span>
                      )}
                      {doc.status === 'failed' && (
                        <span className="status-indicator failed" title={doc.error || 'Lập chỉ mục thất bại'}>
                          <i className="fa-solid fa-circle-exclamation"></i> Lỗi
                        </span>
                      )}
                      {doc.status === 'processing' && (
                        <span className="status-indicator processing">
                          <i className="fa-solid fa-spinner spinner-icon"></i> Đang index
                        </span>
                      )}
                      {doc.id && (
                        <button
                          className="delete-doc-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteDocument(doc);
                          }}
                          title="Xóa tài liệu"
                        >
                          <i className="fa-solid fa-trash-can"></i>
                        </button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </aside>

        {/* Chat Panel: AI Query and Chat area */}
        <section className="chat-column">
          <div className="column-header">
            <div className="header-left">
              <i className="fa-solid fa-comments"></i>{' '}
              <h2>HỎI ĐÁP Y KHOA</h2>
            </div>
            
            {/* Query Mode Options */}
            <div className="query-modes">
              <label htmlFor="queryModeSelect">Chế độ AI:</label>
              <select 
                id="queryModeSelect"
                value={queryMode}
                onChange={(e) => setQueryMode(e.target.value)}
              >
                <option value="hybrid">Hybrid (Đồ thị + Vector)</option>
                <option value="local">Local (Ngữ nghĩa cục bộ)</option>
                <option value="global">Global (Toàn cục đồ thị)</option>
                <option value="naive">Naive (Chỉ Vector DB)</option>
                <option value="mix">Mix (Đồ thị & Vector lai)</option>
                <option value="bypass">Bypass (LLM trực tiếp)</option>
              </select>
            </div>
          </div>

          {/* Messages Log */}
          <div 
            className="chat-messages" 
            ref={chatMessagesRef}
            onClick={handleChatContainerClick}
          >
            {messages.map((m) => (
              <div className={`message ${m.role}`} key={m.id}>
                <div className="message-avatar">
                  <i className={m.role === 'user' ? 'fa-solid fa-user' : 'fa-solid fa-user-doctor'}></i>
                </div>
                <div className="message-content">
                  {m.isThinking ? (
                    <div className="thinking-indicator">
                      <div className="thinking-dot"></div>
                      <div className="thinking-dot"></div>
                      <div className="thinking-dot"></div>
                    </div>
                  ) : m.isError ? (
                    <div dangerouslySetInnerHTML={{ __html: m.text }} />
                  ) : (
                    <div dangerouslySetInnerHTML={{ __html: renderFormattedContent(m.text) }} />
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Chat Input Form */}
          <form className="chat-input-form" onSubmit={handleChatSubmit}>
            <textarea 
              id="chatInput" 
              placeholder="Nhập câu hỏi y khoa cần tra cứu từ hồ sơ phòng khám..." 
              rows={2}
              required
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleChatSubmit(e);
                }
              }}
            ></textarea>
            <button type="submit" className="send-btn" id="sendBtn">
              <i className="fa-solid fa-paper-plane"></i>
            </button>
          </form>
        </section>
      </main>

      {/* Citations Tooltip / Modal Popover */}
      {popover.visible && (
        <div 
          className="citation-popover"
          style={{
            display: 'block',
            top: `${popover.top}px`,
            left: `${popover.left}px`
          }}
        >
          <div className="popover-header">
            <span className="popover-title">Đoạn trích nguồn tài liệu</span>
            <button 
              className="popover-close" 
              onClick={() => setPopover(prev => ({ ...prev, visible: false }))}
            >
              &times;
            </button>
          </div>
          <div className="popover-body">
            <div className="popover-meta">
              <strong>Nguồn:</strong> <span>{popover.sourceFile}</span>
            </div>
            <div 
              className="popover-text"
              dangerouslySetInnerHTML={{ __html: renderFormattedContent(popover.snippet) }}
            />
          </div>
        </div>
      )}

      {/* Configuration Modal overlay */}
      {isSettingsOpen && (
        <div className="modal-overlay" onClick={() => setIsSettingsOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2><i className="fa-solid fa-gear"></i> Cấu hình hệ thống Trợ lý</h2>
              <button className="modal-close" onClick={() => setIsSettingsOpen(false)}>&times;</button>
            </div>
            <div className="modal-body">
              <p className="config-desc">Doctor AI sử dụng thư viện RAG-Anything kết hợp LightRAG để lập chỉ mục tài liệu đa phương tiện y khoa.</p>
              <div className="config-status-card">
                <h3>Trạng thái kết nối</h3>
                <div className="status-row">
                  <span>Lõi RAG-Anything:</span>
                  <span className="status-badge success">
                    <i className="fa-solid fa-circle-check"></i> Đang hoạt động
                  </span>
                </div>
                <div className="status-row">
                  <span>Phương pháp Parser:</span>
                  <span className="status-value font-mono">MinerU (PDF Layout Analysis)</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {isDeleting && (
        <div className="modal-overlay" style={{ zIndex: 1100 }}>
          <div className="loading-modal-content">
            <i className="fa-solid fa-spinner spinner-icon loading-modal-spinner"></i>
            <h3>Đang xóa tài liệu y khoa...</h3>
            <p>Hệ thống đang loại bỏ dữ liệu chỉ mục và đồng bộ lại đồ thị tri thức.</p>
          </div>
        </div>
      )}
    </div>
  );
}
