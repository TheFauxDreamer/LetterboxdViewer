import urllib.request
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import time
from datetime import datetime
from email.utils import formatdate
import json
import re

def fetch_poster(film_link):
    """
    Cleans the URL to ensure it points to the canonical movie page and 
    extracts the poster URL using your working split logic.
    """
    default_poster = "https://via.placeholder.com/600x900?text=No+Poster"
    if not film_link:
        return default_poster

    # Strip username to get the canonical film page (Fixes Blade Runner 2049 etc)
    match = re.search(r'(/film/[^/]+/?)', film_link)
    if match:
        clean_url = "https://letterboxd.com" + match.group(1)
    else:
        clean_url = film_link

    try:
        req = urllib.request.Request(
            clean_url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
            soup = BeautifulSoup(html, 'html.parser')

        # Use the specific split logic from your working script
        script_w_data = soup.select_one('script[type="application/ld+json"]')
        if script_w_data and ' */' in script_w_data.text:
            json_text = script_w_data.text.split(' */')[1].split('/* ]]>')[0]
            json_obj = json.loads(json_text)
            
            if 'image' in json_obj:
                print("    Poster URL retrieved")
                return json_obj['image']
    except Exception as e:
        print(f"    Error fetching poster for {clean_url}: {e}")

    return default_poster

def fetch_review(review_url):
    try:
        req = urllib.request.Request(review_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            soup = BeautifulSoup(response.read(), 'html.parser')
        review_elem = soup.find('div', class_='body-text')
        if review_elem:
            paragraphs = review_elem.find_all('p')
            return '\n'.join(p.get_text(strip=True) for p in paragraphs)
    except:
        return ""
    return ""

def scrape_full_history(username):
    all_entries = []
    page = 1
    print(f"Scraping full Letterboxd history for: {username}...")

    while True:
        url = f"https://letterboxd.com/{username}/films/diary/page/{page}/"
        print(f"Fetching page {page}...")

        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                soup = BeautifulSoup(response.read(), 'html.parser')

            entries = soup.find_all('tr', class_='diary-entry-row')
            if not entries:
                print(f"No more entries found. Scraped {page-1} pages.")
                break

            for entry in entries:
                try:
                    viewing_id = entry.get('data-viewing-id', '')
                    title_elem = entry.find('h2', class_='name')
                    if not title_elem: continue
                    
                    title_link = title_elem.find('a')
                    title = title_link.get_text(separator=' ', strip=True)
                    year_elem = entry.find('td', class_='col-releaseyear')
                    year = year_elem.get_text(strip=True) if year_elem else ""

                    # Date extraction
                    date_elem = entry.find('td', class_='col-daydate')
                    date_link = date_elem.find('a')
                    if date_link and 'href' in date_link.attrs:
                        p = date_link['href'].strip('/').split('/')
                        watch_date_iso = f"{p[-3]}-{p[-2]}-{p[-1]}"
                    else: continue

                    # Rating extraction
                    rating = ""
                    rating_numeric = None
                    rating_elem = entry.find('span', class_='rating')
                    if rating_elem:
                        for cls in rating_elem.get('class', []):
                            if cls.startswith('rated-'):
                                num = int(cls.split('-')[1])
                                rating_numeric = num / 2
                                rating = "★" * (num // 2) + ("½" if num % 2 else "")
                                break

                    film_link = f"https://letterboxd.com{title_link['href']}"
                    print(f"  Processing: {title} ({year})")
                    poster = fetch_poster(film_link)

                    is_rewatch = 'icon-status-off' not in entry.find('td', class_='col-rewatch').get('class', [])
                    
                    review = ""
                    review_elem = entry.find('td', class_='col-review')
                    if review_elem and review_elem.find('a'):
                        review = fetch_review(f"https://letterboxd.com{review_elem.find('a')['href']}")

                    all_entries.append({
                        'title': title, 'year': year, 'watch_date_iso': watch_date_iso,
                        'rating': rating, 'rating_numeric': rating_numeric, 'poster': poster,
                        'review': review, 'guid': f"letterboxd-watch-{viewing_id}" if viewing_id else f"lb-{watch_date_iso}", 
                        'film_link': film_link, 'is_rewatch': is_rewatch
                    })
                except Exception as e:
                    print(f"  Error parsing entry: {e}")
            
            page += 1
            time.sleep(1)
        except Exception: break

    return all_entries

def create_xml_from_entries(entries, output_file='my_history.xml'):
    """Restore original XML layout and namespaces exactly"""
    root = ET.Element('rss')
    root.set('xmlns:dc', "http://purl.org/dc/elements/1.1/")
    root.set('xmlns:ns0', "https://letterboxd.com")
    root.set('xmlns:ns1', "https://themoviedb.org")
    root.set('xmlns:ns3', "http://www.w3.org/2005/Atom")
    root.set('version', "2.0")

    channel = ET.SubElement(root, 'channel')
    ET.SubElement(channel, 'title').text = 'Letterboxd Archive'
    ET.SubElement(channel, 'link').text = 'https://letterboxd.com'

    entries.sort(key=lambda x: x['watch_date_iso'], reverse=True)

    for entry in entries:
        item = ET.SubElement(channel, 'item')
        
        # Original Title Format
        full_title = f"{entry['title']}, {entry['year']}"
        if entry['rating']: full_title += f" - {entry['rating']}"
        ET.SubElement(item, 'title').text = full_title
        ET.SubElement(item, 'link').text = entry['film_link']
        
        guid_elem = ET.SubElement(item, 'guid')
        guid_elem.set('isPermaLink', 'false')
        guid_elem.text = entry['guid']

        # Original pubDate Logic
        try:
            date_obj = datetime.strptime(entry['watch_date_iso'], '%Y-%m-%d')
            pub_date = formatdate(date_obj.timestamp(), localtime=False, usegmt=True).replace('GMT', '+1200')
        except: pub_date = entry['watch_date_iso']
        ET.SubElement(item, 'pubDate').text = pub_date

        # Restore ns0: Tags
        ET.SubElement(item, 'ns0:watchedDate').text = entry['watch_date_iso']
        ET.SubElement(item, 'ns0:rewatch').text = 'Yes' if entry['is_rewatch'] else 'No'
        ET.SubElement(item, 'ns0:filmTitle').text = entry['title']
        ET.SubElement(item, 'ns0:filmYear').text = entry['year']
        if entry['rating_numeric'] is not None:
            ET.SubElement(item, 'ns0:memberRating').text = str(entry['rating_numeric'])

        # Original description content
        desc = f'<p><img src="{entry["poster"]}"/></p>'
        if entry['review']: desc += f'<p>{entry["review"]}</p>'
        ET.SubElement(item, 'description').text = desc

        ET.SubElement(item, 'dc:creator').text = 'Archive'
        ET.SubElement(item, 'poster').text = entry['poster']
        ET.SubElement(item, 'review').text = entry['review']

    ET.ElementTree(root).write(output_file, encoding='utf-8', xml_declaration=True)
    print(f"\nCreated {output_file} with {len(entries)} entries")

if __name__ == "__main__":
    USER = "TheFauxDreamer" 
    entries = scrape_full_history(USER)
    if entries: create_xml_from_entries(entries)