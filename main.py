import os
import json
from time import sleep
import pytz
import requests
from enum import Enum
import openai
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
import PyPDF2
from trafilatura import fetch_url, extract
from googlesearch import search
import argparse
import json
from yaspin import yaspin

openai.api_key = os.getenv("OPENAI_API_KEY")
serper_api_key = os.getenv("SERPER_API_KEY")

system_prompt = """
# MISSION
You are a search query generator. You will be given a specific query or problem by the USER and you are to generate
a plain JSON array of a list of questions that will be used to search the internet.
Make sure you generate comprehensive and counterfactual search queries.
Employ everything you know about information foraging and information literacy to generate the best possible questions.
"""

# Define model and token prices
class Model(Enum):
    GPT4_32k = ('gpt-4-32k', 0.03, 0.06)
    GPT4 = ('gpt-4', 0.06, 0.12)
    GPT3_5_Turbo_16k = ('gpt-3.5-turbo-16k', 0.003, 0.004)
    GPT3_5_Turbo = ('gpt-3.5-turbo', 0.0015, 0.002)

def get_token_price(token_count, model_engine, direction="output"):
    token_price_input = 0
    token_price_output = 0
    for model in Model:
        if model_engine.startswith(model.value[0]):
            token_price_input = model.value[1] / 1000
            token_price_output = model.value[2] / 1000
            break
    if direction == "input":
        return round(token_price_input * token_count, 4)
    return round(token_price_output * token_count, 4)

def sanitize_filename(filename):
    return "results/" + ''.join(char if char.isalnum() else '_' for char in filename).lower()

def tee_print(file, *args, **kwargs):
    print(*args, **kwargs)
    print(*args, **kwargs, file=file)

def get_openai_response(model, messages):
    max_tries = 3
    tries = 0
    while tries < max_tries:
        try:
            return openai.ChatCompletion.create(
                model=model,
                messages=messages
            )
        except Exception as e:
            tries += 1
            print(f"(Error while talking to OpenAI : {e}")
            print(f"(Retrying in {tries} second(s))")
            sleep(tries)
    print(f"(Multiple errors while talking to OpenAI - aborting)")
    exit(1)

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
        with yaspin(text=f"(Calling Serper API to search for : {question})", spinner="dots", timer=True):
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

def process_question(question, model, max_results, max_page_size):
    pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Whatever')
    parser.add_argument('--max-questions', type=int, default=10, help='Maximum number of questions to look up via google')
    parser.add_argument('--max-results', type=int, default=5, help='Maximum number of results to return per question')
    parser.add_argument('--max-page-size', type=int, default=8000, help='Maximum number of characters to send to the summary model')
    parser.add_argument('--question-model', type=str, default="gpt-4", help='Model to use for generating questions')
    parser.add_argument('--summary-model', type=str, default="gpt-3.5-turbo-16k", help='Model to use for generating summaries')
    # parser.add_argument('--quiet', type=bool, default=False, help='Don\'t log anything - just print the response')
    args = parser.parse_args()

    total_tokens_used = 0
    total_token_cost = 0
    question = input("\nWhat would you like to research? ")
    filename = sanitize_filename(question) + ".md"
    file = open(filename, "w")
    print(f"\n\n(Output being duplicated into {filename})\n")
    tee_print(file, f"# {question}\n")
    with yaspin(text="(Calling OpenAI to get questions)", spinner="dots", timer=True):
        response = get_openai_response(
            model=args.question_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ]
        )

    response_text = response['choices'][0]['message']['content']
    tokens = response['usage']['total_tokens']
    total_tokens_used += tokens
    total_token_cost += get_token_price(tokens, args.question_model, direction="output")
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
            page_text = None
            try:
                response = requests.get(url, timeout=30)
                soup = BeautifulSoup(response.text, 'html.parser')
                page_text = soup.get_text(strip=True)
            except Exception as e:
                print(f"(Skipping {url} because of error: {e})")
                continue

            if not page_text:
                print(f"(Skipping {url} because it has no text.)")
                continue
            if 'cloudflare' in page_text.lower() and 'cookies' in page_text.lower():
                print(f"(Skipping {url} because it is a cloudflare cookie check page.)")
                continue
            if '403 Forbidden' in page_text.lower():
                print(f"(Skipping {url} because it is a 403 Forbidden page.)")
                continue

            with yaspin(text="(Calling OpenAI for summary)", spinner="dots", timer=True):
                response = get_openai_response(
                    model=args.summary_model,
                    messages=[
                        {"role": "system", "content": "You are a helpful AI assistant who specialises in reading a USERS text and providing a concise summary of it containing the main information contained in it with a focus on answering any points in the users question."},
                        {"role": "user", "content": f"Hi, I am researching ''{question}''. Could you help by summarising anything useful in this text I have found? ''{page_text[:args.max_page_size]}''."},
                    ]
                )
            summary = response['choices'][0]['message']['content']
            tokens = response['usage']['total_tokens']
            total_tokens_used += tokens
            total_token_cost += get_token_price(tokens, args.summary_model, direction="output")
            tee_print(file, f'\n### Summary of {url}')
            tee_print(file, summary)
            sleep(1)
    file.close()
    content = ""
    with open(filename, 'r') as file:
        content = file.read(args.max_page_size)
    with yaspin(text="(Calling OpenAI for overall summary)", spinner="dots", timer=True):
        response = get_openai_response(
            model=args.summary_model,
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant who specialises in reading a list of various summaries of a users findings about websites and providing a overall summary of it containing the main information contained in it."},
                {"role": "user", "content": content},
            ]
        )
    summary = response['choices'][0]['message']['content']
    tokens = response['usage']['total_tokens']
    total_tokens_used += tokens
    total_token_cost += get_token_price(tokens, args.summary_model, direction="output")
    file = open(filename, "a")
    tee_print(file, f'\n## Overall Summary')
    tee_print(file, summary)
    tee_print(file, f'\n\n### Usage')
    tee_print(file, f'* Total tokens used: {total_tokens_used}')
    tee_print(file, f'* Total cost (est): ${round(total_token_cost, 2)}\n\n')

    file.close()

    print(f"\n\n(Output saved to {filename})\n")
