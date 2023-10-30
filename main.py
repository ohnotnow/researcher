import os
import json
from time import sleep
import pytz
import requests
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
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

def get_openai_response(model, messages, max_tokens=1000, timeout=60, asking_for_questions=False):
    max_tries = 3
    tries = 0
    while tries < max_tries:
        try:
            return openai.ChatCompletion.create(
                request_timeout=timeout,
                model=model,
                messages=messages,
                max_tokens=max_tokens,
            )
        except Exception as e:
            tries += 1
            print(f"(Error while talking to OpenAI : {e}")
            print(f"(Retrying in {tries * 5} second(s))")
            sleep(tries * 5)
    print(f"(Multiple errors while talking to OpenAI - skipping this call)")
    if asking_for_questions:
        print("Aborting...")
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
        return links[:num_results]
    else:
        return search(query, num_results=num_results)

def process_question(question, model, max_results, max_page_size):
    question = question.strip()
    print(f"\n(Searching for question: {question})\n")
    unwanted_domains = ['reddit.com', 'youtube.com', 'mattermost.com']
    question_results = ""
    tokens = 0
    for url in get_search_results(question, num_results=max_results):
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

        page_text = page_text[:max_page_size]
        temp_model = model
        temp_max_tokens = min(max_page_size, 6000)
        if len(page_text) < 3000 and '16k' in model:
            print(f"(Using gpt-3.5-turbo for {url} as the page is short.)")
            temp_model = 'gpt-3.5-turbo'
            temp_max_tokens = min(max_page_size, 2000)
        with yaspin(text="(Calling OpenAI for summary)", spinner="dots", timer=True):
            response = get_openai_response(
                model=temp_model,
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant who specialises in reading a USERS text and providing a concise summary of it containing the main information contained in it with a focus on answering any points in the users question."},
                    {"role": "user", "content": f"Hi, I am researching ''{question}''. Could you help by summarising anything useful in this text I have found? ''{page_text}''."},
                ],
                max_tokens=temp_max_tokens
            )
        summary = response['choices'][0]['message']['content']
        tokens += response['usage']['total_tokens']
        if temp_model != model:
            tokens = round(tokens / 2) # Half the tokens used if we used the smaller model as it's 1/2 the cost
        question_results = question_results + f"\n\n### {url}\n\n{summary}"
        sleep(1)
    return question_results, tokens

def parse_arguments():
    parser = argparse.ArgumentParser(description='Whatever')
    parser.add_argument('--max-questions', type=int, default=10, help='Maximum number of questions to look up via google')
    parser.add_argument('--max-results', type=int, default=5, help='Maximum number of results to return per question')
    parser.add_argument('--max-page-size', type=int, default=8000, help='Maximum number of characters to send to the summary model')
    parser.add_argument('--question-model', type=str, default="gpt-4", help='Model to use for generating questions')
    parser.add_argument('--summary-model', type=str, default="gpt-3.5-turbo-16k", help='Model to use for generating summaries')
    parser.add_argument('--num-threads', type=int, default=5, help='Number of questions to process in parallel')
    parser.add_argument('--openai_timeout', type=int, default=60, help='Number of seconds to wait for a response from the OpenAI API')
    parser.add_argument('--hurry', type=bool, default=False, action=argparse.BooleanOptionalAction, help='Shorthand for --question-model gpt-3.5-turbo --summary-model gpt-3.5-turbo --max-questions 5 --max-results 2 --max-page-size 2000 --num-threads 5')
    parser.add_argument('--thorough', type=bool, default=False, action=argparse.BooleanOptionalAction, help='Shorthand for --question-model gpt-4 --summary-model gpt-3.5-turbo --max-questions 10 --max-results 10 --max-page-size 8000 --num-threads 5')
    parser.add_argument('--delux', type=bool, default=False, action=argparse.BooleanOptionalAction, help='Shorthand for --question-model gpt-4 --summary-model gpt-4 --max-questions 10 --max-results 10 --max-page-size 8000 --num-threads 5')
    # parser.add_argument('--quiet', type=bool, default=False, help='Don\'t log anything - just print the response')
    args = parser.parse_args()

    if args.delux:
        args.max_questions = 10
        args.max_results = 10
        args.max_page_size = 8000
        args.num_threads = 5
        args.question_model = "gpt-4"
        args.summary_model = "gpt-4"
    if args.thorough:
        args.max_questions = 10
        args.max_results = 10
        args.max_page_size = 8000
        args.num_threads = 5
        args.question_model = "gpt-4"
        args.summary_model = "gpt-3.5-turbo-16k"
    if args.hurry:
        args.max_questions = 5
        args.max_results = 2
        args.max_page_size = 2000
        args.num_threads = 5
        args.question_model = "gpt-3.5-turbo"
        args.summary_model = "gpt-3.5-turbo"

    return args

if __name__ == '__main__':
    args = parse_arguments()
    total_tokens_used = 0
    total_token_cost = 0
    question = input("\nWhat would you like to research? ")
    filename = sanitize_filename(question) + ".md"
    with yaspin(text="(Calling OpenAI to get initial summary)", spinner="dots", timer=True):
        response = get_openai_response(
            model=args.question_model,
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant who specialised in giving concise overviews of a topic the USER is trying to research."},
                {"role": "user", "content": f"I am looking to research the following question, could you give me a short response of your thoughts on it? Q :: {question}"},
            ],
            timeout=args.openai_timeout,
        )

    gpt_thoughts = response['choices'][0]['message']['content']
    tokens = response['usage']['total_tokens']
    total_tokens_used += tokens
    total_token_cost += get_token_price(tokens, args.summary_model, direction="output")
    print(f"\n\n## Initial Summary:\n")
    print(gpt_thoughts)

    with yaspin(text="(Calling OpenAI to get questions)", spinner="dots", timer=True):
        response = get_openai_response(
            model=args.question_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"I am looking to research the following topic :: {question}"},
            ],
            timeout=args.openai_timeout,
            asking_for_questions=True,
        )

    response_text = response['choices'][0]['message']['content']
    tokens = response['usage']['total_tokens']
    total_tokens_used += tokens
    total_token_cost += get_token_price(tokens, args.question_model, direction="output")
    data = json.loads(response_text)[:args.max_questions]
    print(f"\n\n## Researcher Questions:\n")
    for researcher_question in data:
        print(f"* {researcher_question.strip()}")

    summary_results = {}
    with ThreadPoolExecutor(max_workers=args.num_threads) as executor:
        futures = {executor.submit(process_question, query, args.summary_model, args.max_results, args.max_page_size): (query, args.summary_model, args.max_results, args.max_page_size) for query in data}
        for future in futures:
            summary, tokens_used = future.result()
            query_tuple = futures[future]
            query_question, summary_model, max_results, max_page_size = query_tuple
            summary_results[query_question] = {
                "summary": summary,
                "tokens": tokens_used
            }

    with open(filename, "w") as file:
        tee_print(file, f'# {question}\n\n')
        tee_print(file, f'## Initial Summary:\n')
        tee_print(file, f"{gpt_thoughts}\n\n")
        tee_print(file, f'## Researcher Questions:\n')
        for researcher_question in data:
            tee_print(file, f"* {researcher_question.strip()}")
        tee_print(file, f'\n\n## Researcher Summaries:\n')

        for query_question, result in summary_results.items():
            tee_print(file, f"### {query_question}")
            tee_print(file, result['summary'])
            total_tokens_used += result['tokens']
    file.close()
    content = ""
    with open(filename, 'r') as file:
        content = file.read(args.max_page_size)
    if args.summary_model != "gpt-3.5-turbo":
        max_tokens = 6000
    else:
        max_tokens = 2000
    with yaspin(text="(Calling OpenAI for overall summary)", spinner="dots", timer=True):
        response = get_openai_response(
            model=args.summary_model,
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant who specialises in reading a list of various summaries of a users findings about websites and providing a readable summary of it containing the main information contained in it."},
                {"role": "user", "content": f"Could you extract the important points from my findings about ''{question}''? Please give a thorough summary and point out any key points. Findings :: {content}"},
            ],
            max_tokens=max_tokens,
            timeout=args.openai_timeout,
        )
    summary = response['choices'][0]['message']['content']
    tokens = response['usage']['total_tokens']
    total_tokens_used += tokens
    total_token_cost += get_token_price(total_tokens_used, args.summary_model, direction="output")
    file = open(filename, "a")
    tee_print(file, f'\n## Overall Summary')
    tee_print(file, summary)
    tee_print(file, f'\n\n### Usage')
    tee_print(file, f'* Total tokens used: {total_tokens_used}')
    tee_print(file, f'* Total cost (est): ${round(total_token_cost, 2)}\n\n')

    file.close()

    print(f"\n\n(Output saved to {filename})\n")
