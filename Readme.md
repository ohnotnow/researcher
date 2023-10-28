# Researcher

Researcher is a Python script that generates a list of search queries based on a specific query or problem. It uses OpenAI's GPT-4 and GPT-3.5-turbo-16k models to generate comprehensive and counterfactual search queries. It also fetches and parses web pages, and provides a concise summary of the main information contained in them.

## Installation (Native)

1. Clone the repository: `git clone https://github.com:ohnotnow/researcher.git`
2. Install the required packages: `pip install -r requirements.txt`

## Usage (Native)

1. `export OPENAI_API_KEY=sk-.....`
2. Run the script - `python main.py`
3. Enter the query or problem you want to research.
4. Wait for the script to generate a list of search queries and summaries of the web pages.

## Usage (Docker)
1. Create an .env file containing `OPENAI_API_KEY=sk....`
2. Run `./run.sh`
3. Enter the query or problem you want to research.
4. Wait for the script to generate a list of search queries and summaries of the web pages.

## Options
The script will take various flags to control limits and the like.  So you can pass:
```
--max-questions (default=10) Maximum number of questions to look up via google
--max-results (default=5) Maximum number of results to return per question
--max-page-size (default=8000) Maximum number of characters to send to the summary model
--question-model (default="gpt-4") Model to use for generating questions
--summary-model (default="gpt-3.5-turbo-16k") Model to use for generating summaries
--num-threads (default=5) Number of questions to process in parallel (be careful of API limits!)
--hurry (default=False) Shorthand for --question-model gpt-3.5-turbo --summary-model gpt-3.5-turbo --max-questions 5 --max-results 5  --max-page-size 2000 --num-threads 5
--thorough (default=False) Shorthand for --question-model gpt-4 --summary-model gpt-3.5-turbo --max-questions 10 --max-results 10 --max-page-size 8000 --num-threads 5
--delux (default=False) Shorthand for --question-model gpt-4 --summary-model gpt-4 --max-questions 10 --max-results 10 --max-page-size 8000 --num-threads 5
```

## Limitations
By default the script will just use basic scraping of google - which is not great (and against their T&C's).  You will also likely get blocked
by google if you run more than a couple of queries.  You can however sign up to https://serper.dev/ for free and get a fairly generous free
number of queries to run against google (I'm not associated with them - just a handy/easy service).  Just set your API key before you run the script and it will automatically use your serper account.  Eg,
```sh
export SERPER_API_KEY=123ba......
export OPENAI_API_KEY=sk-.....
python main.py
```

## Contributing

Contributions are welcome! If you find a bug or have a feature request, please open an issue or submit a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
