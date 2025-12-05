import os
import shutil
from dotenv import load_dotenv

# Document loaders and splitters
from langchain_community.document_loaders import TextLoader, PyPDFLoader, UnstructuredWordDocumentLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Embeddings
from langchain_community.embeddings import HuggingFaceEmbeddings

# Try to import Chroma from community or core
try:
    from langchain_community.vectorstores import Chroma
except Exception:
    try:
        from langchain.vectorstores import Chroma
    except Exception:
        Chroma = None

# Load environment
load_dotenv()

# E5 embeddings wrapper (keeps passage/query prefixes)
class E5Embeddings(HuggingFaceEmbeddings):
    def __init__(self, **kwargs):
        super().__init__(
            model_name="intfloat/multilingual-e5-large",
            encode_kwargs={"normalize_embeddings": True},
            **kwargs,
        )

    def embed_documents(self, texts):
        texts = [f"passage: {t}" for t in texts]
        return super().embed_documents(texts)

    def embed_query(self, text):
        return super().embed_query(f"query: {text}")


def main():
    upload_dir = "uploaded_docs"
    if not os.path.exists(upload_dir):
        print(f"資料夾 '{upload_dir}' 不存在。請先將文件放到該資料夾後再執行。")
        return

    files = os.listdir(upload_dir)
    if not files:
        print(f"資料夾 '{upload_dir}' 目前為空。請放入 .txt/.pdf/.docx 文件後再執行。")
        return

    documents = []
    for fn in files:
        path = os.path.join(upload_dir, fn)
        if fn.lower().endswith('.txt'):
            loader = TextLoader(path, encoding='utf-8')
        elif fn.lower().endswith('.pdf'):
            loader = PyPDFLoader(path)
        elif fn.lower().endswith('.docx'):
            loader = UnstructuredWordDocumentLoader(path)
        else:
            print(f"跳過不支援的檔案: {fn}")
            continue
        try:
            docs = loader.load()
            documents.extend(docs)
            print(f"已載入 {fn} -> {len(docs)} 文件片段")
        except Exception as e:
            print(f"載入 {fn} 失敗: {e}")

    if not documents:
        print("沒有載入任何文件。結束。")
        return

    # split
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    split_docs = splitter.split_documents(documents)
    print(f"已分割成 {len(split_docs)} 個區塊。")

    # embeddings
    emb = E5Embeddings()

    if Chroma is None:
        print("找不到 Chroma vectorstore 套件 (chromadb). 請先安裝 chromadb。")
        return

    chroma_dir = "chroma_db"
    # Remove existing chroma dir if exists to create fresh index
    if os.path.exists(chroma_dir):
        print(f"發現既有 {chroma_dir}，將會覆寫它。")
        shutil.rmtree(chroma_dir)

    print("建立 Chroma 向量資料庫... 這可能需要一些時間（計算 embeddings）")
    try:
        vect = Chroma.from_documents(split_docs, embedding=emb, persist_directory=chroma_dir)
        try:
            vect.persist()
        except Exception:
            pass
        print(f"✅ Chroma 向量資料庫已儲存在 '{chroma_dir}'")
    except Exception as e:
        print(f"建立 Chroma 向量資料庫失敗: {e}")
        return

    # Optional: zip the folder to make uploading easier
    try:
        zip_name = "chroma_db"
        shutil.make_archive(zip_name, 'zip', chroma_dir)
        print(f"✅ 已將 '{chroma_dir}' 壓縮為 '{zip_name}.zip' 可供上傳部署。")
    except Exception as e:
        print(f"壓縮 chroma_db 失敗: {e}")


if __name__ == '__main__':
    main()
