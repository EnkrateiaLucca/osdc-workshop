#!/usr/bin/env python
# coding: utf-8

# - Simple Research Assistant Agent:
#     - Definition: Agent that can dynamically create and edit research reports as markdown files.
#     - Tools: scrape articles from url, read files, create files, send email.

# In[80]:


from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import ConfigurableField
from langchain_core.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import PyPDFLoader
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime

MODEL = "gpt-4o-mini"


# In[81]:


@tool
def read_file(file_path: str) -> str:
    """
    Read the content of a file and return it as a string.
    
    Args:
        file_path: (str) The path to the file to read.
    
    Returns:
        str: The content of the file
    """
    if file_path.endswith('.pdf'):
        return '\n'.join([p.page_content for p in PyPDFLoader(file_path).load_and_split()])
    else:
        with open(file_path, 'r') as file:
            return file.read()
    
# read_file("./paper-test.pdf")


# In[82]:


# read_file("./folder-tracker-agent.py")


# In[83]:


# read_file("./sample_transcript.txt")


# In[84]:


@tool
def create_markdown_file(contents: str, file_path: str) -> None:
    """
    Create a markdown file with the given contents at the given file path.
    
    Args:
        contents: (str) The contents of the markdown file.
        file_path: (str) The path to save the markdown file.
    """
    with open(file_path, 'w') as file:
        file.write(contents)

# create_markdown_file("# Hello World", "./hello-world.md")


# In[85]:


# !pip install youtube_transcript_api
from youtube_transcript_api import YouTubeTranscriptApi


@tool
def scrape_text(url: str):
    """
    Function that scrapes the text from a webpage.
    
    Args:
        url: (str) The URL of the webpage to scrape.    
    """
    # Send a GET request to the webpage
    if "youtube.com" in url:
        youtube_video_id = url.split("v=")[1]
        transcript = YouTubeTranscriptApi.get_transcript(youtube_video_id)
    
        transcript_str = ' '.join([chunk["text"] for chunk in transcript])
        return transcript_str
        
    try:
        response = requests.get(url)

        # Check if the request was successful
        if response.status_code == 200:
            # Parse the content of the request with BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")

            # Extract all text from the webpage
            page_text = soup.get_text(separator=" ", strip=True)

            # Print the extracted text
            return page_text
        else:
            return f"Failed to retrieve the webpage: Status code {response.status_code}"
    except Exception as e:
        print(e)
        return f"Failed to retrieve the webpage: {e}"


def read_youtube_transcript(youtube_video_id: str) -> str:
    """
    Reads the transcript of a Youtube video.
    
    Args:
        youtube_video_id: (str) The video id extracted from the Youtube url.
    """
    transcript = YouTubeTranscriptApi.get_transcript(youtube_video_id)
    
    transcript_str = ' '.join([chunk["text"] for chunk in transcript])
    return transcript_str


@tool
def send_email(subject_task: str, email_contents: str) -> None:
    """
    Function that sends an email with the given subject and contents.
    
    Args:
        subject_task: (str) The subject of the email.
        email_contents: (str) The contents of the email.
    """
    # Email credentials and SMTP settings
    smtp_server = "smtp.gmail.com"
    port = 587  # For starttls
    sender_email = "lucasenkrateia@gmail.com"  # Enter your email
    receiver_email = "lucasenkrateia@gmail.com"  # Enter receiver email
    password = os.environ["GMAIL_PWD"]

    # Create message
    subject = f"{subject_task}"
    # Get today's date in day month year format
    today_date = datetime.now().strftime('%d %B %Y')
    body = f"{email_contents}"

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    # Send email
    try:
        server = smtplib.SMTP(smtp_server, port)
        server.starttls()  # Secure the connection
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message.as_string())
        print("Email sent successfully!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        server.quit()


tools = [read_file, create_markdown_file, scrape_text, send_email]

llm = ChatOpenAI(model=MODEL,
                 temperature=0,
                 )

llm_with_tools = llm.bind_tools(tools)


prompt = ChatPromptTemplate.from_messages([
    ("system", "you're a helpful assistant"), 
    ("human", "{input}"), 
    ("placeholder", "{agent_scratchpad}"),
])


agent = create_tool_calling_agent(llm, tools, prompt)



agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)


agent_executor.invoke({"input": """
                       Use the information from these resources
                        - https://support.anthropic.com/en/articles/9487310-what-are-artifacts-and-how-do-i-use-them
                        - https://www.youtube.com/watch?v=zVUxO5CFA40
                        to create a markdown file containing a 10 slides in markdown style discussing how to use
                        and leverage Claude's artifacts feature for personal productivity.
                        Send me an email also with the contents of those slides.
                       """, })