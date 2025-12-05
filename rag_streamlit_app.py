import os
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from sentence_transformers import SentenceTransformer
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from sentence_transformers import SentenceTransformer
from langchain_community.vectorstores import FAISS

try:
    import aisuite as ai
except Exception:
    ai = None
import time


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


@st.cache_resource
def load_vectorstore(path="chroma_db"):
    emb = E5Embeddings()
    try:
        # FAISS deserialization uses pickle; allow only when loading trusted local DBs
        store = FAISS.load_local(path, emb, allow_dangerous_deserialization=True)
        return store
    except Exception as e:
        # If faiss python package is missing or FAISS can't be imported, try Chromadb fallback
        msg = str(e)
        if "faiss" in msg.lower() or isinstance(e, ModuleNotFoundError) or "Could not import faiss" in msg:
            try:
                # Try langchain_community first (some deployments use this package)
                try:
                    from langchain_community.vectorstores import Chroma
                except Exception:
                    try:
                        from langchain.vectorstores import Chroma
                    except Exception as e_import:
                        raise ImportError("Chroma vectorstore not found in langchain_community or langchain") from e_import

                chroma_dir = "chroma_db"
                if os.path.exists(chroma_dir):
                    store = Chroma(persist_directory=chroma_dir, embedding_function=emb)
                    st.warning("FAISS isn't available in this environment — using existing Chroma DB at 'chroma_db'.")
                    return store
                else:
                    st.error("FAISS not available and no 'chroma_db' found. Please run the indexing script locally to create a vectorstore or deploy with FAISS support.")
                    return None
            except Exception as e2:
                st.error(f"FAISS not available and Chroma fallback failed: {e2}")
                return None
        else:
            st.error(f"Failed to load FAISS vectorstore from {path}: {e}")
            return None


def generate_from_openai(prompt: str, model_name: str = "gpt-3.5-turbo", temperature: float = 0.2):
    import openai
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not found in environment.")
    openai.api_key = api_key
    resp = openai.ChatCompletion.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=512,
        temperature=temperature,
    )
    return resp.choices[0].message.content


def generate_from_groq(client, model, system_prompt, final_prompt, temperature: float = 0.2):
    # Uses aisuite client from rag02 implementation style
    try:
        # Attempt to pass temperature if supported by client
        kwargs = {"model": model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": final_prompt}]}
        try:
            kwargs["temperature"] = float(temperature)
        except Exception:
            pass
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content
    except Exception as e:
        raise


def main():
    st.set_page_config(page_title="RAG Streamlit App", layout="wide")
    st.title("RAG — Streamlit QA")

    # --- Debug / Deployment info: show whether faiss_db or chroma_db exist ---
    st.sidebar.markdown("**Storage status**")
    faiss_exists = os.path.exists("faiss_db")
    chroma_exists = os.path.exists("chroma_db")
    st.sidebar.write(f"faiss_db exists: {faiss_exists}")
    st.sidebar.write(f"chroma_db exists: {chroma_exists}")
    # If chroma exists, show a small listing to help debug in cloud
    if chroma_exists:
        try:
            files = os.listdir("chroma_db")
            st.sidebar.write(f"chroma_db contents (sample): {files[:10]}")
        except Exception as e:
            st.sidebar.write(f"Could not list chroma_db: {e}")

    # Sidebar settings
    st.sidebar.header("Settings")
    k = st.sidebar.number_input("Number of results (k)", min_value=1, max_value=10, value=4)
    db_path = st.sidebar.text_input("FAISS folder path", value="chroma_db")
    use_groq = st.sidebar.checkbox("Use Groq (aisuite) if available", value=True)
    # Prompt / model controls
    st.sidebar.markdown("---")
    system_prompt_input = st.sidebar.text_area("System prompt", value="你是我的筆記管理人，請根據提供內容並以台灣中文簡潔回覆。", height=120)
    prompt_template_input = st.sidebar.text_area("Prompt template", value="根據下列資料：\n{retrieved_chunks}\n\n回答使用者的問題：{question}\n\n若資料不足請說明。", height=120)
    temperature = st.sidebar.slider("Temperature", min_value=0.0, max_value=1.0, value=0.2, step=0.05)
    openai_model = st.sidebar.text_input("OpenAI model", value="gpt-3.5-turbo")
    groq_model_input = st.sidebar.text_input("Groq model", value=os.getenv("GROQ_MODEL", "groq:openai/gpt-oss-120b"))

    # (Preset UI moved to the Chat panel)

    with st.spinner("Loading vectorstore and embeddings..."):
        store = load_vectorstore(db_path)

    if store is None:
        st.error("Vectorstore not available. Run rag01_create_vector_db.py first.")
        return

    # Setup aisuite client if GROQ key is present and aisuite is installed
    groq_key = os.getenv("GROQ_API_KEY")
    groq_client = None
    groq_model = os.getenv("GROQ_MODEL", "groq:openai/gpt-oss-120b")
    if use_groq and groq_key and ai is not None:
        os.environ["GROQ_API_KEY"] = groq_key
        try:
            groq_client = ai.Client()
        except Exception:
            groq_client = None

    # session-based chat history
    if "history" not in st.session_state:
        st.session_state.history = []  # list of (role, text)

    # UI layout: left for chat, right for results
    left, right = st.columns([2, 3])

    with left:
        st.subheader("Chat")
        # Demo preset selectbox placed above the chat input (fills the input but does not auto-send)
        preset_options = ["", "GIT reset 怎麼寫？", "Vue 的 props 是甚麼用途", "AWS EC2 是甚麼？"]
        preset_choice = st.selectbox("Demo Preset Questions", options=preset_options, index=0, key="preset_select")
        if preset_choice:
            st.session_state["user_input"] = preset_choice

        user_input = st.text_input("Your question", key="user_input")
        send = st.button("Send")

        # display chat history
        for role, text in st.session_state.history:
            if role == "user":
                st.markdown(f"**You:** {text}")
            else:
                st.markdown(f"**Assistant:** {text}")

    with right:
        st.subheader("Retrieved Context")
        result_container = st.empty()

    if send and user_input.strip():
        st.session_state.history.append(("user", user_input))

        # retrieval
        try:
            # try retriever.invoke if available for newer vectorstore
            retriever = None
            try:
                retriever = store.as_retriever(search_kwargs={"k": k})
                if hasattr(retriever, "invoke"):
                    docs = retriever.invoke(user_input)
                else:
                    docs = store.similarity_search(user_input, k=k)
            except Exception:
                docs = store.similarity_search(user_input, k=k)
        except Exception as e:
            st.error(f"Retrieval failed: {e}")
            docs = []

        # show retrieved
        snippets = []
        for i, d in enumerate(docs, start=1):
            src = d.metadata.get("source", "") if hasattr(d, "metadata") else ""
            snippets.append(f"Source {i} ({src}):\n{d.page_content}")

        result_container.write("\n\n---\n\n".join(snippets) if snippets else "(no results)")

        # prepare prompt using sidebar inputs
        system_prompt = system_prompt_input
        retrieved_chunks = "\n\n".join([d.page_content for d in docs])
        try:
            final_prompt = prompt_template_input.format(retrieved_chunks=retrieved_chunks, question=user_input)
        except Exception:
            # if formatting fails, fall back to a simple concatenation
            final_prompt = f"{prompt_template_input}\n\n{retrieved_chunks}\n\nQuestion: {user_input}"

        # generate answer: prefer groq if client available and enabled, else openai if key present
        answer_text = None
        if groq_client:
            try:
                with st.spinner("Generating answer via Groq..."):
                    answer_text = generate_from_groq(groq_client, groq_model_input, system_prompt, final_prompt, temperature)
            except Exception as e:
                st.error(f"Groq generation failed: {e}")
                answer_text = None

        if not answer_text:
            openai_key = os.getenv("OPENAI_API_KEY")
            if openai_key:
                try:
                    with st.spinner("Generating answer via OpenAI..."):
                        answer_text = generate_from_openai(final_prompt, model_name=openai_model, temperature=temperature)
                except Exception as e:
                    st.error(f"OpenAI generation failed: {e}")
                    answer_text = None

        if not answer_text:
            answer_text = "無法產生回覆：未設定或呼叫 LLM 失敗。"

        # simulate progressive display (simple non-streaming chunked reveal)
        st.session_state.history.append(("assistant", ""))
        assistant_index = len(st.session_state.history) - 1
        chunk_size = 200
        for i in range(0, len(answer_text), chunk_size):
            st.session_state.history[assistant_index] = ("assistant", answer_text[: i + chunk_size])
            time.sleep(0.05)
        # ensure final stored
        st.session_state.history[assistant_index] = ("assistant", answer_text)


if __name__ == "__main__":
    main()
