import os
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
import aisuite as ai
import gradio as gr
from huggingface_hub import login

# Load environment variables
load_dotenv()

# Login to HuggingFace
hf_token = os.getenv('HUGGINGFACE_TOKEN')
if hf_token:
    login(token=hf_token)
else:
    print("警告: 未找到 HUGGINGFACE_TOKEN 環境變數。")

# 2. 自訂 E5 embedding 類別
class E5Embeddings(HuggingFaceEmbeddings):
    def __init__(self, **kwargs):
        super().__init__(
            model_name="intfloat/multilingual-e5-large",
            encode_kwargs={"normalize_embeddings": True},
            **kwargs
        )

    def embed_documents(self, texts):
        # E5 文件前綴
        texts = [f"passage: {t}" for t in texts]
        return super().embed_documents(texts)

    def embed_query(self, text):
        # E5 查詢前綴
        return super().embed_query(f"query: {text}")

# 3. 載入 faiss_db
if not os.path.exists("faiss_db"):
    print("錯誤: 找不到 'faiss_db' 資料夾。請先執行 rag01_create_vector_db.py 建立向量資料庫。")
    exit()

embedding_model = E5Embeddings()
vectorstore = FAISS.load_local(
    "faiss_db",
    embeddings=embedding_model,
    allow_dangerous_deserialization=True
)

retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

# 4. 設定好我們要的 LLM
# 這裡使用 Groq 服務
api_key = os.getenv('GROQ_API_KEY')
if not api_key:
    print("警告: 未找到 GROQ_API_KEY 環境變數。")
else:
    os.environ['GROQ_API_KEY'] = api_key

model = "groq:openai/gpt-oss-120b"
# base_url="https://api.groq.com/openai/v1" # Not used in aisuite call directly here

client = ai.Client()

# 5. prompt 設計
system_prompt = "你是我(Sam)的筆記管理人員，請根據資料來回應我的問題。請親切、簡潔並附帶具體建議。請用台灣習慣的中文回應。"

prompt_template = """
根據下列資料：
{retrieved_chunks}

回答使用者的問題：{question}

請根據資料內容回覆，若資料不足請告訴我(Sam)。
"""

# 6. 使用 RAG 來回應
chat_history = []

def chat_with_rag(user_input):
    global chat_history
    # 取回相關資料
    docs = retriever.invoke(user_input)
    retrieved_chunks = "\n\n".join([doc.page_content for doc in docs])

    # 將自定 prompt 套入格式
    final_prompt = prompt_template.format(retrieved_chunks=retrieved_chunks, question=user_input)

    # 用 AI Suite 呼叫語言模型
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": final_prompt},
            ]
        )
        answer = response.choices[0].message.content
    except Exception as e:
        answer = f"發生錯誤: {str(e)}"

    chat_history.append((user_input, answer))
    return answer

# 7. 用 Gradio 打造 Web App
with gr.Blocks() as demo:
    gr.Markdown("# AI 筆記管理人員")
    chatbot = gr.Chatbot()
    msg = gr.Textbox(placeholder="請輸入你的問題...")

    def respond(message, chat_history_local):
        chat_history_local.append({"role": "user", "content": message})
        response = chat_with_rag(message)
        chat_history_local.append({"role": "assistant", "content": response})
        return "", chat_history_local

    msg.submit(respond, [msg, chatbot], [msg, chatbot])

if __name__ == "__main__":
    demo.launch(debug=True)
