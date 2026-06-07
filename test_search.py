import requests
from bs4 import BeautifulSoup
import urllib.parse
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
}
query = "yesterday's gold cost"
encoded_query = urllib.parse.quote(query)
url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
print("URL:", url)
resp = requests.get(url, headers=headers)
print("Status:", resp.status_code)
html = resp.text

# print meta tags
meta_tags = re.findall(r'<meta[^>]*>', html)
for m in meta_tags:
    print(m)
    
links = re.findall(r'<a[^>]*href=\"([^\"]+)\"', html)
for i, l in enumerate(links[:5]):
    print(f"Link {i}:", l)
