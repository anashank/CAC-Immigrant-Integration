import os
import ssl
import nltk
import re
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from langchain_community.document_loaders import PyMuPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_groq import ChatGroq
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from pathlib import Path

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

os.environ["TOKENIZERS_PARALLELISM"] = "false"
groq_api_key = ""

BASE_DIR = Path(__file__).resolve().parent.parent

# Memory to store chat history
chat_history = []

def extract_keywords(text):
    """Extract keywords from the user prompt for document relevance checking."""
    words = word_tokenize(text.lower())
    stop_words = set(stopwords.words('english'))
    keywords = [word for word in words if word.isalpha() and word not in stop_words]
    keywords.append("document")  # Ensure the context of a document is considered
    return keywords

def check_document_relevance(retrieved_docs, user_prompt):
    """Check if the retrieved documents are relevant to the user prompt."""
    if not retrieved_docs:
        return False
    doc_texts = [doc.page_content for doc in retrieved_docs]
    keywords = extract_keywords(user_prompt.lower())
    for k in keywords:
        for doc_text in doc_texts:
            if k in doc_text.lower():
                return True
    return False

def store_in_chat_history(user_prompt, bot_response):
    """Stores each user query and bot response in the chat history."""
    chat_history.append({"user": user_prompt, "bot": bot_response})

def get_previous_conversations():
    """Retrieves chat history and returns it as a formatted string."""
    return "\n".join([f"User: {item['user']}\nBot: {item['bot']}" for item in chat_history])

def get_last_response():
    """Retrieve the most recent bot response from chat history."""
    if chat_history:
        return chat_history[-1]['bot']
    return None

def handle_summarization(user_prompt):
    """Handles summarization or follow-up queries referencing the last bot response."""
    last_response = get_last_response()
    if last_response:
        # Generate a summarization prompt
        llm = ChatGroq(groq_api_key=groq_api_key, model_name="Llama3-8b-8192")
        summarize_prompt = f"Please summarize the following response:\n\n{last_response}"
        response = llm.invoke(summarize_prompt)
        return clean_response(response.pretty_repr())
    else:
        return "No previous response to summarize."
    
def clean_response(response):
    """Removes unwanted text from the LLM response."""
    return response.replace("================================== Ai Message ==================================", "").strip()

def clean_response_pdf(response):
    # Replace bullet points with <li> tags and wrap everything in <ul>
    response = re.sub(r'(\*|\-|\•)\s*', '', response)  # Remove bullet point symbols
    response = re.sub(r'\n+', '</li><li>', response)  # New line to list item
    response = f'<ul><li>{response.strip()}</li></ul>'  # Wrap in <ul> and ensure no leading/trailing spaces
    return response


def get_response(user_prompt, filename):
    pdf_path = str(BASE_DIR) + '/static/' + filename

    # Load and process the document
    loader = PyMuPDFLoader(pdf_path)
    documents = loader.load()

    nltk.download('stopwords')
    nltk.download('punkt')

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=64)
    texts = text_splitter.split_documents(documents)

    # Use FAISS vector DB
    embeddings = HuggingFaceEmbeddings()
    index = FAISS.from_documents(texts, embeddings)
    retriever = index.as_retriever()

    # Check if the user is asking for a summarization or follow-up on the previous response
    if "summarize" in user_prompt.lower() or "previous" in user_prompt.lower():
        return handle_summarization(user_prompt)

    # Retrieve previous conversations
    previous_conversations = get_previous_conversations()

    # Set up the LLM
    llm = ChatGroq(groq_api_key=groq_api_key, model_name="Llama3-8b-8192")
    prompt = ChatPromptTemplate.from_template(
        """
        Answer the questions based on the provided context and previous conversation.
        <previous_conversations>
        {previous_conversations}
        </previous_conversations>
        %- if context -%
        <context>
        {context}
        </context>
        %- endif -%
        Questions: {input}
        """
    )

    document_chain = create_stuff_documents_chain(llm, prompt)
    retrieval_chain = create_retrieval_chain(retriever, document_chain)

    # First, check if the user query is relevant to the document using keyword matching
    retrieved_docs = retriever.invoke(user_prompt)

    if check_document_relevance(retrieved_docs, user_prompt):
        # PDF-specific response, include previous conversations in the context
        response = retrieval_chain.invoke({
            'input': user_prompt, 
            'previous_conversations': previous_conversations
        })
        bot_response = clean_response_pdf(response['answer'])
    else:
        # If no document match, generate a generic LLM response with chat memory
        response = llm.invoke(user_prompt)
        bot_response = clean_response(response.pretty_repr())

    # Store the conversation in memory
    store_in_chat_history(user_prompt, bot_response)
    
    return bot_response