from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import PromptTemplate
import gradio as gr
from nemoguardrails import RailsConfig
from nemoguardrails.integrations.langchain.runnable_rails import RunnableRails
import nest_asyncio
nest_asyncio.apply()

# import the .env file
from dotenv import load_dotenv
load_dotenv()
import os

# configuration
croma_path = os.getenv("CHROMA_PATH")

embeddings_model = OpenAIEmbeddings(model="text-embedding-3-large")

# initiate the model
llm = ChatOpenAI(temperature=0.5, model='gpt-4o-mini')
output_parser = StrOutputParser()
# connect to the chromadb
vector_store = Chroma(
    collection_name="voy_collection",
    embedding_function=embeddings_model,
    persist_directory=croma_path, 
)

# Set up the vectorstore to be the retriever
num_results = 20
retriever = vector_store.as_retriever(search_kwargs={'k': num_results})

# call this function for every message added to the chatbot
def stream_response(message, history):
    #print(f"Input: {message}. History: {history}\n")

    # retrieve the relevant chunks based on the question asked
    docs = retriever.invoke(message)

    # add all the chunks to 'knowledge'
    knowledge = ""

    for doc in docs:
        knowledge += doc.page_content+"\n\n"

    # make the call to the LLM (including prompt)
    if message is not None:

        partial_message = ""

        
        custom_prompt_template  = f"""
        You are an assistent which answers questions based on knowledge which is provided to you.
        While answering, you don't use your internal knowledge, 
        but solely the information in the "The knowledge" section.
        You don't mention anything to the user about the povided knowledge.

        The question: {message}

        Conversation history: {history}

        The knowledge: {knowledge}

        """

        custom_prompt = PromptTemplate(
        template=custom_prompt_template,
        input_variables=["message", "chat_history", "question"],
)
        config = RailsConfig.from_path("config")
        guard_rail = RunnableRails(config=config)

        guardrail_response = guard_rail.invoke({"input":message})
        message = guardrail_response['output']
        # #print(rag_prompt)
        chain =  custom_prompt | llm | output_parser
        # stream the response to the Gradio App
        for response in chain.stream({"message":message, "chat_history":history, "question":message}):
            partial_message += response
            yield partial_message

# initiate the Gradio app
chatbot = gr.ChatInterface(stream_response, textbox=gr.Textbox(placeholder="Send to the LLM...",
    container=False,
    autoscroll=True,
    scale=7),
)

# launch the Gradio app
chatbot.launch()