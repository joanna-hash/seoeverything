import streamlit as st
import xml.etree.ElementTree as ET
import io
import pandas as pd
from datetime import date

# ----------------------------
# Page config & title
# ----------------------------
st.set_page_config(page_title="Sitemap Generator", layout="wide")
st.title("🧭 Sitemap Generator")

st.markdown("""
Upload an existing `sitemap.xml`, enter URLs to **exclude** or **add**, and generate a clean sitemap.

**Features**
- ✅ XML Encoding default: `utf-8` (customizable)
- ✅ `<changefreq>monthly</changefreq>` included by default (customizable)
- ✅ `<priority>1.0</priority>` included by default (customizable)
- ✅ Add multiple URLs using **line breaks**
- ✅ Choose **one date** via calendar for `lastmod` of newly added URLs
- ✅ **Duplicate handling**: If an added URL already exists in the sitemap (or is added twice),
  we report how many duplicates were found and **exclude** them from the final output.
""")

# ----------------------------
# Defaults & Customization (moved up, right under help)
# ----------------------------
st.subheader("⚙️ Defaults & Customization")

c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    encoding = st.selectbox(
        "XML Encoding",
        options=["utf-8", "utf-16", "iso-8859-1"],
        index=0,
        help="Default is utf-8."
    )
with c2:
    changefreq = st.selectbox(
        "Default <changefreq>",
        options=["always", "hourly", "daily", "weekly", "monthly", "yearly", "never"],
        index=4,  # monthly
        help="Applied to all URLs in the generated sitemap."
    )
with c3:
    priority = st.number_input(
        "Default <priority>",
        min_value=0.0, max_value=1.0, step=0.1, value=1.0,
        help="Applied to all URLs in the generated sitemap."
    )

c4, c5, c6 = st.columns([1, 1, 1])
with c4:
    normalize_trailing_slash = st.checkbox(
        "Remove trailing slashes", value=False,
        help="Helps reduce duplicates like /page and /page/"
    )
with c5:
    lower_case_urls = st.checkbox(
        "Convert URLs to lowercase", value=False,
        help="May help deduplicate if your site treats URLs case-insensitively"
    )
with c6:
    dedupe_existing = st.checkbox(
        "Deduplicate inside uploaded sitemap", value=True,
        help="If the uploaded file itself has duplicates, keep only the first occurrence"
    )

st.divider()

# ----------------------------
# Upload & Inputs
# ----------------------------
uploaded_file = st.file_uploader("📂 Upload existing sitemap.xml", type=["xml"])

col1, col2 = st.columns(2)
with col1:
    exclude_input = st.text_area(
        "❌ URLs to EXCLUDE (one per line)",
        height=200,
        placeholder="https://example.com/page-a\nhttps://example.com/page-b"
    )
with col2:
    add_input = st.text_area(
        "➕ URLs to ADD (one per line)",
        height=200,
        placeholder="https://example.com/new-1\nhttps://example.com/new-2"
    )

add_date = st.date_input("🗓 Select lastmod date for ADDED URLs", value=date.today())

# ----------------------------
# Helper functions
# ----------------------------
def normalize_url(u: str) -> str:
    u = u.strip()
    if lower_case_urls:
        u = u.lower()
    if normalize_trailing_slash and len(u) > 1:
        # Do not remove slash if the URL is just the domain root
        if u.endswith("/") and "://" in u and u.count("/") > 2:
            u = u[:-1]
    return u

def clean_lines(raw: str):
    if not raw:
        return []
    return [normalize_url(line) for line in raw.strip().split("\n") if line.strip()]

# ----------------------------
# Generate Button
# ----------------------------
if st.button("🚀 Generate Sitemap"):
    if uploaded_file is None:
        st.warning("⚠️ Please upload a sitemap.xml file first.")
        st.stop()

    try:
        # Parse XML with namespace
        ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        ET.register_namespace('', ns['ns'])

        tree = ET.parse(uploaded_file)
        root = tree.getroot()

        # Prep inputs
        exclude_urls = set(clean_lines(exclude_input))
        add_urls = clean_lines(add_input)
        add_lastmod_str = add_date.strftime("%Y-%m-%d")

        # Collect existing URLs (preserve lastmod if present)
        existing_urls = []  # list of tuples (loc, lastmod)
        seen = set()        # to dedupe (if chosen)
        for url_elem in root.findall('ns:url', ns):
            loc_elem = url_elem.find('ns:loc', ns)
            if loc_elem is None or not loc_elem.text:
                continue

            loc_text = normalize_url(loc_elem.text)

            # Skip excluded
            if loc_text in exclude_urls:
                continue

            # Fetch lastmod if present
            lastmod_elem = url_elem.find('ns:lastmod', ns)
            lastmod = lastmod_elem.text.strip() if lastmod_elem is not None and lastmod_elem.text else None

            if dedupe_existing:
                if loc_text in seen:
                    # Drop duplicates from the uploaded sitemap if requested
                    continue
                seen.add(loc_text)

            existing_urls.append((loc_text, lastmod))

        # Build a set for fast lookup of existing locs
        existing_set = set([loc for loc, _ in existing_urls])

        # Handle new additions with duplicate check
        duplicates = []
        final_urls = existing_urls.copy()

        new_seen = set()  # to catch duplicates within add_inputs themselves
        for new_url in add_urls:
            if not new_url:
                continue
            if new_url in existing_set or new_url in new_seen:
                duplicates.append(new_url)
                continue
            final_urls.append((new_url, add_lastmod_str))
            new_seen.add(new_url)

        # Create new sitemap root
        new_root = ET.Element('urlset', xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
        for loc, lastmod in final_urls:
            url_elem = ET.SubElement(new_root, 'url')
            ET.SubElement(url_elem, 'loc').text = loc
            if lastmod:
                ET.SubElement(url_elem, 'lastmod').text = lastmod
            ET.SubElement(url_elem, 'changefreq').text = changefreq
            ET.SubElement(url_elem, 'priority').text = f"{priority:.1f}"

        # Write XML to memory
        output_io = io.BytesIO()
        ET.ElementTree(new_root).write(output_io, encoding=encoding, xml_declaration=True)
        output_io.seek(0)

        # Report
        st.success("✅ sitemap.xml has been generated successfully.")
        st.write(f"• **Total URLs in final sitemap**: `{len(final_urls)}`")
        if duplicates:
            st.warning(f"• **Duplicates detected in added URLs**: `{len(duplicates)}` (excluded from final sitemap)")
            with st.expander("See duplicate URLs"):
                dup_df = pd.DataFrame(sorted(set(duplicates)), columns=["Duplicate URL"])
                st.dataframe(dup_df, use_container_width=True)

        # Preview table
        df = pd.DataFrame(final_urls, columns=["URL", "lastmod"])
        st.dataframe(df, use_container_width=True)

        # Download
        st.download_button(
            label="📥 Download sitemap.xml",
            data=output_io,
            file_name="sitemap.xml",
            mime="application/xml"
        )

    except ET.ParseError as e:
        st.error("❌ Failed to parse the uploaded XML. Please make sure it is a valid sitemap.xml.")
        st.exception(e)
    except Exception as e:
        st.error("❌ An unexpected error occurred.")
        st.exception(e)
