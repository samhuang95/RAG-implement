專案紀錄：RAG-implement

日期：2025-12-06

目的

- 將會話摘要、已執行的操作、偵錯紀錄與後續建議整理成中文記錄，方便團隊檢閱與部署參考。內容包含將 Notebook 轉為 Python 腳本、建立向量資料庫、調整相依套件以避免雲端部署建置失敗，以及 Streamlit 示範頁面相關修改。

已執行的重點操作（時序摘要）

- 新增 `rag01_create_chroma_db.py`：從 `uploaded_docs` 建立 Chroma 向量索引，並產生 `chroma_db/` 與 `chroma_db.zip`。

  - 本地執行指令（在 venv）：`python .\rag01_create_chroma_db.py`。
  - 產物與大小（本地）：
    - `chroma_db.zip`：2,569,663 bytes（約 2.45 MB）
    - `chroma_db\chroma.sqlite3`：4,120,576 bytes（約 3.93 MB）

- 修改 `rag_streamlit_app.py`：

  - 將預設 FAISS 路徑改為 `chroma_db`，並加入當 FAISS 不可用時載入 Chroma 的備援程式碼。
  - 新增 Demo 用預設問題的 UI：選擇後自動填入聊天輸入框（使用者需按 `Send` 才會送出）。

- 解決雲端建置錯誤（pycairo/rlPyCairo）的處理：
  - 從 `requirements.txt` 移除下列套件，以避免在無法取得系統 Cairo / pkg-config 的環境中觸發編譯失敗：
    - `pycairo==1.29.0`
    - `rlPyCairo==0.4.0`
    - `svglib==1.6.0`（由 `xhtml2pdf` 拉入）
    - `xhtml2pdf==0.2.17`
  - 變更已 commit 並推送至 `origin/main`，以避免雲端部署嘗試編譯上述套件。

偵錯紀錄與處理細節

- 問題描述：在安裝 `pycairo` 時，pip/meson 顯示找不到 `pkg-config`、`cairo` 或 `cmake`，導致在建立套件 metadata 時失敗（metadata-generation-failed）。
- 根本原因：`pycairo` 需要系統層級函式庫（Cairo）與工具（pkg-config），這些在許多 PaaS 上不可得或無法編譯。
- 套件依賴鏈：`xhtml2pdf` -> `svglib` -> `rlPyCairo` -> `pycairo`（此鏈條會觸發編譯步驟而失敗）。

- 採取措施：
  1. 移除會引發編譯的直接或間接相依以避免失敗（如上所列套件）。
  2. 提供 Chroma 作為向量資料庫備援，讓應用在不支援 FAISS 的環境中仍能運作。
  3. 保留 Playwright 作為 PDF 呈現選項，但將其視為可選項，主要依賴 Chroma 與 Streamlit 來提供 RAG 功能。
  4. 如果未來需要保留 pycairo，則可考慮在部署環境中安裝 MSYS2 並透過 pacman 安裝 cairo/pkg-config，或取得對應平台的 prebuilt wheel，但這兩個方案在多數雲端平台上較不方便。

已執行的主要指令（節錄）

- 啟用 venv：`.\venv\Scripts\Activate.ps1`
- 安裝 chromadb：`python -m pip install chromadb`
- 建立 Chroma DB：`python .\rag01_create_chroma_db.py`
- 安裝 requirements（修改後）：`python -m pip install -r requirements.txt`
- Git 操作：`git add`、`git commit -m`、`git push origin main`

變更過的檔案（主清單）

- `rag01_create_chroma_db.py`（新增）：建立並壓縮 Chroma DB。
- `rag_streamlit_app.py`（更新）：預設 DB 路徑改為 `chroma_db`、加入 Chroma 備援、移動 Demo 預設問題 UI。
- `requirements.txt`（更新）：移除可能導致雲端建置失敗的套件（pycairo / rlPyCairo / svglib / xhtml2pdf）。

本地驗證結果

- 執行 `python -m pip check`：結果 `No broken requirements found`（目前 venv 無套件衝突）。
- 已確認 `chroma_db/` 與 `chroma_db.zip` 存放於專案根目錄。

後續建議

1. 將 `chroma_db.zip` 上傳到雲端部署的檔案區或把 `chroma_db/` 直接放入 repo（若檔案大小允許），部署時解壓後即可讓應用載入 Chroma，避免在部署時安裝 FAISS 或編譯 pycairo。
2. 若需在雲端使用 PDF 渲染，採用 Playwright 時請確認部署平台允許下載瀏覽器二進位檔；若不允許，保留 Markdown 或其他簡單回退方案。
3. 若要獲得一份僅包含雲端相容套件的 `requirements.txt`，建議在乾淨的最小 venv 中安裝必要套件後再執行 `pip freeze`，以生成最簡化的部署清單。

---

若您希望我將此 `log.md` 一併 commit 並推上遠端，請回覆 `commit`；若要我直接生成更詳細的 changelog（包含 commit SHA 與差異），請告訴我，我會繼續處理。
**Project Log — RAG-implement**

**Date:** 2025-12-06

**Purpose**

- Capture the conversation summary, actions performed, debugging steps, and next steps for the `RAG-implement` workspace. This log consolidates the work done while converting notebooks to scripts, creating vector DBs, and preparing a Streamlit demo that avoids problematic system builds in cloud environments.

**High-level goals discussed**

- Convert notebooks to `.py` scripts and use `.env` for secrets.
- Build a RAG vector DB from uploaded PDFs and Notion exports.
- Provide a Streamlit UI for QA and make the app cloud-friendly (avoid faiss/pycairo/playwright install failures when possible).
- Create a Chroma fallback DB so the app can run without FAISS.

---

**Actions performed (chronological highlights)**

- Created `rag01_create_chroma_db.py` to build a persistent Chroma index from `uploaded_docs` and produce `chroma_db/` and `chroma_db.zip`.

  - Command run locally (inside venv):
    - `python .\rag01_create_chroma_db.py`
    - Output: created `chroma_db/` and `chroma_db.zip`.
  - Chroma artifacts (local sizes):
    - `chroma_db.zip`: 2,569,663 bytes (~2.45 MB)
    - `chroma_db\chroma.sqlite3`: 4,120,576 bytes (~3.93 MB)

- Updated Streamlit app `rag_streamlit_app.py`:

  - Default FAISS folder path changed to `chroma_db`.
  - Added Chroma fallback loading when FAISS isn't available.
  - Added demo preset QA UI (moved from sidebar into Chat area). Selecting a preset fills the chat input; user presses `Send` to run QA.

- Fixed dependency/build problems that caused pip/meson failures by removing problematic items from `requirements.txt`:
  - Removed `pycairo==1.29.0` and `rlPyCairo==0.4.0`.
  - Removed `svglib==1.6.0` (pulled by `xhtml2pdf`) to avoid indirectly pulling `rlPyCairo/pycairo`.
  - Removed `xhtml2pdf==0.2.17` for same reason (Playwright is available as a PDF rendering fallback and is optional for cloud deploys).
  - These edits were committed and pushed to `origin/main`.

---

**Debug / Error traces and remediation**

- Error: pycairo build failed due to missing system dependencies (pkg-config, cairo, cmake). Meson log and pip metadata-generation failed. This surfaced both locally and in cloud build logs.

  - Root cause: `pycairo` requires system-level Cairo and pkg-config (not always available on cloud PaaS); many environments cannot compile these C deps.

- Dependency chain causing the error:

  - `xhtml2pdf` -> `svglib` -> `rlPyCairo` -> `pycairo` → attempted source build → failed.

- Remediation steps taken:
  1. Remove direct `pycairo` / `rlPyCairo` entries from `requirements.txt`.
  2. Remove `svglib` and `xhtml2pdf` from `requirements.txt` to break the chain that pulls in pycairo.
  3. Provide a Chroma fallback and keep Playwright optional (Playwright may still need browser installs but is often supported or optional during local runs).
  4. If needed, alternate options were discussed: (A) install MSYS2 and system cairo/pkconfig to build pycairo, or (B) use prebuilt wheels — but these were not chosen for cloud-friendly setup.

---

**Commands executed (selected)**

- Activate venv: `.\venv\Scripts\Activate.ps1`
- Install chromadb: `python -m pip install chromadb`
- Create chroma DB: `python .\rag01_create_chroma_db.py`
- Re-generate/refresh requirements (some runs): `pip freeze --all > requirements.txt` (note: this at times re-added previously installed pycairo into `requirements.txt`, so a manual edit was necessary)
- Install from requirements (after edits): `python -m pip install -r requirements.txt`
- Git workflow used to record changes: `git add`, `git commit -m`, `git push origin main` (multiple commits recorded: removal of cairo packages and UI changes)

---

**Files changed**

- `rag01_create_chroma_db.py` — new script to create and zip Chroma DB.
- `rag_streamlit_app.py` — updated: default DB path changed to `chroma_db`, Chroma fallback loader, preset QA UI (moved into Chat area).
- `requirements.txt` — removed `pycairo`, `rlPyCairo`, `svglib`, `xhtml2pdf` to avoid cloud build errors.

---

**Local verification**

- After changes, executed `python -m pip check` — output: `No broken requirements found` in the current venv.
- Verified `chroma_db/` and `chroma_db.zip` exist at repo root.

---

**Next steps / Recommendations**

1. For cloud deploys (Streamlit Cloud / other PaaS): upload `chroma_db.zip` to repo root or the deployed app storage, extract it there so the app loads Chroma without installing FAISS or attempting to compile pycairo.
2. Keep Playwright usage optional for PDF rendering; prefer Playwright only when the environment supports browser installs. Provide Markdown fallback when Playwright/XHTML2PDF are unavailable.
3. If you need a fully-cleaned `requirements.txt` representing only cloud-compatible packages, consider regenerating `pip freeze` from a minimal venv and committing that list.

---

If you want, I can also commit `log.md` into the repo and push it. Do you want me to commit & push this file now? If yes, reply `commit` and I will push.
時間：2025/12/04 21:00:00
我詢問你的文字內容：
請幫我把這兩個檔案建立成兩個 .py 檔，
有需要任何 token 請幫我使用 .env 方式處理，然後使用 os.dot 的方式引用，
請注意，套件安裝與啟動的任務，請幫我使用我的 venv 環境中進行
你回覆給我的處理方式與內容，請簡述：

1. 建立 `requirements.txt` 並列出所有必要套件。
2. 建立 `.env` 檔案供設定 API Token。
3. 將 Jupyter Notebook 轉換為 `rag01_create_vector_db.py` (建立向量資料庫) 與 `rag02_rag_system.py` (RAG 系統)。
4. 在 venv 環境中安裝所有相依套件。

---

時間：2025/12/04 21:10:00
我詢問你的文字內容：
我現在已經把 .env 都設定完成了
我這邊有上傳一個 PDF 檔，請幫我執行建立 RAG DB
你回覆給我的處理方式與內容，請簡述：

1. 建立 `uploaded_docs` 資料夾並將 PDF 檔案移入。
2. 執行 `rag01_create_vector_db.py`。
3. 修正 `langchain` 引用錯誤 (ImportError)。
4. 遇到 Google Gemma 模型權限問題 (403 Forbidden)，將 Embedding 模型更換為開源且支援中文的 `intfloat/multilingual-e5-large`。
5. 成功建立向量資料庫 (`faiss_db`)。

---

時間：2025/12/04 21:20:00
我詢問你的文字內容：
我詢問問題的時候，出現錯誤訊息：
AttributeError: 'VectorStoreRetriever' object has no attribute 'get_relevant_documents'. Did you mean: '\_get_relevant_documents'?
你回覆給我的處理方式與內容，請簡述：
LangChain 新版已棄用 `get_relevant_documents`，將程式碼中的該方法替換為新的標準方法 `invoke`。

---

時間：2025/12/04 21:30:00
我詢問你的文字內容：
TypeError: Chatbot.**init**() got an unexpected keyword argument 'type'
你回覆給我的處理方式與內容，請簡述：
檢查發現 Gradio 版本為 6.0.2。移除 `gr.Chatbot()` 初始化時不被支援的 `type="messages"` 參數，但保留上一步驟修改的字典訊息格式，以符合新版 Gradio 的預設行為。

---

時間：2025/12/05 09:40:00 (Asia/Taipei, UTC+8)
我詢問你的文字內容：
Notion 匯出成 PDF 時內容不完整，請幫我修正並儲存日誌（請使用台灣時區）。
你回覆給我的處理方式與內容，請簡述：

1. 新增 `notion_sources.json` 作為多來源 mapping（放在 repo 根目錄），並把該檔加入 `.gitignore` 以避免提交敏感 mapping。
2. 修改 `rag03_notion_to_pdf.py`：
   - 改為從 `notion_sources.json` 讀取 mapping，可透過 `NOTION_SOURCE_JSON` env 指定路徑。
   - 強化 `extract_page_id_from_url()`：過濾非 hex 字元並取最後 32 個 hex 字元來組成 page id，處理 URL 斷行或額外字元導致的截斷問題。
   - 新增 `try_retrieve_page()` / `try_retrieve_database()` 助手，用多種 id 格式重試以降低 Notion SDK 的 uuid 驗證錯誤。
   - 新增 Markdown 清理（移除控制字元、將全形標點轉半形）以及使用 `fenced_code` + `codehilite` 以產生更穩定的 HTML。
   - 將 HTML->PDF 的主要渲染器改為 Playwright (Chromium)，並保留 xhtml2pdf 作為 fallback（提升 CSS/程式碼區塊與圖片的相容性與還原度）。
3. 在 venv 中安裝 `playwright` 並執行 `playwright install chromium`（Chromium 已下載並安裝完成）。
4. 以新的流程重新匯出 mapping 中的頁面，結果：
   - 成功匯出 `uploaded_docs/Github.pdf`。
   - 成功匯出 `uploaded_docs/Vue3 + Vite.pdf`（先前使用 xhtml2pdf 會失敗的頁面，改用 Playwright 可成功產出）。

補充建議：

- 我在開發階段保留部分 debug 印出（例如 `Mapping entry:`），如需可移除以讓輸出更乾淨。
- 建議將新匯出的 PDF 再執行 `rag01_create_vector_db.py` 以把它們索引進向量資料庫，若你同意我可以立即幫你執行該步驟。

---

```
---

時間：2025/12/04 21:30:00
我詢問你的文字內容：
TypeError: Chatbot.**init**() got an unexpected keyword argument 'type'
你回覆給我的處理方式與內容，請簡述：
檢查發現 Gradio 版本為 6.0.2。移除 `gr.Chatbot()` 初始化時不被支援的 `type="messages"` 參數，但保留上一步驟修改的字典訊息格式，以符合新版 Gradio 的預設行為。
```
