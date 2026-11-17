# DealGuard Website

A Flask website prototype based on the uploaded DealGuard BCA project notebook.

## Run locally
1. Install Python 3.10+.
2. Open a terminal in this folder.
3. Run `python -m venv .venv` and activate it.
4. Run `pip install -r requirements.txt`.
5. Copy your project's `category_price_reference.csv` into this folder (optional but recommended).
6. Run `python app.py`.
7. Open http://127.0.0.1:5000

## Google Colab
Upload/extract this folder into `/content/DealGuard`, then run:
```python
%cd /content/DealGuard
!pip install -r requirements.txt
!python app.py
```
For a clickable Colab proxy link, start the server in the background:
```python
import subprocess, sys, time
from google.colab import output
server = subprocess.Popen([sys.executable, "app.py"])
time.sleep(3)
website_url = output.eval_js("google.colab.kernel.proxyPort(5000)")
print("DealGuard website:", website_url)
```
Keep the Colab runtime running while using the link. It is temporary.

## Project notes
- Product URL is retained and displayed, but automatic scraping is not promised; retailer pages may block automated requests.
- Manual product entry is supported.
- The website uses a transparent rule-based score. It does not claim a trained ML model is being used for this score.
- To enable category price comparison, place `category_price_reference.csv` next to `app.py`.
- Set `DEALGUARD_SECRET_KEY` to a strong random value before public deployment.
