import os
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from tools.qa import TOOLS

load_dotenv()


def vectorize_tools():
    print("Indexing tools into ChromaDB...")

    # Use the same embedding model as the graph_builder
    embeddings = OllamaEmbeddings(
        model=os.getenv("OLLAMA_EMBEDDING_MODEL", "embeddinggemma:300m"),
        base_url=os.getenv("OLLAMA_BASE_URL"),
    )

    persist_directory = "./data/chroma_db"

    # Extract tool names and descriptions
    texts = [tool.description for tool in TOOLS]
    metadatas = [{"name": tool.name} for tool in TOOLS]
    ids = [tool.name for tool in TOOLS]

    vectorstore = Chroma.from_texts(
        texts=texts,
        embedding=embeddings,
        metadatas=metadatas,
        ids=ids,
        persist_directory=persist_directory,
        collection_name="tools",
    )

    print(f"Successfully indexed {len(TOOLS)} tools.")


if __name__ == "__main__":
    vectorize_tools()
