import xml.etree.ElementTree as ET

xml_text = """
<feed xmlns="http://www.w3.org/2005/Atom">
    <entry>
        <title>Learning APIs</title>
        <published>2026-09-24</published>
        <id>https://arxiv.org/abs/1234.5678</id>
    </entry>
</feed>
"""

root = ET.fromstring(xml_text)

ns = {
    "atom": "http://www.w3.org/2005/Atom"
}

entry = root.find("atom:entry", ns)

title = entry.find("atom:title", ns).text
published = entry.find("atom:published", ns).text
paper_id = entry.find("atom:id", ns).text

print(title)
print(published)
print(paper_id)