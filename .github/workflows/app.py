import logging
from flask import Flask, request, jsonify, render_template, send_from_directory
import os
import requests

# -----------------------------------------------------------------------------
# FYI - Use Azure App Servive Plan B1 - Location Canada Central (Highest Avb, and minimal quota restrictions)
# -----------------------------------------------------------------------------

SEARCH_ENDPOINT = "https://ragsearchvsp.search.windows.net"
SEARCH_KEY =  "NyJYGsnIzbjZabD0ZtXqs8VC5z8UIPFHj1xlnmvk9sAzSeDKSxFk"
SEARCH_INDEX =  "rag-1758802105417"
# e.g. https://<resource>.openai.azure.com
OPENAI_ENDPOINT =  "https://ragopenaiembeddingvsp.openai.azure.com/"
OPENAI_KEY =  "BsZvk6Tp4FGhGMEj0u2tY3iutqSleKIOgbIyDytiYrcafoMijRXhJQQJ99BIACYeBjFXJ3w3AAABACOGC73O"
OPENAI_DEPLOYMENT = "gpt-35-turbo"


# API versions
AZ_SEARCH_API_VERSION = "2021-04-30-Preview"
AZ_OPENAI_CHAT_API_VER = "2024-12-01-preview"

app = Flask(__name__)


@app.route('/infer', methods=['GET', 'POST'])
def infer():
    logging.info('Python HTTP trigger function processed a request.')

    # 0. get the question
    question = request.args.get('q') or (
        request.json.get('question') if request.is_json else None
    )
    if not question:
        return jsonify({"error": "No question provided"}), 400

    # 1. (Optional) switch to POST /docs/search
    search_url = (
        f"{SEARCH_ENDPOINT}/indexes/{SEARCH_INDEX}/docs/search"
        f"?api-version={AZ_SEARCH_API_VERSION}"
    )
    search_body = {
        "search": question,
        "queryType": "semantic",
        "semanticConfiguration": "rag-1758802105417-semantic-configuration",
        "top": 5
    }
    search_headers = {
        "Content-Type": "application/json",
        "api-key": SEARCH_KEY
    }
    
    search_res = requests.post(
        search_url, json=search_body, headers=search_headers)
    if search_res.status_code != 200:
    # app.logger.error("Search 400: %s", search_res.text)
        print("Search 400: %s", search_res.text)
        return jsonify({
            "error": "Azure Search failed",
            "details": search_res.text
        }), search_res.status_code
    
    # Process the search results
    # Log
    print("---" * 50)
    print("🚨🚨🚨 Search Response: 🚨🚨🚨")
    print("🔴" * 50
          + "\n" + str(search_res.json()) + "\n" + "🔴" * 50
          + "\n" + "🚨🚨🚨 End of Search Response 🚨🚨🚨")
    print("---" * 50)
    hits = search_res.json().get('value', [])

    # build context
    context = ""
    # list your index’s text‐holding fields in priority order
    fallback_fields = ["content", "chunk", "text", "title"]

    for i, doc in enumerate(hits, start=1):
        # pick the first non-empty field
        text = next(
            (doc.get(field) for field in fallback_fields if doc.get(field)),
            ""
        )
        # ensure we have a string
        text = str(text)
        # truncate to avoid over-long prompts
        snippet = text[:1000]
        context += f"Document {i}:\n{snippet}\n\n"

    # 2. assemble chat messages
    messages = [
        {
            "role": "system",
            "content": (
                "You are an AI assistant given the following documents from an incident report. "
                "Use them to answer the question below. "
                "If the documents do not contain the answer, say you do not know."
            )
        },
        {
            "role": "user",
            "content": f"{context}\nQuestion: {question}"
        }
    ]

    # 3. call chat/completions
    endpoint = OPENAI_ENDPOINT.rstrip('/')
    openai_url = (
        f"{endpoint}/openai/deployments/{OPENAI_DEPLOYMENT}"
        f"/chat/completions?api-version={AZ_OPENAI_CHAT_API_VER}"
    )
    oai_headers = {
        "Content-Type": "application/json",
        "api-key": OPENAI_KEY
    }
    oai_payload = {
        "messages": messages,
        "max_tokens": 500,
        "temperature": 0.2
    }

    oai_res = requests.post(openai_url, json=oai_payload, headers=oai_headers)
    oai_res.raise_for_status()
    chat_data = oai_res.json()

    # Log the chat_data with high alert emojis and visiual indicators
    print("🚨🚨🚨 Chat Data Response: 🚨🚨🚨")
    print("🔴" * 50
          + "\n" + str(chat_data) + "\n" + "🔴" * 50
          + "\n" + "🚨🚨🚨 End of Chat Data Response 🚨🚨🚨")
    
    # 4. extract answer
    answer = chat_data["choices"][0]["message"]["content"].strip()

    return jsonify({"question": question, "answer": answer})


# -----------------------------------------------------------------------------
# Static and Non Function Routes
# -----------------------------------------------------------------------------
def check_configuration():
    """Check if all required Azure configurations are present"""
    configs = {
        "Azure Search Endpoint": SEARCH_ENDPOINT,
        "Azure Search Key": SEARCH_KEY,
        "Azure Search Index": SEARCH_INDEX,
        "Azure OpenAI Endpoint": OPENAI_ENDPOINT,
        "Azure OpenAI Key": OPENAI_KEY,
        "Azure OpenAI Deployment": OPENAI_DEPLOYMENT
    }
    
    status = {}
    all_configured = True
    
    for name, value in configs.items():
        if value:
            status[name] = {"status": "✅ Configured", "class": "success"}
        else:
            status[name] = {"status": "❌ Missing", "class": "error"}
            all_configured = False
    
    return status, all_configured

@app.route('/')
def index():
    print('Request for index page received')
    config_status, all_configured = check_configuration()
    return render_template('index.html', 
                         config_status=config_status, 
                         all_configured=all_configured)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

if __name__ == '__main__':
    app.run(debug=True)