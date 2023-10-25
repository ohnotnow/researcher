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

## Contributing

Contributions are welcome! If you find a bug or have a feature request, please open an issue or submit a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
