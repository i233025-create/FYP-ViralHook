import requests, json
r = requests.post('http://127.0.0.1:8000/research/trends', json={'niche': 'Beauty'}, timeout=120)
print('status:', r.status_code)
data = r.json()
topics = data.get('topics', [])
print(f'{len(topics)} topics returned')
for t in topics:
    print(f"  [{t['trendScore']}] {t['topic']} — {t['niche']}")
    for s in t['signals'][:2]:
        print(f"    · {s}")
