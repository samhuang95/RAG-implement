import os
import shutil
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader, PyPDFLoader, UnstructuredWordDocumentLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from huggingface_hub import login

# Load environment variables
load_dotenv()

# 1. 建立資料夾
upload_dir = "uploaded_docs"
os.makedirs(upload_dir, exist_ok=True)
print(f"請將你的 .txt, .pdf, .docx 檔案放到這個資料夾中： {upload_dir}")

# Check if directory is empty
if not os.listdir(upload_dir):
    print(f"警告: {upload_dir} 資料夾是空的。請放入文件後再執行此程式。")
    # We can choose to exit or continue (which will result in empty vector db)
    # exit()

# 3. 改用 E5 模型 (因為 Gemma 是 gated model，需要特殊權限)
class E5Embeddings(HuggingFaceEmbeddings):
    def __init__(self, **kwargs):
        super().__init__(
            model_name="intfloat/multilingual-e5-large",
            encode_kwargs={"normalize_embeddings": True},
            **kwargs
        )

    def embed_documents(self, texts):
        # E5 文件前綴
        texts = [f'passage: {t}' for t in texts]
        return super().embed_documents(texts)

    def embed_query(self, text):
        # E5 查詢前綴
        return super().embed_query(f'query: {text}')

# ... (rest of the code)

# 4. 載入文件
folder_path = upload_dir
documents = []
for file in os.listdir(folder_path):
    path = os.path.join(folder_path, file)
    if file.endswith(".txt"):
        loader = TextLoader(path, encoding='utf-8')
    elif file.endswith(".pdf"):
        loader = PyPDFLoader(path)
    elif file.endswith(".docx"):
        loader = UnstructuredWordDocumentLoader(path)
    else:
        continue
    documents.extend(loader.load())

if not documents:
    print("沒有載入任何文件。結束程式。")
    exit()

print(f"已載入 {len(documents)} 份文件。")

# 5. 建立向量資料庫
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
split_docs = splitter.split_documents(documents)
print(f"已分割成 {len(split_docs)} 個區塊。")

# Login to HuggingFace
hf_token = os.getenv('HUGGINGFACE_TOKEN')
if hf_token:
    login(token=hf_token)
else:
    print("警告: 未找到 HUGGINGFACE_TOKEN 環境變數。")

embedding_model = E5Embeddings()
vectorstore = FAISS.from_documents(split_docs, embedding_model)

# 6. 儲存向量資料庫
vectorstore.save_local("faiss_db")
print("✅ 向量資料庫已儲存為 'faiss_db' 資料夾。")

# Optional: Zip the folder if needed (mimicking the notebook)
shutil.make_archive("faiss_db", 'zip', "faiss_db")
print("✅ 向量資料庫已壓縮為 'faiss_db.zip'。")
