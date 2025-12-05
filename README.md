# RAG-implement

**Abstract**: 本專案參考 國立政治大學蔡炎龍教授的線上課程【生成式 AI】07.檢索增強生成(RAG)的原理及實作，建立一套可部署的 RAG（Retrieval-Augmented Generation）示範系統：將 Notion 筆記自動化的方式匯出 PDF 內容，並轉為切段文件，使用 Hugging Face 的 E5 多語向量模型產生嵌入，並以 Chroma 作為預設向量資料庫（同時保留蔡炎龍教授教材使用的本地 FAISS 的選項）。為提升在雲端 PaaS 的相容性，刻意移除需系統編譯的 `pycairo` 等套件，改以 Chroma 備援並提供預建 `chroma_db.zip` 以便部署。Streamlit 提供簡易 Chat UI、測試題庫與模型後備機制（Groq 可選、OpenAI 後備），目前已在本地完成索引與基本驗證，適合作為小型 RAG 示範或上手範本。

**Quick Start**

- **建立 Python venv**: 在專案根目錄執行：

```
python -m venv venv
\venv\Scripts\Activate.ps1
```

- **安裝套件**: 使用已整理的 `requirements.txt`：

```
python -m pip install -r requirements.txt
```

- **建立向量資料庫（選項）**: 若需從 `uploaded_docs/` 建立 Chroma DB：

```
python .\rag01_create_chroma_db.py
```

- **執行 Demo（Streamlit）**: 啟動應用並在瀏覽器開啟 `http://localhost:8501`：

```
streamlit run rag_streamlit_app.py
```

**Demo 連結**

- 本地測試：`http://localhost:8501`（啟動後開啟）
- 若已部署至平台，請將對應的公開 URL 填入此處或於部署平台查詢。

**Notes / 部署建議**

- 若部署環境無法安裝 FAISS 或編譯系統套件，請把預建的 `chroma_db.zip` 解壓至應用根目錄 `chroma_db/`，應用會自動載入 Chroma。
- 若需要 PDF 呈現功能，建議使用 Playwright（需允許下載瀏覽器二進位檔），或在無瀏覽器環境改以 Markdown 回退。
- 若要我幫忙 commit 並 push 這份 README，請回覆 `commit`，我會代為執行。
