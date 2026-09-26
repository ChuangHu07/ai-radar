import requests
import xml.etree.ElementTree as ET

url = "http://export.arxiv.org/api/query"

params = {
    "search_query": "cat:cs.AI",
    "start": 0,
    "max_results": 20,
    "sortBy": "submittedDate",
    "sortOrder": "descending",
}

headers = {
    "User-Agent": "ai-radar/0.1"
}

response = requests.get(
    url,
    params=params,
    headers=headers,
    timeout=30
)



print(response.status_code)
print(response.url)
print(response.headers.get("Content-Type"))

root = ET.fromstring(response.content)

print(root.tag)

ns = {
    "atom": "http://www.w3.org/2005/Atom"
}

entries = root.findall("atom:entry", ns)

print(len(entries))

for i , entry in enumerate(entries, start=1):
    title = entry.find("atom:title", ns).text
    published = entry.find("atom:published", ns).text
    paper_id = entry.find("atom:id", ns).text
    print(f"{i}. {title}\n{published}\n{paper_id}")