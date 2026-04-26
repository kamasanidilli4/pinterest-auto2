import os
import sys
import subprocess
import time

try:
    from flask import Flask, request, render_template_string, jsonify
    from werkzeug.utils import secure_filename
except ImportError:
    print("Installing Flask...")
    subprocess.run([sys.executable, "-m", "pip", "install", "flask", "werkzeug", "--quiet"])
    from flask import Flask, request, render_template_string, jsonify
    from werkzeug.utils import secure_filename

# Import the existing functions from your script
from amazon_pin_poster import scrape_amazon_product, create_pinterest_image, post_to_pinterest

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pinterest Automation Pro</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
        
        :root {
            --bg-color: #0f172a;
            --panel-bg: rgba(30, 41, 59, 0.7);
            --border-color: rgba(255, 255, 255, 0.1);
            --accent: #E60023; /* Pinterest Red */
            --accent-hover: #ad081b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }

        body {
            margin: 0;
            padding: 0;
            font-family: 'Outfit', sans-serif;
            background: var(--bg-color);
            background-image: 
                radial-gradient(at 0% 0%, rgba(230, 0, 35, 0.15) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(56, 189, 248, 0.1) 0px, transparent 50%);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        .header {
            text-align: center;
            margin-top: 3rem;
            margin-bottom: 2rem;
            animation: fadeIn 1s ease-out;
        }

        h1 {
            font-size: 3rem;
            font-weight: 800;
            margin: 0;
            background: linear-gradient(135deg, #fff, #cbd5e1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        p.subtitle {
            color: var(--text-muted);
            font-size: 1.1rem;
            margin-top: 0.5rem;
        }

        .container {
            width: 100%;
            max-width: 600px;
            background: var(--panel-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 2rem;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            animation: slideUp 0.6s ease-out;
        }

        .form-group {
            margin-bottom: 1.5rem;
        }

        label {
            display: block;
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: #e2e8f0;
            font-size: 0.95rem;
        }

        input[type="text"], input[type="file"], select {
            width: 100%;
            padding: 0.75rem 1rem;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            color: #fff;
            font-family: 'Outfit', sans-serif;
            font-size: 1rem;
            box-sizing: border-box;
            transition: all 0.3s ease;
        }

        input[type="text"]:focus, select:focus {
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 0 3px rgba(230, 0, 35, 0.2);
        }

        .file-upload {
            position: relative;
            overflow: hidden;
        }
        
        .file-upload input[type="file"] {
            padding: 0.5rem;
        }

        .divider {
            display: flex;
            align-items: center;
            text-align: center;
            color: var(--text-muted);
            margin: 1.5rem 0;
        }

        .divider::before, .divider::after {
            content: '';
            flex: 1;
            border-bottom: 1px solid var(--border-color);
        }

        .divider:not(:empty)::before { margin-right: 1rem; }
        .divider:not(:empty)::after { margin-left: 1rem; }

        .btn-submit {
            width: 100%;
            padding: 1rem;
            background: var(--accent);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 1.1rem;
            font-weight: 600;
            font-family: 'Outfit', sans-serif;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 10px 15px -3px rgba(230, 0, 35, 0.3);
        }

        .btn-submit:hover {
            background: var(--accent-hover);
            transform: translateY(-2px);
        }
        
        .btn-submit:disabled {
            background: #475569;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }

        #loading {
            display: none;
            text-align: center;
            margin-top: 1rem;
            color: var(--text-muted);
        }

        .spinner {
            border: 3px solid rgba(255,255,255,0.1);
            width: 24px;
            height: 24px;
            border-radius: 50%;
            border-top-color: var(--accent);
            animation: spin 1s ease-in-out infinite;
            margin: 0 auto 0.5rem auto;
        }

        #result {
            display: none;
            margin-top: 1.5rem;
            padding: 1rem;
            border-radius: 10px;
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.2);
            color: #10b981;
            text-align: center;
        }

        #result a {
            color: #34d399;
            font-weight: 600;
            text-decoration: none;
        }

        #result a:hover { text-decoration: underline; }

        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        @keyframes slideUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>

    <div class="header">
        <h1>Pin Auto Pro</h1>
        <p class="subtitle">Ultimate Amazon to Pinterest Automation Engine</p>
    </div>

    <div class="container">
        <form id="posterForm" enctype="multipart/form-data">
            
            <div class="form-group">
                <label>Amazon Product URL</label>
                <input type="text" name="amazon_url" placeholder="https://amzn.to/..." required>
            </div>

            <div class="form-group">
                <label>Custom Headline (Top Text)</label>
                <input type="text" name="headline" placeholder="DON'T BUY THIS | UNTIL YOU SEE THIS!" value="DON'T BUY THIS | UNTIL YOU SEE THIS!">
            </div>

            <div class="divider">DESIGN SETTINGS</div>

            <div style="display: flex; gap: 1rem;">
                <div class="form-group" style="flex: 1;">
                    <label>Layout Style</label>
                    <select name="layout">
                        <option value="random">Random (Surprise Me!)</option>
                        <option value="classic">Classic Minimal</option>
                        <option value="modern">Modern Pill</option>
                        <option value="bold">Bold Impact</option>
                    </select>
                </div>
                
                <div class="form-group" style="flex: 1;">
                    <label>Color Theme</label>
                    <select name="theme">
                        <option value="random">Random (Surprise Me!)</option>
                        <option value="0">Sleek Dark</option>
                        <option value="1">Clean Light</option>
                        <option value="2">Navy Blue</option>
                        <option value="3">Maroon Red</option>
                    </select>
                </div>
            </div>

            <div class="divider">OR USE CUSTOM MEDIA</div>

            <div class="form-group file-upload">
                <label>Upload Custom Image/Video (Overrides Amazon)</label>
                <input type="file" name="custom_media" accept="image/*,video/mp4">
            </div>

            <button type="submit" class="btn-submit" id="submitBtn">Generate & Post to Pinterest</button>
        </form>

        <div id="loading">
            <div class="spinner"></div>
            <p>Scraping, designing, and posting... please wait.</p>
        </div>

        <div id="result"></div>
    </div>

    <script>
        document.getElementById('posterForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const form = e.target;
            const submitBtn = document.getElementById('submitBtn');
            const loading = document.getElementById('loading');
            const result = document.getElementById('result');
            
            submitBtn.disabled = true;
            loading.style.display = 'block';
            result.style.display = 'none';
            
            const formData = new FormData(form);
            
            try {
                const response = await fetch('/generate', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.success) {
                    result.style.display = 'block';
                    result.style.background = 'rgba(16, 185, 129, 0.1)';
                    result.style.borderColor = 'rgba(16, 185, 129, 0.2)';
                    result.style.color = '#10b981';
                    result.innerHTML = `🎉 Success! Pin created.<br><br><a href="${data.url}" target="_blank">View on Pinterest ➔</a>`;
                    form.reset();
                } else {
                    result.style.display = 'block';
                    result.style.background = 'rgba(239, 68, 68, 0.1)';
                    result.style.borderColor = 'rgba(239, 68, 68, 0.2)';
                    result.style.color = '#ef4444';
                    result.innerHTML = `⚠️ Error: ${data.error}`;
                }
            } catch (err) {
                result.style.display = 'block';
                result.style.background = 'rgba(239, 68, 68, 0.1)';
                result.style.borderColor = 'rgba(239, 68, 68, 0.2)';
                result.style.color = '#ef4444';
                result.innerHTML = `⚠️ Error connecting to server.`;
            }
            
            submitBtn.disabled = false;
            loading.style.display = 'none';
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/generate', methods=['POST'])
def generate():
    amazon_url = request.form.get('amazon_url', '')
    headline = request.form.get('headline', "DON'T BUY THIS | UNTIL YOU SEE THIS!")
    layout = request.form.get('layout', 'random')
    theme = request.form.get('theme', 'random')
    custom_media = request.files.get('custom_media')

    if layout == 'random': layout = None
    if theme == 'random': theme = None

    if not amazon_url:
        return jsonify({"success": False, "error": "Amazon URL is required!"})

    file_path = None

    # Handle custom media upload saving
    if custom_media and custom_media.filename:
        filename = secure_filename(custom_media.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        custom_media.save(file_path)

    # We always scrape Amazon to get the title, price, and description exactly like the terminal
    try:
        product = scrape_amazon_product(amazon_url)
        if not product or not product.get("title") or product.get("title") == "Amazon Deal":
            return jsonify({"success": False, "error": "Failed to scrape Amazon product. Try the direct link."})
        
        # If user uploaded custom media, override the scraped media!
        if file_path:
            if file_path.lower().endswith('.mp4'):
                product['video_url'] = file_path
                product['image_url'] = ""
            else:
                product['image_url'] = file_path
                product['video_url'] = ""
            product['local_media_path'] = file_path
            
    except Exception as e:
        return jsonify({"success": False, "error": f"Scraping error: {str(e)}"})

    try:
        # Override requests.get locally to handle file:// paths seamlessly in the poster generator
        import requests
        original_get = requests.get
        
        def local_get(url, *args, **kwargs):
            if url.startswith(app.config['UPLOAD_FOLDER']):
                class DummyResp:
                    def __init__(self, path):
                        with open(path, 'rb') as f:
                            self.content = f.read()
                    def raise_for_status(self): pass
                    def iter_content(self, chunk_size=8192):
                        with open(url, 'rb') as f:
                            yield f.read()
                return DummyResp(url)
            return original_get(url, *args, **kwargs)
            
        requests.get = local_get
        
        # Execute poster creation
        success = post_to_pinterest(product, headline, layout, theme)
        
        requests.get = original_get
        
        if success:
            return jsonify({
                "success": True, 
                "url": "https://pinterest.com/kdkr666/amazon-deals/"
            })
        else:
            return jsonify({"success": False, "error": "Failed to upload to Pinterest. Check console."})

    except Exception as e:
        return jsonify({"success": False, "error": f"Posting error: {str(e)}"})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("==============================================")
    print("  🚀 Pin Auto Pro WEB APP STARTING...")
    print(f"  👉 Listening on port {port}...")
    print("==============================================")
    app.run(debug=False, port=port, host='0.0.0.0')
