# Gói đặc tả — Xây dựng Ứng dụng Web Hỏi Đáp AI (RAG-Anything Web App)

> Tạo: 2026-08-03 · Giai đoạn: 1  
> **Nguồn tham chiếu duy nhất cho việc tích hợp giao diện Web và API.**  
> Không triển khai bất kỳ nội dung nào không được mô tả ở đây. Các điểm chưa rõ → Open Issues.

---

## 1. Bối cảnh / Mục đích
Hiện tại, dự án **RAG-Anything** là một thư viện/framework Python rất mạnh mẽ cho phép phân tích tài liệu y khoa đa phương tiện và xây dựng hệ thống hỏi đáp RAG (kết hợp Đồ thị tri thức + Vector DB). Tuy nhiên, dự án chưa có giao diện đồ họa trực quan (Web UI) hoặc hệ thống API server độc lập để bác sĩ và nhân viên phòng khám dễ dàng import hồ sơ bệnh án, phác đồ điều trị, danh mục thuốc và trò chuyện trực tiếp với AI trợ lý y khoa.

Mục đích của gói đặc tả này là định nghĩa chi tiết các yêu cầu kỹ thuật, cấu trúc API, và luồng giao diện người dùng nhằm đóng gói RAG-Anything thành một **Ứng dụng Trợ Lý Y Khoa Hỏi Đáp (Doctor AI) hoàn chỉnh**.

---

## 2. Phạm vi

### Trong phạm vi
*   **API Gateway (Backend - FastAPI):** 
    *   Tích hợp trực tiếp với framework RAG-Anything thông qua cơ chế bất đồng bộ (async).
    *   API Tải lên & Lập chỉ mục tài liệu (`/api/upload`).
    *   API Quản lý & Trạng thái tài liệu (`/api/documents`).
    *   API Hỏi đáp / Truy vấn (`/api/query`).
*   **Web Interface (Frontend - Single Page Application):**
    *   Giao diện responsive, phong cách thiết kế **Glassmorphism Premium Dark Mode**.
    *   Khu vực quản lý tài liệu (kéo thả upload file, danh sách file, trạng thái xử lý).
    *   Khung chat thông minh (hộp nhập câu hỏi, luồng lịch sử chat, hỗ trợ hiển thị Markdown, hiển thị công thức LaTeX trực quan, hiển thị nguồn tài liệu trích dẫn).
*   **Cấu hình linh hoạt:** Hỗ trợ cấu hình nhanh LLM qua file `.env` (OpenAI, Gemini API hoặc Ollama local).
*   **Deploy ở vercel và sử dụng neon db:**
### Ngoài phạm vi
*   **Quản lý người dùng đa người dùng (Multi-tenant):** Ứng dụng tập trung chạy local/single-user (dùng chung một cơ sở tri thức cho tất cả phiên chat).
*   **Chỉnh sửa lõi thuật toán RAG-Anything:** Chỉ gọi các hàm API công khai của thư viện `RAGAnything`.

---

## 3. Thuật ngữ

| #  | Thuật ngữ | Định nghĩa |
|----|-----------|------------|
| 1  | RAG (Retrieval-Augmented Generation) | Phương pháp cải thiện câu trả lời của AI bằng cách truy vấn thông tin từ tài liệu bên ngoài. |
| 2  | LightRAG | Cơ sở dữ liệu RAG thế hệ mới tích hợp Đồ thị tri thức (Knowledge Graph) và Vector DB. |
| 3  | MinerU | Công cụ phân tích cấu trúc tài liệu mặc định của RAG-Anything, trích xuất text, table, formula, và image. |
| 4  | Hybrid Retrieval | Chế độ tìm kiếm kết hợp cả cấu trúc đồ thị (quan hệ thực thể toàn cục) và vector (ngữ nghĩa cục bộ). |
| 5  | Citations (Trích dẫn) | Các thẻ liên kết hiển thị nguồn gốc của thông tin (tên file, đoạn văn bản gốc) được dùng để AI trả lời. |
| 6  | KaTeX / MathJax | Thư viện JS giúp render công thức toán học dạng LaTeX đẹp mắt trên web. |

---

## 4. Hiện trạng / Trạng thái mục tiêu

| #  | Khía cạnh | Hiện trạng | Trạng thái mục tiêu |
|----|-----------|------------|---------------------|
| 1  | Giao diện người dùng | Chỉ chạy qua CLI (dòng lệnh) hoặc viết script Python thủ công. | Giao diện Web 2 cột hiện đại, kéo thả upload file và chat trực quan. |
| 2  | Cơ chế API | Chưa có API server để tích hợp với ứng dụng khác. | API RESTful (FastAPI) tốc độ cao, hỗ trợ quản lý tài liệu và chat bất đồng bộ. |
| 3  | Trạng thái xử lý file | Người dùng phải theo dõi qua log terminal. | Danh sách tài liệu trên Sidebar hiển thị tiến trình: `Chờ xử lý` -> `Đang index` -> `Thành công / Lỗi`. |

---

## 5. Chi tiết đặc tả

### 5.1 Đặc tả API Backend (FastAPI)

#### 5.1.1 API Upload Tài Liệu (`POST /api/upload`)
*   **Mô tả:** Nhận file từ người dùng, lưu tạm vào thư mục `uploads/` và đưa vào luồng lập chỉ mục của RAG-Anything.
*   **Request:** `multipart/form-data` chứa file (chấp nhận `.pdf, .docx, .xlsx, .pptx, .txt, .md, .png, .jpg`).
*   **Response (JSON):**
    ```json
    {
      "success": true,
      "message": "File uploaded successfully. Indexing started.",
      "file_info": {
        "filename": "financial_report.pdf",
        "size_bytes": 1048576,
        "status": "processing"
      }
    }
    ```
*   **Business Rules:**
    *   **BR-1:** Giới hạn kích thước file tối đa 50MB.
    *   **BR-2:** Validate phần mở rộng file (chỉ chấp nhận danh sách định dạng được quy định trong config).
    *   **BR-3:** Lập chỉ mục phải được chạy dưới dạng **background task** (FastAPI `BackgroundTasks`) để tránh block HTTP response.

#### 5.1.2 API Danh Sách Tài Liệu (`GET /api/documents`)
*   **Mô tả:** Trả về danh sách tài liệu đã tải lên kèm trạng thái và ngày tạo.
*   **Response (JSON):**
    ```json
    {
      "documents": [
        {
          "filename": "financial_report.pdf",
          "status": "success",
          "uploaded_at": "2026-08-03T08:00:00Z"
        },
        {
          "filename": "schema.png",
          "status": "failed",
          "error": "OCR failed",
          "uploaded_at": "2026-08-03T08:05:00Z"
        }
      ]
    }
    ```

#### 5.1.3 API Trò Chuyện (`POST /api/query`)
*   **Mô tả:** Nhận câu hỏi y khoa và thực hiện truy vấn RAG-Anything để sinh câu trả lời từ dữ liệu phòng khám đã tải lên.
*   **Request Body (JSON):**
    ```json
    {
      "query": "Phác đồ điều trị viêm phổi cộng đồng ở trẻ em được khuyến cáo như thế nào?",
      "mode": "hybrid" // Tùy chọn: hybrid, naive, local, global
    }
    ```
*   **Response (JSON):**
    ```json
    {
      "answer": "Theo phác đồ điều trị (trang 5), thuốc kháng sinh hàng đầu được khuyến cáo cho viêm phổi cộng đồng không biến chứng ở trẻ em là Amoxicillin với liều 80-90 mg/kg/ngày chia 2 lần [1].",
      "citations": [
        {
          "id": 1,
          "source_file": "phac_do_dieu_tri_nhi_khoa.pdf",
          "snippet": "Lựa chọn kháng sinh ban đầu cho viêm phổi cộng đồng không biến chứng ở trẻ em là Amoxicillin liều cao..."
        }
      ]
    }
    ```
*   **Business Rules & System Prompts cho Query:**
    *   **BR-4 (Strict Context-Only):** AI chỉ được phép trả lời dựa trên các thông tin và ngữ cảnh y khoa đã trích xuất từ dữ liệu y tế phòng khám đã import (retrieved context).
    *   **BR-5 (No Hallucination/Out-of-Context):** Tuyệt đối không được tự bịa thông tin y tế bên ngoài hoặc sử dụng tri thức chung sẵn có của mô hình LLM để bổ sung cho câu trả lời ngoài phạm vi hồ sơ/phác đồ của phòng khám nhằm đảm bảo an toàn y khoa.
    *   **BR-6 (Fallback Response):** Nếu câu hỏi của bác sĩ không thể được trả lời bằng tài liệu y tế đã import, AI bắt buộc phải trả lời theo mẫu chuẩn: *"Tôi không tìm thấy thông tin y khoa này trong các tài liệu/bệnh án được tải lên của phòng khám. Vui lòng bổ sung thêm tài liệu chuyên môn liên quan."*

---

### 5.2 Đặc tả Giao diện Frontend (Single Page App)

#### 5.2.1 Sidebar - Quản lý tài liệu (Cột bên trái)
*   **Cơ chế Kéo thả (Drag & Drop Zone):** Người dùng có thể kéo thả nhiều file vào khu vực này để upload hàng loạt.
*   **Danh sách tài liệu:** Hiển thị danh sách file với biểu tượng đại diện loại file. Mỗi file có trạng thái tương ứng:
    *   `Đang xử lý` (biểu tượng loading xoay tròn).
    *   `Thành công` (dấu tick xanh).
    *   `Thất bại` (dấu chấm than đỏ, rê chuột vào hiển thị lý do lỗi).

#### 5.2.2 Cửa sổ Trò chuyện (Cột bên phải)
*   **Khu vực hiển thị tin nhắn (Chat Window):**
    *   Hiển thị tin nhắn người dùng và tin nhắn AI riêng biệt.
    *   AI response hỗ trợ render rich text (Markdown, in đậm, bảng biểu, danh sách).
    *   Tự động phát hiện công thức toán dạng `$$ formula $$` hoặc `$ formula $` để render thành ký tự toán học đẹp mắt nhờ thư viện KaTeX.
*   **Hiển thị trích dẫn (Citations):**
    *   Các thẻ nguồn trích dẫn như `[1]`, `[2]` xuất hiện trực tiếp trong văn bản.
    *   Khi người dùng click vào thẻ hoặc xem mục tham chiếu ở cuối tin nhắn, hệ thống sẽ mở một tooltip/modal hiển thị đoạn văn bản gốc đã trích dẫn để đối chiếu.

---

## 6. Yêu cầu phi chức năng

| #  | Danh mục | Yêu cầu |
|----|----------|---------|
| 1  | Trải nghiệm (UX) | Thời gian phản hồi chat (thời gian bắt đầu trả lời) phụ thuộc LLM, nhưng giao diện phải hiển thị trạng thái "AI đang suy nghĩ..." mượt mà. |
| 2  | Khả năng cài đặt | Đóng gói đơn giản. Người dùng chỉ cần chạy file script Python `run_web.py` để tự động khởi chạy FastAPI và mở trình duyệt web. |
| 3  | Bảo mật | Dữ liệu tài liệu upload chỉ lưu trữ local trong thư mục của hệ thống, không gửi đi bất kỳ server trung gian nào (ngoại trừ API của LLM cấu hình sẵn). |

---

## 7. Tiêu chí chấp nhận (Acceptance Criteria)

| #  | ID | Mô tả | Loại kiểm thử |
|----|----|-------|---------------|
| 1  | AC-QA-1 | Người dùng kéo thả file PDF vào Sidebar → File được upload thành công và hiển thị trạng thái `Đang xử lý`. | E2E |
| 2  | AC-QA-2 | Sau khi parser hoàn tất → Trạng thái chuyển sang `Thành công`. Cơ sở tri thức tự động cập nhật dữ liệu từ file mới. | E2E |
| 3  | AC-QA-3 | Người dùng gửi câu hỏi trên chat → Hệ thống gọi API `/api/query` và nhận về câu trả lời có tính liên quan trực tiếp đến tài liệu. | E2E |
| 4  | AC-QA-4 | Đoạn chat chứa bảng biểu markdown hoặc công thức toán LaTeX phải hiển thị đúng giao diện định dạng cột/ký tự toán, không lộ ký tự raw. | UI |
| 5  | AC-QA-5 | Khi thay đổi tham số trong file `.env` (ví dụ chuyển từ OpenAI sang Gemini), ứng dụng vẫn khởi chạy bình thường mà không cần sửa code. | IT |
| 6  | AC-QA-6 | Đặt câu hỏi ngoài phạm vi tài liệu (ví dụ: thời tiết, tin tức chung) → AI từ chối trả lời và phản hồi theo mẫu quy định tại BR-6, không bịa thông tin hoặc sử dụng tri thức ngoài. | E2E |

---

## 8. Ví dụ Luồng Người dùng

### Luồng thành công (Happy Path)
1.  Bác sĩ mở trang web → Giao diện Trợ Lý Y Khoa Dark Mode Premium mở ra, Sidebar trống.
2.  Bác sĩ kéo file `phac_do_dieu_tri_nhi_khoa.pdf` thả vào Sidebar.
3.  Hệ thống hiển thị trạng thái file là `Đang xử lý` kèm hiệu ứng loading. Sau 30 giây, trạng thái đổi thành `Thành công` kèm dấu tick xanh.
4.  Bác sĩ nhập câu hỏi vào hộp chat: "Liều dùng Paracetamol cho trẻ em là bao nhiêu?"
5.  Khung chat hiển thị tin nhắn AI đang suy nghĩ, sau đó in ra câu trả lời chi tiết lấy trực tiếp từ phác đồ điều trị nhi khoa, kèm chú thích trích dẫn `[1]` ở cuối câu.
6.  Bác sĩ bấm vào thẻ `[1]`, một panel nhỏ hiện ra hiển thị nội dung gốc từ trang 12 của file PDF.

---

## 9. Giao diện Wireframe ASCII (Premium Glassmorphism Layout)

```text
+------------------------------------------------------------------------------------+
|  🏥 DOCTOR AI - TRỢ LÝ Y KHOA                                       [⚙️ Settings]  |
+------------------------------------------------------+-----------------------------+
| 📂 HỒ SƠ & TÀI LIỆU Y KHOA                           | 💬 HỎI ĐÁP Y KHOA           |
|                                                      |                             |
| +--------------------------------------------------+ | +-------------------------+ |
| |  📥 Kéo & Thả file vào đây hoặc Chọn file        | | | [AI] Bác sĩ cần tra cứu | |
| |  Hỗ trợ PDF, Word, Excel, Hình ảnh...            | | | thông tin gì từ hồ sơ / | |
| +--------------------------------------------------+ | | phác đồ điều trị?       | |
|                                                      | |                           | |
| TÀI LIỆU PHÒNG KHÁM ĐÃ TẢI LÊN                       | | [Bác sĩ] Liều dùng của    | |
| ----------------------------------                   | | Paracetamol ở trẻ em?     | |
| 📄 Phac_Do_Dieu_Tri_Nhi.pdf   [✔️ Thành công]        | |                           | |
| 📊 Danh_Muc_Thuoc_BHYT.xlsx   [⏳ Đang index]        | | [AI] Theo phác đồ điều trị| |
| 📝 Tiep_Nhan_Benh_Nhan.docx   [❌ Lỗi: LibreOffice]   | | nhi khoa (trang 12), liều | |
|                                                      | | dùng là 10-15 mg/kg mỗi   | |
|                                                      | | 4-6 giờ [1].              | |
|                                                      | |                           | |
|                                                      | | ----------------------- | |
|                                                      | | [1] Phac_Do_Dieu_Tri_Nhi  | |
|                                                      | +-------------------------+ |
|                                                      | [ Nhập câu hỏi y khoa...  ] |
+------------------------------------------------------+-----------------------------+
```

---

## 10. Rủi ro & Biện pháp giảm thiểu

| #  | Rủi ro | Khả năng | Ảnh hưởng | Biện pháp giảm thiểu |
|----|--------|----------|-----------|----------------------|
| 1  | Parser MinerU tốn tài nguyên và nặng, dễ lỗi trên Windows do thiếu dependency C++ hoặc CUDA. | Cao | Nghiêm trọng | Nếu import `mineru` lỗi hoặc check installation thất bại, tự động chuyển sang chế độ parser đơn giản hơn (ví dụ: `pdfplumber` hoặc `paddleocr` có sẵn trong python). |
| 2  | Dung lượng Vector DB và Đồ thị tri thức tăng nhanh khi import nhiều tài liệu lớn. | Trung bình | Trung bình | Thiết lập cơ chế xóa bớt tài liệu cũ hoặc tối ưu hóa kích thước chunking (chunk_token_size). |
| 3  | Phản hồi chậm do xây dựng Đồ thị tri thức (Knowledge Graph) của LightRAG cần nhiều lượt gọi LLM. | Cao | Trung bình | Tích hợp cơ chế thông báo tiến trình rõ ràng cho người dùng ở giao diện, khuyến khích sử dụng chế độ query `naive` hoặc `local` để phản hồi nhanh hơn nếu không cần phân tích toàn cục. |
