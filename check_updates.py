import requests, os, json
from dotenv import load_dotenv
load_dotenv()
token = os.getenv('BOT_TOKEN')
url = f'https://api.telegram.org/bot{token}/getUpdates'
r = requests.get(url, timeout=10)
data = r.json()
if data.get('ok'):
    results = data.get('result', [])
    print(f'Total updates: {len(results)}')
    # Show last 5 updates
    for upd in results[-5:]:
        print(json.dumps(upd, indent=2, ensure_ascii=False))
else:
    print('Error:', data)