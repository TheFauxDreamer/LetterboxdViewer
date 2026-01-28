import urllib.request
import xml.etree.ElementTree as ET
import os
import re

def update_history(username):
    url = f"https://letterboxd.com/{username}/rss/"
    local_file = "my_history.xml"
    
    req = urllib.request.Request(url, headers={"User-Agent": "LetterboxdViewer/1.0"})
    with urllib.request.urlopen(req) as response:
        live_xml = ET.fromstring(response.read())
    
    live_items = live_xml.findall(".//item")
    
    if os.path.exists(local_file):
        tree = ET.parse(local_file)
        root = tree.getroot()
        channel = root.find("channel")
        
        # Track both GUIDs and watch date + film combinations
        existing_guids = {item.find("guid").text for item in channel.findall("item")}
        existing_watches = set()
        
        for item in channel.findall("item"):
            # Get watch date
            watch_date_elem = item.find(".//{https://letterboxd.com}watchedDate")
            if watch_date_elem is None:
                watch_date_elem = item.find("pubDate")
            watch_date = watch_date_elem.text if watch_date_elem is not None else ""
            
            # Get film from link
            link_elem = item.find("link")
            film_slug = link_elem.text.split('/film/')[-1].rstrip('/') if link_elem is not None else ""
            
            if watch_date and film_slug:
                existing_watches.add((watch_date, film_slug))
    else:
        root = live_xml
        channel = root.find("channel")
        existing_guids = set()
        existing_watches = set()
        for item in channel.findall("item"):
            channel.remove(item)
    
    for item in live_items:
        guid = item.find("guid").text
        
        # Get watch date and film for duplicate checking
        watch_date_elem = item.find(".//{https://letterboxd.com}watchedDate")
        if watch_date_elem is None:
            watch_date_elem = item.find("pubDate")
        watch_date = watch_date_elem.text if watch_date_elem is not None else ""
        
        link_elem = item.find("link")
        film_slug = link_elem.text.split('/film/')[-1].rstrip('/') if link_elem is not None else ""
        
        # Check if this is a duplicate by GUID or by watch date + film
        is_duplicate = guid in existing_guids
        if watch_date and film_slug:
            is_duplicate = is_duplicate or (watch_date, film_slug) in existing_watches
        
        if not is_duplicate:
            desc = item.find("description").text
            
            # Extract Poster
            img_match = re.search(r'src="([^"]+)"', desc)
            if img_match:
                p_tag = ET.SubElement(item, "poster")
                p_tag.text = img_match.group(1)
            
            # Extract Review Text
            clean_review = re.sub(r'<p>.*?<img.*?>.*?</p>', '', desc)
            clean_review = re.sub(r'<[^>]+>', '', clean_review).strip()
            
            rev_tag = ET.SubElement(item, "review")
            rev_tag.text = clean_review if clean_review else "No review written."
            
            channel.insert(0, item)
            existing_guids.add(guid)
            if watch_date and film_slug:
                existing_watches.add((watch_date, film_slug))
    
    ET.ElementTree(root).write(local_file, encoding="utf-8", xml_declaration=True)
    print("Updated history with reviews.")

if __name__ == "__main__":
    username = os.environ.get('LETTERBOXD_USERNAME', 'XXX')
    update_history(username)
