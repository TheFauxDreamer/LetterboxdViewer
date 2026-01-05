import urllib.request
import xml.etree.ElementTree as ET
import os
import re

def update_history(username):
    url = f"https://letterboxd.com/{username}/rss/"
    local_file = "my_history.xml"
    
    with urllib.request.urlopen(url) as response:
        live_xml = ET.fromstring(response.read())
    
    live_items = live_xml.findall(".//item")
    
    if os.path.exists(local_file):
        tree = ET.parse(local_file)
        root = tree.getroot()
        channel = root.find("channel")
        existing_guids = {item.find("guid").text for item in channel.findall("item")}
    else:
        root = live_xml
        channel = root.find("channel")
        existing_guids = set()
        for item in channel.findall("item"):
            channel.remove(item)
    
    for item in live_items:
        guid = item.find("guid").text
        if guid not in existing_guids:
            desc = item.find("description").text
            
            # 1. Extract Poster
            img_match = re.search(r'src="([^"]+)"', desc)
            if img_match:
                p_tag = ET.SubElement(item, "poster")
                p_tag.text = img_match.group(1)
            
            # 2. Extract Review Text (Strip HTML tags)
            clean_review = re.sub(r'<p>.*?<img.*?>.*?</p>', '', desc)
            clean_review = re.sub(r'<[^>]+>', '', clean_review).strip()
            
            rev_tag = ET.SubElement(item, "review")
            rev_tag.text = clean_review if clean_review else "No review written."
            
            channel.insert(0, item)
    
    ET.ElementTree(root).write(local_file, encoding="utf-8", xml_declaration=True)
    print("Updated history with reviews.")

if __name__ == "__main__":
    username = os.environ.get('LETTERBOXD_USERNAME', 'XXX')
    update_history(username)
