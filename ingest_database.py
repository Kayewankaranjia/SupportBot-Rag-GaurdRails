from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain_chroma import Chroma
from uuid import uuid4
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from urllib.parse import urlparse, urljoin
from langchain_core.documents import Document
import time
import os
# import the .env file
from dotenv import load_dotenv
load_dotenv()

# configuration
croma_path = os.getenv("CHROMA_PATH")
root_url = os.getenv("ROOT_URL")

# initiate the embeddings model
embeddings_model = OpenAIEmbeddings(model="text-embedding-3-large")

# initiate the vector store
vector_store = Chroma(
    collection_name="voy_collection",
    embedding_function=embeddings_model,
    persist_directory=croma_path,
)

# Set up the driver for selenium automation
driver = webdriver.Chrome()

# Set limits and filters
max_links = os.getenv("MAX_LINKS")
SKIP_KEYWORDS = ["login", "sign-in", "signin", "log-in", "logon", "signon", "Sign in"] # Skip URLs with these keywords
VISITED_URL = set() # Track visited URLs, so we do not repeat them
DOCUMENTS = []

def should_skip(url):
    """Check if the URL should be skipped based on keywords."""
    return any(skip_word in url.lower() for skip_word in SKIP_KEYWORDS)

def scrape_links_recursively(current_url):

    parsed_root = urlparse(current_url)
    root_domain = parsed_root.netloc

    if (
        current_url in VISITED_URL
        or len(VISITED_URL) >= int(max_links)
        or should_skip(current_url)
    ):
        return

    VISITED_URL.add(current_url)

    try:
        driver.get(current_url)
        time.sleep(1)

        soup = BeautifulSoup(driver.page_source, "lxml")

        # Save current page data as LangChain Document
        DOCUMENTS.append(
            Document(page_content=soup.get_text(), metadata={"source": current_url})
        )

        for link_tag in soup.find_all("a", href=True):
            href = link_tag.get("href")
            full_url = urljoin(current_url, href)
            parsed = urlparse(full_url)

            if parsed.netloc == root_domain and full_url not in VISITED_URL:
                scrape_links_recursively(full_url)

    except Exception as e:
        print(f"Error scraping {current_url}: {e}")

# Start from root
scrape_links_recursively(root_url)

# # Output all DOCUMENTS gathered
# print(f"\n✅ Scraped {len(DOCUMENTS)} pages.\n")
# for doc in DOCUMENTS:
#     print(f"--- Document from {doc.metadata['source']} ---")
#     print(doc.page_content[:500])
#     print("\n" + "-"*80 + "\n")

driver.quit()
raw_documents = DOCUMENTS

# splitting the document
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=100,
    length_function=len,
    is_separator_regex=False,
)

# creating the chunks
chunks = text_splitter.split_documents(raw_documents)

# creating unique ID's
uuids = [str(uuid4()) for _ in range(len(chunks))]

# adding chunks to vector store
vector_store.add_documents(documents=chunks, ids=uuids) 