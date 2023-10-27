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
import argparse
import json

openai.api_key = os.getenv("OPENAI_API_KEY")
serper_api_key = os.getenv("SERPER_API_KEY")

system_prompt = """
# MISSION
You are a search query generator. You will be given a specific query or problem by the USER and you are to generate
a plain JSON array of a list of questions that will be used to search the internet.
Make sure you generate comprehensive and counterfactual search queries.
Employ everything you know about information foraging and information literacy to generate the best possible questions.
"""

def sanitize_filename(filename):
    return "results/" + ''.join(char if char.isalnum() else '_' for char in filename).lower()

def tee_print(file, *args, **kwargs):
    print(*args, **kwargs)
    print(*args, **kwargs, file=file)

def get_search_results(query, num_results=5):
    if serper_api_key:
        links = []
        url = "https://google.serper.dev/search"
        payload = json.dumps({
            "q": query
        })
        headers = {
            'X-API-KEY': serper_api_key,
            'Content-Type': 'application/json'
        }
        response = requests.request("POST", url, headers=headers, data=payload)
        json_dict = response.json()
        answers = json_dict.get("organic", [])
        for result in answers:
            link = result.get("link", None)
            if link and not 'reddit.com' in link:
                links.append(link)
        return links[0:num_results-1]
    else:
        return search(query, num_results=num_results)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Whatever')
    parser.add_argument('--max-questions', type=int, default=10, help='Maximum number of questions to look up via google')
    parser.add_argument('--max-results', type=int, default=5, help='Maximum number of results to return per question')
    parser.add_argument('--max-page-size', type=int, default=8000, help='Maximum number of characters to send to the summary model')
    parser.add_argument('--question-model', type=str, default="gpt-4", help='Model to use for generating questions')
    parser.add_argument('--summary-model', type=str, default="gpt-3.5-turbo-16k", help='Model to use for generating summaries')
    # parser.add_argument('--quiet', type=bool, default=False, help='Don\'t log anything - just print the response')
    args = parser.parse_args()

    question = input("\nWhat would you like to research? ")
    filename = sanitize_filename(question) + ".md"
    file = open(filename, "w")
    print(f"\n\n(Output being duplicated into {filename})\n")
    tee_print(file, f"# {question}\n")
    response = openai.ChatCompletion.create(
        model=args.question_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]
    )

    response_text = response['choices'][0]['message']['content']
    data = json.loads(response_text)[:args.max_questions]
    tee_print(file, f"\n\n## Researcher Questions:\n")
    for question in data:
        tee_print(file, f"* {question.strip()}")

    for question in data:
        question = question.strip()
        print(f"\n(Searching for question: {question})\n")
        unwanted_domains = ['reddit.com', 'youtube.com', 'mattermost.com']
        for url in get_search_results(question, num_results=args.max_results):
            for domain in unwanted_domains:
                if domain in url:
                    print(f"(Skipping {url} because it is a {domain} we can't handle.)")
                    continue
            response = requests.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            page_text = soup.get_text(strip=True)
            if not page_text:
                continue
            response = openai.ChatCompletion.create(
                model=args.summary_model,
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant who specialises in reading a USERS text and providing a concise summary of it containing the main information contained in it."},
                    {"role": "user", "content": page_text[:args.max_page_size]},
                ]
            )
            summary = response['choices'][0]['message']['content']
            tee_print(file, f'\n### Summary of {url}')
            tee_print(file, summary)
            sleep(1)
    file.close()
    content = ""
    with open(filename, 'r') as file:
        content = file.read(args.max_page_size)
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-16k",
        messages=[
            {"role": "system", "content": "You are a helpful AI assistant who specialises in reading a list of various summaries of a users findings about websites and providing a overall summary of it containing the main information contained in it."},
            {"role": "user", "content": content},
        ]
    )
    summary = response['choices'][0]['message']['content']
    file = open(filename, "a")
    tee_print(file, f'\n## Overall Summary')
    tee_print(file, summary)
    file.close()

    print(f"\n\n(Output saved to {filename}.md)\n")
