import os
import sys
import json
from notion_client import Client
from notion2md.exporter.block import StringExporter
import markdown
try:
    from xhtml2pdf import pisa
except Exception:
    pisa = None
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def save_text_to_pdf(text, output_path):
    """
    Converts Markdown text to HTML and then to PDF.
    """
    # Basic sanitization to avoid problematic unicode/punctuation
    def sanitize_md(md_text: str) -> str:
        # replace fullwidth colon with ASCII colon
        md_text = md_text.replace('\uFF1A', ':')
        # remove any NULL or other control characters
        md_text = ''.join(ch for ch in md_text if ord(ch) >= 9 and ord(ch) != 11 and ord(ch) != 12)
        return md_text

    sanitized = sanitize_md(text)

    # Convert Markdown to HTML using fenced_code and codehilite for more robust output
    try:
        html_content = markdown.markdown(sanitized, extensions=['fenced_code', 'codehilite'])
    except Exception:
        html_content = markdown.markdown(sanitized)

    # Add some basic styling for the PDF
    full_html = f"""
    <html>
    <head>
    <style>
        body {{ font-family: Helvetica, sans-serif; font-size: 12pt; }}
        h1 {{ font-size: 24pt; color: #333; }}
        h2 {{ font-size: 18pt; color: #555; }}
        p {{ margin-bottom: 10px; }}
        code {{ background-color: #f4f4f4; padding: 2px 5px; }}
        pre {{ background-color: #f4f4f4; padding: 10px; white-space: pre-wrap; }}
    </style>
    </head>
    <body>
    {html_content}
    </body>
    </html>
    """

    # Try Playwright only if available
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(full_html, wait_until="networkidle")
            page.pdf(path=output_path, print_background=True, format="A4")
            browser.close()
        return True
    except Exception as e:
        # If Playwright isn't available, fall back to xhtml2pdf only when its dependency is present
        if pisa is None:
            # Neither Playwright nor xhtml2pdf available — save markdown as fallback
            try:
                # Save the markdown content to a .md file next to requested output
                md_path = os.path.splitext(output_path)[0] + ".md"
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(sanitized)
                print(f"Playwright/xhtml2pdf not installed. Saved markdown fallback: {md_path}")
                return False
            except Exception as e3:
                print(f"Failed to save markdown fallback: {e3}")
                return False
        else:
            try:
                with open(output_path, "wb") as pdf_file:
                    pisa_status = pisa.CreatePDF(full_html, dest=pdf_file)
                if pisa_status.err:
                    print(f"Error creating PDF with xhtml2pdf: {pisa_status.err}")
                    return False
                return True
            except Exception as e2:
                print(f"xhtml2pdf failed: {e2}")
                return False

def fetch_notion_page_as_pdf(page_id, output_folder="uploaded_docs"):
    """
    Fetches a Notion page by ID, converts it to Markdown, then PDF.
    """
    notion_token = os.getenv("NOTION_TOKEN")
    if not notion_token:
        print("Error: NOTION_TOKEN not found in environment variables.")
        return

    client = Client(auth=notion_token)

    # First check if the id is a database
    try:
        db = client.databases.retrieve(page_id)
        is_database = True
    except Exception:
        is_database = False
            # Priority: CLI arg > NOTION_SOURCE_URL env var > NOTION_SOURCE_URL_LIST JSON mapping
    if is_database:
        return fetch_notion_database_as_pdfs(page_id, output_folder)

    print(f"Fetching Notion page: {page_id}...")
    try:
        page = client.pages.retrieve(page_id)
        title = "Untitled"

        # Extract title safely
        if "properties" in page:
            for prop in page["properties"].values():
                if prop.get("type") == "title":
                    if prop.get("title"):
                        title = prop["title"][0].get("plain_text", title)
                    break

        safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '-', '_')]).strip()
        output_filename = f"{safe_title}.pdf"
        output_path = os.path.join(output_folder, output_filename)

        # Ensure environ available for notion2md
        if "NOTION_TOKEN" not in os.environ:
            os.environ["NOTION_TOKEN"] = notion_token

        print("Converting Notion blocks to Markdown...")
        md_exporter = StringExporter(block_id=page_id)
        md_string = md_exporter.export()

        if not md_string:
            print("Warning: No content found or failed to convert to Markdown.")
            return

        print(f"Saving to PDF: {output_path}...")
        if save_text_to_pdf(md_string, output_path):
            print(f"Successfully saved {output_path}")
        else:
            print("Failed to save PDF.")

    except Exception as e:
        print(f"An error occurred: {e}")


def _get_title_from_properties(properties: dict) -> str:
    # Try to extract title from database item properties
    for prop in properties.values():
        if prop.get("type") == "title":
            title_list = prop.get("title") or []
            if title_list:
                return "".join([t.get("plain_text", "") for t in title_list]).strip()
    return ""


def fetch_notion_database_as_pdfs(database_id, output_folder="uploaded_docs"):
    """
    Queries a Notion database and exports each page to a PDF in `output_folder`.
    """
    notion_token = os.getenv("NOTION_TOKEN")
    if not notion_token:
        print("Error: NOTION_TOKEN not found in environment variables.")
        return

    client = Client(auth=notion_token)
    print(f"Fetching Notion database: {database_id}...")

    start_cursor = None
    count = 0
    while True:
        try:
            resp = client.databases.query(database_id=database_id, start_cursor=start_cursor, page_size=100)
        except Exception as e:
            print(f"Failed to query database: {e}")
            return

        results = resp.get("results", [])
        for item in results:
            page_id = item.get("id")
            title = _get_title_from_properties(item.get("properties", {}))
            if not title:
                try:
                    p = client.pages.retrieve(page_id)
                    if "properties" in p:
                        title = _get_title_from_properties(p.get("properties", {}))
                except Exception:
                    title = "Untitled"

            safe_title = "".join([c for c in (title or "Untitled") if c.isalnum() or c in (' ', '-', '_')]).strip()
            output_filename = f"{safe_title or page_id}.pdf"
            output_path = os.path.join(output_folder, output_filename)

            # Ensure environ available for notion2md
            if "NOTION_TOKEN" not in os.environ:
                os.environ["NOTION_TOKEN"] = notion_token

            print(f"Converting page {page_id} -> {output_filename}...")
            try:
                md_exporter = StringExporter(block_id=page_id)
                md_string = md_exporter.export()
                if not md_string:
                    print(f"Warning: page {page_id} returned empty markdown.")
                    continue
                if save_text_to_pdf(md_string, output_path):
                    print(f"Saved: {output_path}")
                    count += 1
                else:
                    print(f"Failed to save PDF for page {page_id}")
            except Exception as e:
                print(f"Error exporting page {page_id}: {e}")

        if resp.get("has_more"):
            start_cursor = resp.get("next_cursor")
        else:
            break

    print(f"Completed. Exported {count} pages to {output_folder}")

if __name__ == "__main__":
    # Ensure output directory exists
    os.makedirs("uploaded_docs", exist_ok=True)

    def extract_page_id_from_url(src: str):
        import re
        if not src:
            return None
        s = src.strip()
        # remove surrounding quotes if any
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            s = s[1:-1].strip()

        # Keep only hex characters to assemble a continuous hex string (robust to newlines/spaces)
        hexchars = '0123456789abcdefABCDEF'
        filtered = ''.join([c for c in s if c in hexchars])
        if len(filtered) >= 32:
            raw = filtered[-32:]
            hy = f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"
            return hy

        # fallback: last path segment without non-hex chars
        seg = s.rstrip('/').split('/')[-1]
        seg_filtered = ''.join([c for c in seg if c in hexchars])
        if len(seg_filtered) == 32:
            raw = seg_filtered
            return f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"

        return None

    def try_retrieve_database(client, page_id_candidate: str):
        """Try multiple id formats to retrieve a database. Returns (resp, used_id) or (None, None)."""
        if not page_id_candidate:
            return None, None
        candidates = []
        pid = page_id_candidate.strip()
        # strip quotes
        pid = pid.strip('"').strip("'")
        candidates.append(pid)
        # raw without hyphens
        raw = pid.replace('-', '')
        candidates.append(raw)
        # hyphenated form from raw
        if len(raw) == 32:
            hy = f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"
            candidates.append(hy)

        tried = set()
        for c in candidates:
            if not c or c in tried:
                continue
            tried.add(c)
            try:
                resp = client.databases.retrieve(c)
                return resp, c
            except Exception:
                continue
        return None, None

    def try_retrieve_page(client, page_id_candidate: str):
        """Try multiple id formats to retrieve a page. Returns (resp, used_id) or (None, None)."""
        if not page_id_candidate:
            return None, None
        candidates = []
        pid = page_id_candidate.strip()
        pid = pid.strip('"').strip("'")
        candidates.append(pid)
        raw = pid.replace('-', '')
        candidates.append(raw)
        if len(raw) == 32:
            hy = f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"
            candidates.append(hy)

        tried = set()
        for c in candidates:
            if not c or c in tried:
                continue
            tried.add(c)
            try:
                resp = client.pages.retrieve(c)
                return resp, c
            except Exception:
                continue
        return None, None

    # Priority: CLI arg > NOTION_SOURCE_URL env var > NOTION_SOURCE_URL_LIST (JSON mapping)
    page_id = None
    if len(sys.argv) > 1:
        page_id = sys.argv[1]

    if not page_id:
        src = os.getenv("NOTION_SOURCE_URL") or os.getenv("NOTION_PAGE_ID")
        if src:
            page_id = extract_page_id_from_url(src)

    if page_id:
        print(f"Using Notion page id: {page_id}")
        fetch_notion_page_as_pdf(page_id)
    else:
        # Read mapping from a JSON file; path can be set via NOTION_SOURCE_JSON env var
        json_path = os.getenv("NOTION_SOURCE_JSON", "notion_sources.json")
        obj = None
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    obj = json.load(f)
            except Exception as e:
                print(f"Failed to read {json_path}: {e}")
                obj = None
        else:
            print(f"Notion sources JSON not found at {json_path}")

        if isinstance(obj, dict):
            for name, url in obj.items():
                pid = extract_page_id_from_url(url)
                if not pid:
                    print(f"Could not extract page id from URL for '{name}': {url}")
                    continue
                print(f"Exporting '{name}' from {pid}...")
                fetch_notion_page_as_pdf(pid)
                # Try to rename most recently created file to the provided name
                try:
                    files = sorted([f for f in os.listdir("uploaded_docs")], key=lambda x: os.path.getmtime(os.path.join("uploaded_docs", x)), reverse=True)
                    if files:
                        latest = files[0]
                        target = f"{name}.pdf"
                        src_path = os.path.join("uploaded_docs", latest)
                        dst_path = os.path.join("uploaded_docs", target)
                        if src_path != dst_path:
                            try:
                                os.replace(src_path, dst_path)
                                print(f"Renamed {latest} -> {target}")
                            except Exception:
                                pass
                except Exception:
                    pass
            print("Completed exporting mapping.")
        else:
            print("NOTION_SOURCE_URL_LIST must be provided as a JSON file (set NOTION_SOURCE_JSON or put notion_sources.json in repo).")
            print("Usage: python rag03_notion_to_pdf.py <NOTION_PAGE_ID>")
            print("Or set NOTION_SOURCE_URL or NOTION_PAGE_ID or NOTION_SOURCE_URL_LIST in your .env file.")
