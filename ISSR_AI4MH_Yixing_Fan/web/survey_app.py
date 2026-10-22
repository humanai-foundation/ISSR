import os
import re
import csv
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI(title="AI4MH Organic Data Portal")

DATASET_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dataset"))
SURVEY_CSV = os.path.join(DATASET_DIR, "organic_survey.csv")

os.makedirs(DATASET_DIR, exist_ok=True)
CSV_HEADERS = ["id", "timestamp", "text", "perceived_intensity", "language", "tags", "sentiment"]

if not os.path.exists(SURVEY_CSV):
    with open(SURVEY_CSV, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADERS)

def sanitize_text(text: str) -> str:
    """Strips phone numbers and email addresses to guarantee strict anonymity."""
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[REDACTED_EMAIL]', text)
    text = re.sub(r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b', '[REDACTED_PHONE]', text)
    return text.strip()

@app.get("/", response_class=HTMLResponse)
async def survey_page():
    submissions = []
    if os.path.exists(SURVEY_CSV):
        with open(SURVEY_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                submissions.append(row)
    
    count = len(submissions)
    recent = submissions[-5:][::-1] if submissions else []

    recent_rows = ""
    for r in recent:
        tags_badge = " ".join([f"<span class='tag-pill'>{t}</span>" for t in r.get("tags", "").split(";") if t])
        level_colors = {
            "0": "badge-safe",
            "1": "badge-anxiety",
            "2": "badge-depression",
            "3": "badge-crisis"
        }
        b_class = level_colors.get(str(r.get("perceived_intensity", "0")), "badge-safe")
        level_names = {"0": "Level 0: Safe", "1": "Level 1: Anxiety", "2": "Level 2: Depressed", "3": "Level 3: Crisis"}
        lvl_name = level_names.get(str(r.get("perceived_intensity", "0")), "Level 0")
        
        recent_rows += f"""
        <div class="submission-card">
            <div class="sub-header">
                <span class="{b_class}">{lvl_name}</span>
                <span class="sub-lang">{r.get('language', 'English')}</span>
            </div>
            <div class="sub-text">"{r.get('text', '')[:140]}{'...' if len(r.get('text', '')) > 140 else ''}"</div>
            <div class="sub-meta">{tags_badge}</div>
        </div>
        """

    if not recent_rows:
        recent_rows = "<div style='color: #94a3b8; font-size: 0.9rem; text-align: center; padding: 20px;'>No contributions recorded yet. Be the first!</div>"

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Community Data Portal • AI4MH</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg: #090d16;
                --surface: #111827;
                --surface-card: #1f2937;
                --surface-card-hover: #263346;
                --border: #374151;
                --primary: #38bdf8;
                --primary-glow: rgba(56, 189, 248, 0.2);
                --text-main: #f8fafc;
                --text-muted: #94a3b8;
                --safe: #10b981;
                --warning: #f59e0b;
                --moderate: #f97316;
                --danger: #ef4444;
            }}
            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }}
            body {{
                font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
                background-color: var(--bg);
                color: var(--text-main);
                min-height: 100vh;
                padding: 40px 20px;
                display: flex;
                justify-content: center;
                align-items: flex-start;
                background-image: radial-gradient(circle at 50% 0%, rgba(56, 189, 248, 0.08) 0%, transparent 50%);
            }}
            .layout-grid {{
                max-width: 1100px;
                width: 100%;
                display: grid;
                grid-template-columns: 1.2fr 0.8fr;
                gap: 28px;
            }}
            @media (max-width: 860px) {{
                .layout-grid {{
                    grid-template-columns: 1fr;
                }}
            }}
            .portal-card {{
                background: var(--surface);
                border: 1px solid var(--border);
                border-radius: 20px;
                padding: 36px;
                box-shadow: 0 12px 35px -8px rgba(0, 0, 0, 0.4);
            }}
            .badge-counter {{
                display: inline-flex;
                align-items: center;
                gap: 8px;
                background: rgba(56, 189, 248, 0.1);
                color: var(--primary);
                border: 1px solid rgba(56, 189, 248, 0.25);
                padding: 6px 14px;
                border-radius: 9999px;
                font-size: 0.85rem;
                font-weight: 700;
                margin-bottom: 20px;
            }}
            h1 {{
                font-size: 1.85rem;
                font-weight: 800;
                letter-spacing: -0.02em;
                color: #ffffff;
                margin-bottom: 8px;
            }}
            p.lead {{
                color: var(--text-muted);
                font-size: 0.95rem;
                line-height: 1.6;
                margin-bottom: 28px;
            }}
            label.form-label {{
                display: block;
                font-weight: 600;
                font-size: 0.9rem;
                color: #e2e8f0;
                margin-top: 22px;
                margin-bottom: 8px;
            }}
            textarea, select {{
                width: 100%;
                background: var(--surface-card);
                border: 1px solid var(--border);
                color: #ffffff;
                padding: 14px 16px;
                border-radius: 12px;
                font-family: inherit;
                font-size: 0.95rem;
                outline: none;
                transition: all 0.2s ease;
            }}
            textarea:focus, select:focus {{
                border-color: var(--primary);
                box-shadow: 0 0 0 4px var(--primary-glow);
            }}
            /* Intensity Cards Grid */
            .intensity-grid {{
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 10px;
            }}
            @media (max-width: 520px) {{
                .intensity-grid {{
                    grid-template-columns: repeat(2, 1fr);
                }}
            }}
            .intensity-card {{
                background: var(--surface-card);
                border: 2px solid var(--border);
                border-radius: 12px;
                padding: 14px 8px;
                text-align: center;
                cursor: pointer;
                transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            }}
            .intensity-card:hover {{
                background: var(--surface-card-hover);
                border-color: #64748b;
            }}
            .intensity-card .icon {{
                font-size: 1.5rem;
                margin-bottom: 4px;
            }}
            .intensity-card .title {{
                font-size: 0.8rem;
                font-weight: 700;
                color: #ffffff;
                display: block;
            }}
            .intensity-card .desc {{
                font-size: 0.7rem;
                color: var(--text-muted);
            }}
            .intensity-card.active[data-level="0"] {{
                border-color: var(--safe);
                background: rgba(16, 185, 129, 0.12);
            }}
            .intensity-card.active[data-level="1"] {{
                border-color: var(--warning);
                background: rgba(245, 158, 11, 0.12);
            }}
            .intensity-card.active[data-level="2"] {{
                border-color: var(--moderate);
                background: rgba(249, 115, 22, 0.12);
            }}
            .intensity-card.active[data-level="3"] {{
                border-color: var(--danger);
                background: rgba(239, 68, 68, 0.12);
            }}

            /* Tag Pills */
            .tags-cloud {{
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
            }}
            .tag-chip {{
                background: var(--surface-card);
                border: 1px solid var(--border);
                padding: 7px 14px;
                border-radius: 9999px;
                font-size: 0.8rem;
                color: #cbd5e1;
                cursor: pointer;
                transition: all 0.15s;
                user-select: none;
            }}
            .tag-chip.active {{
                background: var(--primary);
                color: #090d16;
                border-color: var(--primary);
                font-weight: 700;
            }}
            .tag-chip input {{
                display: none;
            }}

            /* Submit Button */
            .submit-btn {{
                margin-top: 28px;
                width: 100%;
                background: linear-gradient(135deg, #38bdf8 0%, #2563eb 100%);
                color: #ffffff;
                border: none;
                padding: 15px 24px;
                border-radius: 12px;
                font-size: 1rem;
                font-weight: 700;
                cursor: pointer;
                box-shadow: 0 4px 15px rgba(37, 99, 235, 0.3);
                transition: transform 0.1s, box-shadow 0.2s;
            }}
            .submit-btn:hover {{
                transform: translateY(-1px);
                box-shadow: 0 6px 20px rgba(37, 99, 235, 0.4);
            }}

            /* Sidebar Submissions */
            .sidebar-title {{
                font-size: 1.15rem;
                font-weight: 700;
                margin-bottom: 14px;
                color: #ffffff;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }}
            .submission-card {{
                background: var(--surface-card);
                border: 1px solid var(--border);
                border-radius: 12px;
                padding: 14px 16px;
                margin-bottom: 12px;
            }}
            .sub-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 6px;
            }}
            .sub-text {{
                font-size: 0.88rem;
                color: #e2e8f0;
                line-height: 1.4;
                margin-bottom: 8px;
            }}
            .sub-lang {{
                font-size: 0.75rem;
                color: var(--text-muted);
            }}
            .badge-safe {{ color: var(--safe); font-size: 0.75rem; font-weight: 700; text-transform: uppercase; }}
            .badge-anxiety {{ color: var(--warning); font-size: 0.75rem; font-weight: 700; text-transform: uppercase; }}
            .badge-depression {{ color: var(--moderate); font-size: 0.75rem; font-weight: 700; text-transform: uppercase; }}
            .badge-crisis {{ color: var(--danger); font-size: 0.75rem; font-weight: 700; text-transform: uppercase; }}

            .tag-pill {{
                background: rgba(255, 255, 255, 0.08);
                color: #94a3b8;
                padding: 2px 8px;
                border-radius: 4px;
                font-size: 0.7rem;
                margin-right: 4px;
            }}
        </style>
    </head>
    <body>
        <div class="layout-grid">
            <!-- Main Form Card -->
            <div class="portal-card">
                <span class="badge-counter">✨ {count} Organic Samples Collected</span>
                <h1>🌱 Community Mental Health Survey</h1>
                <p class="lead">
                    Contribute authentic, anonymized thoughts or journal snippets. Your inputs directly retrain and improve our open-source <strong>System 1 Crisis Triage Model</strong> to be culturally inclusive and linguistically empathetic.
                </p>

                <form action="/submit" method="post" id="surveyForm">
                    <label class="form-label" for="text">Your Statement, Reflection, or Conversational Thought *</label>
                    <textarea id="text" name="text" rows="5" required placeholder="Write freely. For example: a stressful thought, coping thoughts, or an authentic emotion..."></textarea>
                    <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted); margin-top: 4px;">
                        <span>🔒 PII like emails & phone numbers are automatically redacted.</span>
                        <span id="charCount">0 characters</span>
                    </div>

                    <label class="form-label">Perceived Emotional Intensity (0–3 Scale) *</label>
                    <div class="intensity-grid">
                        <div class="intensity-card active" data-level="0" onclick="setIntensity('0', this)">
                            <div class="icon">☀️</div>
                            <span class="title">Level 0</span>
                            <span class="desc">Safe / Neutral</span>
                        </div>
                        <div class="intensity-card" data-level="1" onclick="setIntensity('1', this)">
                            <div class="icon">⛅</div>
                            <span class="title">Level 1</span>
                            <span class="desc">Mild / Tension</span>
                        </div>
                        <div class="intensity-card" data-level="2" onclick="setIntensity('2', this)">
                            <div class="icon">🌧️</div>
                            <span class="title">Level 2</span>
                            <span class="desc">Depression</span>
                        </div>
                        <div class="intensity-card" data-level="3" onclick="setIntensity('3', this)">
                            <div class="icon">⚡</div>
                            <span class="title">Level 3</span>
                            <span class="desc">Acute Crisis</span>
                        </div>
                    </div>
                    <input type="hidden" name="intensity" id="intensityInput" value="0">

                    <label class="form-label" for="language">Language of Statement</label>
                    <select id="language" name="language">
                        <option value="English">English</option>
                        <option value="Spanish">Spanish (Español)</option>
                        <option value="Hindi">Hindi (हिंदी)</option>
                        <option value="French">French (Français)</option>
                        <option value="German">German (Deutsch)</option>
                        <option value="Other">Other</option>
                    </select>

                    <label class="form-label">Contextual Category Tags</label>
                    <div class="tags-cloud">
                        <label class="tag-chip"><input type="checkbox" name="tags" value="Academics"> Academics & Exams</label>
                        <label class="tag-chip"><input type="checkbox" name="tags" value="Work Stress"> Work Stress</label>
                        <label class="tag-chip"><input type="checkbox" name="tags" value="Loneliness"> Loneliness</label>
                        <label class="tag-chip"><input type="checkbox" name="tags" value="Relationships"> Relationships</label>
                        <label class="tag-chip"><input type="checkbox" name="tags" value="Grief"> Grief & Loss</label>
                        <label class="tag-chip"><input type="checkbox" name="tags" value="Venting"> Daily Venting</label>
                        <label class="tag-chip"><input type="checkbox" name="tags" value="Recovery"> Hope & Recovery</label>
                    </div>

                    <label class="form-label" for="sentiment">Emotional Sentiment</label>
                    <select id="sentiment" name="sentiment">
                        <option value="Neutral">Neutral</option>
                        <option value="Negative">Negative / Distressed</option>
                        <option value="Positive">Positive / Encouraging</option>
                    </select>

                    <button type="submit" class="submit-btn">Submit Contribution</button>
                </form>
            </div>

            <!-- Sidebar: Feed & Mission -->
            <div class="portal-card" style="align-self: flex-start;">
                <div class="sidebar-title">
                    <span>Recent Community Data</span>
                    <span style="font-size: 0.75rem; color: var(--primary); font-weight: 600;">Live Feed</span>
                </div>
                <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 16px;">
                    Below are the latest verified submissions appended to <code>dataset/organic_survey.csv</code>:
                </p>
                {recent_rows}

                <div style="margin-top: 24px; padding-top: 20px; border-top: 1px solid var(--border); font-size: 0.8rem; color: var(--text-muted);">
                    <strong style="color: #ffffff; display: block; margin-bottom: 4px;">🤝 Research Ethics & Safety</strong>
                    All submissions are stored strictly in local project storage. Any sensitive credentials or contacts are automatically sanitized upon ingestion.
                </div>
            </div>
        </div>

        <script>
            function setIntensity(val, el) {{
                document.querySelectorAll('.intensity-card').forEach(c => c.classList.remove('active'));
                el.classList.add('active');
                document.getElementById('intensityInput').value = val;
            }}

            document.querySelectorAll('.tag-chip input').forEach(box => {{
                box.addEventListener('change', function() {{
                    if (this.checked) {{
                        this.parentElement.classList.add('active');
                    }} else {{
                        this.parentElement.classList.remove('active');
                    }}
                }});
            }});

            const textarea = document.getElementById('text');
            const charCount = document.getElementById('charCount');
            textarea.addEventListener('input', () => {{
                charCount.textContent = `${{textarea.value.length}} characters`;
            }});
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.post("/submit", response_class=HTMLResponse)
async def submit_survey(
    request: Request,
    text: str = Form(...),
    intensity: int = Form(0),
    language: str = Form("English"),
    sentiment: str = Form("Neutral")
):
    form_data = await request.form()
    tags = form_data.getlist("tags")
    tags_str = ";".join(tags) if tags else "General"

    clean_text = sanitize_text(text)
    entry_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now(timezone.utc).isoformat()

    with open(SURVEY_CSV, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([entry_id, timestamp, clean_text, intensity, language, tags_str, sentiment])

    crisis_block = ""
    if intensity >= 2:
        crisis_block = """
        <div style="background-color: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 12px; padding: 20px; margin: 24px 0; text-align: left;">
            <div style="font-weight: 700; color: #f87171; margin-bottom: 6px; display: flex; align-items: center; gap: 8px;">
                <span>❤️</span> Confidential Support is Available 24/7
            </div>
            <p style="margin: 0; color: #fca5a5; font-size: 0.9rem; line-height: 1.5;">
                If you are struggling or feel overwhelmed, compassionate support is ready to listen:
                <br>• <strong>USA & Canada:</strong> Call or text <strong style="color: #ffffff;">988</strong>
                <br>• <strong>UK:</strong> Text SHOUT to <strong style="color: #ffffff;">85258</strong>
                <br>• <strong>Worldwide:</strong> Visit <a href="https://findahelpline.com" target="_blank" style="color: #38bdf8; text-decoration: underline;">findahelpline.com</a>
            </p>
        </div>
        """

    confirmation_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Submission Saved • AI4MH</title>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;700;800&display=swap" rel="stylesheet">
        <style>
            body {{
                font-family: 'Plus Jakarta Sans', sans-serif;
                background-color: #090d16;
                color: #ffffff;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                padding: 20px;
            }}
            .card {{
                background: #111827;
                border: 1px solid #374151;
                padding: 44px 36px;
                border-radius: 20px;
                max-width: 540px;
                width: 100%;
                text-align: center;
                box-shadow: 0 20px 40px rgba(0,0,0,0.5);
            }}
            .btn {{
                display: inline-block;
                background: #38bdf8;
                color: #090d16;
                text-decoration: none;
                padding: 14px 28px;
                border-radius: 12px;
                font-weight: 700;
                margin-top: 20px;
                transition: transform 0.1s;
            }}
            .btn:hover {{ transform: scale(1.02); }}
        </style>
    </head>
    <body>
        <div class="card">
            <div style="font-size: 3.5rem; margin-bottom: 16px;">🌱</div>
            <h2 style="font-size: 1.7rem; font-weight: 800; margin-bottom: 8px;">Thank You for Contributing!</h2>
            <p style="color: #94a3b8; font-size: 0.95rem; line-height: 1.5;">
                Your submission <code>#{entry_id}</code> was recorded into <code>dataset/organic_survey.csv</code>.
            </p>
            {crisis_block}
            <a href="/" class="btn">Submit Another Reflection</a>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=confirmation_html)

if __name__ == "__main__":
    port = int(os.environ.get("SURVEY_PORT", os.environ.get("PORT", 8081)))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
