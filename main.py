import os
import json
from time import sleep
import pytz
import requests
import openai
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
import PyPDF2
from trafilatura import fetch_url, extract
from googlesearch import search


openai.api_key = os.getenv("OPENAI_API_KEY")

system_prompt = """
# MISSION
You are a search query generator. You will be given a specific query or problem by the USER and you are to generate
a plain JSON array of a list of questions that will be used to search the internet.
Make sure you generate comprehensive and counterfactual search queries.
Employ everything you know about information foraging and information literacy to generate the best possible questions.
"""

question = input("\nWhat would you like to research? ")

response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]
)

response_text = response['choices'][0]['message']['content']
data = json.loads(response_text)
print(f"\n\n# Questions: {data}\n")

for question in data:
    print(f"\n\n# Searching for question: {question}\n")
    for url in search(question, num_results=5):
        # Step 2: Fetch and Parse Web Page
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        page_text = soup.get_text(strip=True)
        if not page_text:
            continue
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-16k",
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant who specialises in reading a USERS text and providing a concise summary of it containing the main information contained in it."},
                {"role": "user", "content": page_text[:2000]},
            ]
        )
        summary = response['choices'][0]['message']['content']
        print(f'\n## Summary of {url}')
        print(summary)
        sleep(1)
