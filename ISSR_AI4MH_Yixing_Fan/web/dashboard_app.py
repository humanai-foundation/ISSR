import os
import sys
import gradio as gr

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(PROJECT_ROOT)

from pipeline.system1_gatekeeper import System1CrisisGatekeeper

print("[Dashboard] Loading fine-tuned XLM-RoBERTa System 1 Gatekeeper...")
gatekeeper = System1CrisisGatekeeper()

WORDCLOUD_IMG = os.path.join(PROJECT_ROOT, "output", "mental_health_wordcloud.png")
TRENDS_IMG = os.path.join(PROJECT_ROOT, "output", "google_trends_plot.png")

ANTI_SLOP_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');

:root {
    --bg-base: #090d16;
    --surface-card: #0f172a;
    --surface-elevated: #1e293b;
    --surface-subtle: #172033;
    
    --border-subtle: rgba(255, 255, 255, 0.08);
    --border-hover: rgba(255, 255, 255, 0.16);
    
    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    
    --brand-primary: #2563eb;
    --brand-primary-hover: #1d4ed8;
    
    /* Strict Semantic Colors */
    --semantic-safe: #10b981;
    --semantic-mild: #f59e0b;
    --semantic-moderate: #f97316;
    --semantic-crisis: #ef4444;
    
    --radius-sm: 6px;
    --radius-md: 10px;
    --radius-lg: 16px;
}

/* Page Canvas */
body, .gradio-container {
    font-family: 'Plus Jakarta Sans', -apple-system, sans-serif !important;
    background-color: var(--bg-base) !important;
    color: var(--text-primary) !important;
    line-height: 1.5;
}

::selection {
    background: rgba(37, 99, 235, 0.4);
    color: #ffffff;
}

/* Base Surfaces: Solid, High-Contrast (No blanket blur slop) */
.gradio-container .block,
.gradio-container .panel,
.gradio-container .gr-group,
.gradio-container .gr-box {
    background: var(--surface-card) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: var(--radius-lg) !important;
    box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.5) !important;
}

/* Input Discipline */
textarea, input[type="text"] {
    background: #060911 !important;
    border: 1px solid var(--border-subtle) !important;
    color: var(--text-primary) !important;
    border-radius: var(--radius-md) !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 0.95rem !important;
    padding: 14px 16px !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
}

textarea:focus, input[type="text"]:focus {
    border-color: var(--brand-primary) !important;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.25) !important;
    outline: none !important;
}

/* Primary Action Button (Solid, Confident Color - No generic blue/purple gradient) */
button.primary {
    background: var(--brand-primary) !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important;
    border-radius: var(--radius-md) !important;
    padding: 12px 24px !important;
    font-size: 0.9375rem !important;
    transition: background-color 0.15s ease, transform 0.1s ease !important;
}

button.primary:hover {
    background: var(--brand-primary-hover) !important;
    transform: translateY(-1px) !important;
}

/* Tabs */
.tab-nav {
    border-bottom: 1px solid var(--border-subtle) !important;
    background: transparent !important;
    gap: 4px !important;
}

.tab-nav button {
    color: var(--text-secondary) !important;
    font-weight: 600 !important;
    border-radius: var(--radius-sm) var(--radius-sm) 0 0 !important;
    padding: 10px 18px !important;
    border: none !important;
    background: transparent !important;
    font-size: 0.875rem !important;
}

.tab-nav button.selected {
    color: #ffffff !important;
    background: var(--surface-card) !important;
    border-bottom: 2px solid var(--brand-primary) !important;
}

/* Dashboard Header */
.instrument-header {
    background: var(--surface-card);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: 24px 30px;
    margin-bottom: 24px;
}

.header-meta-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 16px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border-subtle);
}

.title-wrap h1 {
    font-size: 1.5rem;
    font-weight: 700;
    margin: 0;
    color: #ffffff;
    letter-spacing: -0.02em;
}

.title-wrap p {
    font-size: 0.875rem;
    color: var(--text-secondary);
    margin: 4px 0 0 0;
}

.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(16, 185, 129, 0.1);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.25);
    padding: 5px 12px;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

.status-indicator-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #10b981;
}

.telemetry-meta-strip {
    display: flex;
    flex-wrap: wrap;
    gap: 24px;
    margin-top: 14px;
}

.meta-chip {
    font-size: 0.8125rem;
    color: var(--text-secondary);
}

.meta-chip strong {
    color: #ffffff;
    font-family: 'JetBrains Mono', monospace;
    font-variant-numeric: tabular-nums;
}

/* Focal Element: Glassmorphism strictly capped to the Instrument Housing (R-10 Dose Cap) */
.instrument-gauge-housing {
    background: rgba(30, 41, 59, 0.35);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: 24px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}

/* Spectrum Probability Bars */
.spectrum-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 10px;
    font-size: 0.8125rem;
}

.spectrum-label {
    width: 130px;
    color: var(--text-secondary);
    font-weight: 500;
}

.spectrum-track {
    flex: 1;
    height: 8px;
    background: #1e293b;
    border-radius: 4px;
    overflow: hidden;
}

.spectrum-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.5s cubic-bezier(0.16, 1, 0.3, 1);
}

.spectrum-val {
    width: 50px;
    text-align: right;
    font-family: 'JetBrains Mono', monospace;
    font-variant-numeric: tabular-nums;
    font-weight: 700;
    color: #ffffff;
}

/* Clinical Decision Summary Box */
.clinical-decision-box {
    background: #0b1120;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 18px 20px;
    margin-top: 14px;
}

.clinical-decision-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}

.clinical-tier-name {
    font-size: 1.1rem;
    font-weight: 700;
    color: #ffffff;
}

.clinical-disposition-badge {
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

/* Emergency Safety Support (High Contrast, No Endless Pulse Slop) */
.emergency-protocol-panel {
    background: rgba(239, 68, 68, 0.08);
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: var(--radius-md);
    padding: 18px 20px;
    margin-top: 14px;
}

.emergency-protocol-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.95rem;
    font-weight: 700;
    color: #f87171;
    margin-bottom: 6px;
}

.emergency-protocol-desc {
    font-size: 0.875rem;
    color: #fca5a5;
    margin-bottom: 12px;
    line-height: 1.5;
}

.emergency-btn-group {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
}

.lifeline-action-btn {
    display: inline-flex;
    align-items: center;
    background: var(--semantic-crisis);
    color: #ffffff !important;
    text-decoration: none;
    font-size: 0.8125rem;
    font-weight: 600;
    padding: 7px 16px;
    border-radius: var(--radius-sm);
    transition: opacity 0.15s;
}

.lifeline-action-btn:hover {
    opacity: 0.9;
}

.lifeline-action-secondary {
    background: rgba(255, 255, 255, 0.06);
    color: #f87171 !important;
    border: 1px solid rgba(239, 68, 68, 0.3);
}
"""

def generate_calibrated_gauge(level: int, confidence: float) -> str:
    """Calibrated Instrument SVG Gauge with smooth cubic-bezier sweep."""
    angles = {0: -67.5, 1: -22.5, 2: 22.5, 3: 67.5}
    deg = angles.get(level, -67.5)

    schemes = {
        0: {"color": "#10b981", "name": "Level 0: Safe", "desc": "Routine Interaction / Baseline"},
        1: {"color": "#f59e0b", "name": "Level 1: Mild Distress", "desc": "Sub-clinical Stress & Tension"},
        2: {"color": "#f97316", "name": "Level 2: Moderate Concern", "desc": "Depression / Hopelessness"},
        3: {"color": "#ef4444", "name": "Level 3: Acute Crisis", "desc": "Self-Harm Intent / Immediate Risk"}
    }
    cur = schemes.get(level, schemes[0])

    svg = f"""
    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%;">
        <svg viewBox="0 0 260 145" width="250" height="140" style="overflow: visible;" aria-label="Crisis Intensity Dial">
            <!-- Calibrated Arc Segments -->
            <path d="M 30 130 A 100 100 0 0 1 73 50" fill="none" stroke="#10b981" stroke-width="12" stroke-linecap="round"/>
            <path d="M 80 43 A 100 100 0 0 1 125 30" fill="none" stroke="#f59e0b" stroke-width="12"/>
            <path d="M 135 30 A 100 100 0 0 1 180 43" fill="none" stroke="#f97316" stroke-width="12"/>
            <path d="M 187 50 A 100 100 0 0 1 230 130" fill="none" stroke="#ef4444" stroke-width="12" stroke-linecap="round"/>

            <!-- Calibration Ticks -->
            <text x="32" y="142" font-size="10" font-family="'JetBrains Mono', monospace" font-weight="700" fill="#64748b" text-anchor="middle">0</text>
            <text x="82" y="32" font-size="10" font-family="'JetBrains Mono', monospace" font-weight="700" fill="#64748b" text-anchor="middle">1</text>
            <text x="178" y="32" font-size="10" font-family="'JetBrains Mono', monospace" font-weight="700" fill="#64748b" text-anchor="middle">2</text>
            <text x="228" y="142" font-size="10" font-family="'JetBrains Mono', monospace" font-weight="700" fill="#64748b" text-anchor="middle">3</text>

            <!-- Center Bearing -->
            <circle cx="130" cy="130" r="12" fill="#0b1120" stroke="rgba(255, 255, 255, 0.15)" stroke-width="2"/>
            <circle cx="130" cy="130" r="4" fill="{cur['color']}"/>

            <!-- Needle with Author-Damped Physics Sweep -->
            <g transform="rotate({deg} 130 130)" style="transition: transform 0.6s cubic-bezier(0.16, 1, 0.3, 1);">
                <polygon points="127,130 133,130 131,38 129,38" fill="#ffffff" opacity="0.9"/>
                <polygon points="129,38 131,38 130,26" fill="{cur['color']}"/>
            </g>
        </svg>

        <div style="text-align: center; margin-top: 4px;">
            <div style="font-size: 1.25rem; font-weight: 700; color: {cur['color']}; letter-spacing: -0.01em;">
                {cur['name']}
            </div>
            <div style="font-size: 0.8125rem; color: #94a3b8; font-weight: 500;">
                {cur['desc']} • <span style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: #f8fafc;">{confidence:.1%}</span> confidence
            </div>
        </div>
    </div>
    """
    return svg

def triage_pipeline(text: str):
    if not text or not text.strip():
        blank_gauge = generate_calibrated_gauge(0, 1.0)
        blank_meta = """
        <div class="clinical-decision-box">
            <div style="color: #64748b; font-size: 0.875rem;">Awaiting input text. Enter or select a statement to execute triage.</div>
        </div>
        """
        empty_bars = """
        <div>
            <div class="spectrum-row"><span class="spectrum-label">Level 0: Safe</span><div class="spectrum-track"><div class="spectrum-fill" style="width: 0%; background: #10b981;"></div></div><span class="spectrum-val">0.0%</span></div>
            <div class="spectrum-row"><span class="spectrum-label">Level 1: Mild</span><div class="spectrum-track"><div class="spectrum-fill" style="width: 0%; background: #f59e0b;"></div></div><span class="spectrum-val">0.0%</span></div>
            <div class="spectrum-row"><span class="spectrum-label">Level 2: Moderate</span><div class="spectrum-track"><div class="spectrum-fill" style="width: 0%; background: #f97316;"></div></div><span class="spectrum-val">0.0%</span></div>
            <div class="spectrum-row"><span class="spectrum-label">Level 3: Crisis</span><div class="spectrum-track"><div class="spectrum-fill" style="width: 0%; background: #ef4444;"></div></div><span class="spectrum-val">0.0%</span></div>
        </div>
        """
        return blank_gauge, empty_bars, blank_meta, ""

    result = gatekeeper.predict(text)
    level = result["intensity_level"]
    conf = result["confidence"]
    probs = result["probabilities"]

    gauge_svg = generate_calibrated_gauge(level, conf)

    p0 = probs["Level 0 (Safe)"] * 100
    p1 = probs["Level 1 (Anxiety / Mild)"] * 100
    p2 = probs["Level 2 (Depression / Moderate)"] * 100
    p3 = probs["Level 3 (Acute Crisis)"] * 100

    bars_html = f"""
    <div>
        <div class="spectrum-row">
            <span class="spectrum-label">Level 0: Safe</span>
            <div class="spectrum-track"><div class="spectrum-fill" style="width: {p0:.1f}%; background: #10b981;"></div></div>
            <span class="spectrum-val">{p0:.1f}%</span>
        </div>
        <div class="spectrum-row">
            <span class="spectrum-label">Level 1: Mild Tension</span>
            <div class="spectrum-track"><div class="spectrum-fill" style="width: {p1:.1f}%; background: #f59e0b;"></div></div>
            <span class="spectrum-val">{p1:.1f}%</span>
        </div>
        <div class="spectrum-row">
            <span class="spectrum-label">Level 2: Depression</span>
            <div class="spectrum-track"><div class="spectrum-fill" style="width: {p2:.1f}%; background: #f97316;"></div></div>
            <span class="spectrum-val">{p2:.1f}%</span>
        </div>
        <div class="spectrum-row">
            <span class="spectrum-label">Level 3: Acute Crisis</span>
            <div class="spectrum-track"><div class="spectrum-fill" style="width: {p3:.1f}%; background: #ef4444;"></div></div>
            <span class="spectrum-val">{p3:.1f}%</span>
        </div>
    </div>
    """

    routing_target = "System 2 Supervisor & Crisis Hotline Routing" if result["is_crisis"] else "System 1 Finalized (Routine Engagement)"
    disposition_text = "CRISIS ESCALATION ACTIVE" if result["is_crisis"] else "NON-CRISIS TRIAGE"
    disposition_color = "#ef4444" if result["is_crisis"] else "#10b981"

    meta_box = f"""
    <div class="clinical-decision-box">
        <div class="clinical-decision-header">
            <span class="clinical-tier-name">{result['intensity_name']}</span>
            <span class="clinical-disposition-badge" style="color: {disposition_color};">
                {disposition_text}
            </span>
        </div>
        <p style="margin: 0 0 12px 0; font-size: 0.875rem; color: #94a3b8; line-height: 1.5;">
            {result['description']}
        </p>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; padding-top: 10px; border-top: 1px solid var(--border-subtle); font-size: 0.8125rem;">
            <div>
                <span style="color: #64748b; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; display: block; margin-bottom: 2px;">Action Protocol</span>
                <span style="color: #f8fafc; font-weight: 600;">{result['suggested_action']}</span>
            </div>
            <div>
                <span style="color: #64748b; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; display: block; margin-bottom: 2px;">Pipeline Disposition</span>
                <span style="color: #60a5fa; font-weight: 600;">{routing_target}</span>
            </div>
        </div>
    </div>
    """

    emergency_block = ""
    if result["is_crisis"]:
        emergency_block = """
        <div class="emergency-protocol-panel">
            <div class="emergency-protocol-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                <span>Crisis Intervention Protocol Active</span>
            </div>
            <p class="emergency-protocol-desc">
                Acute distress signals identified. Free, confidential support from certified crisis responders is accessible 24/7:
            </p>
            <div class="emergency-btn-group">
                <a href="tel:988" class="lifeline-action-btn">Call / Text 988 (USA & Canada)</a>
                <a href="sms:85258" class="lifeline-action-btn lifeline-action-secondary">Text SHOUT to 85258 (UK)</a>
                <a href="https://findahelpline.com" target="_blank" class="lifeline-action-btn lifeline-action-secondary">International Crisis Directory</a>
            </div>
        </div>
        """

    return gauge_svg, bars_html, meta_box, emergency_block

with gr.Blocks(title="AI4MH Triage Instrument") as demo:
    gr.HTML(
        """
        <header class="instrument-header">
            <div class="header-meta-row">
                <div class="title-wrap">
                    <h1>Mental Health Crisis Triage Instrument</h1>
                    <p>Non-autoregressive System 1 classifier operating across 4 ordinal intensity tiers and 100+ languages.</p>
                </div>
                <div class="status-badge">
                    <span class="status-indicator-dot"></span>
                    <span>System 1 Online</span>
                </div>
            </div>
            <div class="telemetry-meta-strip">
                <span class="meta-chip">Model: <strong>XLM-RoBERTa Base</strong></span>
                <span class="meta-chip">Benchmark: <strong>80.2% F1</strong></span>
                <span class="meta-chip">Inference Latency: <strong>&lt; 90 ms</strong></span>
                <span class="meta-chip">Scale: <strong>0–3 Ordinal</strong></span>
            </div>
        </header>
        """
    )

    with gr.Tabs():
        with gr.Tab("Triage Evaluation"):
            with gr.Row():
                with gr.Column(scale=6):
                    input_text = gr.Textbox(
                        label="Source Conversational Text",
                        placeholder="Enter statement, journal entry, or conversational thought to evaluate...",
                        lines=5,
                        value="I had a wonderful evening with my friends at the park."
                    )
                    
                    with gr.Row():
                        eval_btn = gr.Button("Evaluate Intensity", variant="primary")
                        clear_btn = gr.ClearButton(components=[input_text], value="Clear Text")

                    gr.Markdown("##### Authenticated Test Statements")
                    gr.Examples(
                        examples=[
                            ["I had a wonderful evening with my friends at the park."],
                            ["I am feeling so panicked about my exam tomorrow and cannot breathe properly."],
                            ["Nothing brings me joy anymore. I just feel completely empty and exhausted every day."],
                            ["I can't go on living anymore, I just want to end it all tonight."],
                            ["Siento que ya no puedo más con esta tristeza y quiero desaparecer."],
                            ["Je me sens tellement anxieux et incapable de dormir ces derniers temps."],
                            ["मुझे बहुत घबराहट और तनाव महसूस हो रहा है।"]
                        ],
                        inputs=input_text
                    )

                with gr.Column(scale=6):
                    with gr.Group():
                        with gr.Group(elem_classes=["instrument-gauge-housing"]):
                            gauge_view = gr.HTML()
                        bars_view = gr.HTML()
                        meta_view = gr.HTML()
                        emergency_view = gr.HTML()

            eval_btn.click(
                fn=triage_pipeline,
                inputs=input_text,
                outputs=[gauge_view, bars_view, meta_view, emergency_view]
            )
            demo.load(
                fn=triage_pipeline,
                inputs=input_text,
                outputs=[gauge_view, bars_view, meta_view, emergency_view]
            )

        with gr.Tab("Corpus Analytics"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("##### Sentiment Word Cloud")
                    if os.path.exists(WORDCLOUD_IMG):
                        gr.Image(WORDCLOUD_IMG, label="Corpus Word Cloud")
                    else:
                        gr.Markdown("*Word cloud not found in `output/`.*")
                with gr.Column():
                    gr.Markdown("##### Longitudinal Search Trends")
                    if os.path.exists(TRENDS_IMG):
                        gr.Image(TRENDS_IMG, label="Google Search Trends")
                    else:
                        gr.Markdown("*Google Trends plot not found in `output/`.*")

        with gr.Tab("System Specifications"):
            gr.Markdown(
                """
                ### Two-Stage Non-Autoregressive Triage Architecture
                
                * **System 1 (XLM-RoBERTa):** Evaluates full sequence in parallel with sub-100ms CPU latency. Does not use autoregressive generation loops.
                * **System 2 (Generative Supervisor):** Triggered on Level 2 (Moderate Depression) or Level 3 (Acute Crisis) to manage compassionate conversation and safety lifeline routing.
                
                #### Ordinal Severity Criteria
                * **Level 0 (Safe):** Everyday sentiment, neutral or positive narrative.
                * **Level 1 (Mild Tension):** Academic pressure, situational anxiety, daily stress.
                * **Level 2 (Moderate Depression):** Depressive affect, perceived burdensomeness, persistent anhedonia.
                * **Level 3 (Acute Crisis):** Explicit suicidal ideation, immediate plans, active lethal risk.
                """
            )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False, css=ANTI_SLOP_CSS)
