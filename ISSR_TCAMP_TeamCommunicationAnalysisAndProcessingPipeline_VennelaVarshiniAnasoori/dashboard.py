import json
import base64
import pandas as pd
import dash
from dash import dcc, html, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import dash_bootstrap_components as dbc

# Dashboard Theme Configuration
CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

body {
    background-color: #0F172A; /* Deep Slate Background */
    color: #F8FAFC;
    font-family: 'Inter', sans-serif;
    margin: 0;
    -webkit-font-smoothing: antialiased;
}

.dashboard-header {
    background: linear-gradient(90deg, #1E293B 0%, #0F172A 100%);
    border-bottom: 1px solid #334155;
    padding: 20px 30px;
    margin-bottom: 30px;
}

.dashboard-title {
    font-weight: 700;
    font-size: 24px;
    color: #F8FAFC;
    letter-spacing: -0.5px;
    margin: 0;
}

.dashboard-subtitle {
    font-weight: 400;
    font-size: 14px;
    color: #94A3B8;
    margin-top: 5px;
}

.sci-card {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 12px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    padding: 20px;
    margin: 8px; /* Force separation */
    height: 100%;
}

.kpi-title {
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #94A3B8;
    margin-bottom: 10px;
}

.kpi-value {
    font-size: 32px;
    font-weight: 700;
    letter-spacing: -1px;
}

/* Specific KPI Colors */
.val-duration { color: #F8FAFC; }
.val-silence { color: #06B6D4; } /* Cyan */
.val-gini { color: #8B5CF6; } /* Violet */
.val-interrupt { color: #F43F5E; } /* Rose */
.val-latency { color: #10B981; } /* Emerald */

.upload-box {
    border: 2px dashed #475569;
    border-radius: 8px;
    background-color: #0F172A;
    transition: all 0.2s ease;
    cursor: pointer;
    margin: 8px; /* Force separation */
}
.upload-box:hover {
    border-color: #38BDF8;
    background-color: rgba(56, 189, 248, 0.05);
}

.chart-title {
    font-size: 16px;
    font-weight: 600;
    color: #F1F5F9;
    margin-bottom: 15px;
    border-bottom: 1px solid #334155;
    padding-bottom: 10px;
}
"""

# Initialize Dash
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)
app.title = "TCAMP Research Analytics"

# Inject Custom CSS
app.index_string = f'''
<!DOCTYPE html>
<html>
    <head>
        {{%metas%}}
        <title>{{%title%}}</title>
        {{%favicon%}}
        {{%css%}}
        <style>
            {CUSTOM_CSS}
        </style>
    </head>
    <body>
        {{%app_entry%}}
        <footer>
            {{%config%}}
            {{%scripts%}}
            {{%renderer%}}
        </footer>
    </body>
</html>
'''

# Chart Theme Configurations
sci_palette = ['#06B6D4', '#8B5CF6', '#10B981', '#F59E0B', '#F43F5E', '#3B82F6', '#EC4899']

def get_base_layout():
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color="#94A3B8"),
        margin=dict(t=30, l=10, r=10, b=30),
        xaxis=dict(showgrid=False, zeroline=False, linecolor="#334155", tickcolor="#334155"),
        yaxis=dict(showgrid=True, gridcolor="#334155", zeroline=False, linecolor="#334155", tickcolor="#334155"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )


# Layout
app.layout = html.Div([
    # Header
    html.Div([
        html.H1("TCAMP Behavioral Analytics", className="dashboard-title"),
        html.P("Human-Factors Audio Telemetry & NLP Tagging Dashboard", className="dashboard-subtitle")
    ], className="dashboard-header"),
    
    dbc.Container([
        # Control Panel / Uploaders
        dbc.Row([
            dbc.Col(
                html.Div([
                    html.Div("Data Pipeline Controls", className="chart-title"),
                    dbc.Row([
                        dbc.Col(
                            dcc.Upload(
                                id='upload-metrics',
                                children=html.Div(['Drop ', html.B('behavioral_metrics.json'), ' here']),
                                className="upload-box",
                                style={'height': '50px', 'lineHeight': '50px', 'textAlign': 'center'}
                            ), width=6, className="pe-2"
                        ),
                        dbc.Col(
                            dcc.Upload(
                                id='upload-transcript',
                                children=html.Div(['Drop ', html.B('tagged_transcript.json'), ' here']),
                                className="upload-box",
                                style={'height': '50px', 'lineHeight': '50px', 'textAlign': 'center'}
                            ), width=6, className="ps-2"
                        )
                    ], className="mt-2"),
                    html.Div(id='upload-status', className="mt-2 text-info", style={'fontSize': '12px', 'fontWeight': '500'})
                ], className="sci-card mb-4"),
                width=12
            )
        ]),

        # KPIs
        dbc.Row(id='kpi-row', className="mb-4 g-3"),

        # Charts Row 1
        dbc.Row([
            dbc.Col(
                html.Div([
                    html.Div("Talk Time Distribution", className="chart-title"),
                    dcc.Graph(id='talk-time-pie', config={'displayModeBar': False})
                ], className="sci-card"), 
                width=12, lg=5, className="mb-4"
            ),
            dbc.Col(
                html.Div([
                    html.Div("Dialogue Acts Breakdown", className="chart-title"),
                    dcc.Graph(id='dialogue-act-bar', config={'displayModeBar': False})
                ], className="sci-card"), 
                width=12, lg=7, className="mb-4"
            ),
        ]),

        # Charts Row 2
        dbc.Row([
            dbc.Col(
                html.Div([
                    html.Div("Sentiment & Safety Events", className="chart-title"),
                    dcc.Graph(id='sentiment-safety-timeline', config={'displayModeBar': False})
                ], className="sci-card"), 
                width=12, className="mb-4"
            ),
        ]),

        # Charts Row 3
        dbc.Row([
            dbc.Col(
                html.Div([
                    html.Div("Turn-Taking Flow", className="chart-title"),
                    dcc.Graph(id='turn-taking-gantt', config={'displayModeBar': False})
                ], className="sci-card"), 
                width=12, className="mb-4"
            )
        ])
    ], fluid=True, className="px-4")
])

data_store = {'metrics': None, 'transcript': None}

def parse_contents(contents):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    return json.loads(decoded.decode('utf-8'))

@app.callback(
    [Output('upload-status', 'children'),
     Output('kpi-row', 'children'),
     Output('talk-time-pie', 'figure'),
     Output('dialogue-act-bar', 'figure'),
     Output('sentiment-safety-timeline', 'figure'),
     Output('turn-taking-gantt', 'figure')],
    [Input('upload-metrics', 'contents'),
     Input('upload-transcript', 'contents')],
    [State('upload-metrics', 'filename'),
     State('upload-transcript', 'filename')]
)
def update_dashboard(metrics_content, transcript_content, metrics_name, transcript_name):
    status_msg = ""
    if metrics_content:
        data_store['metrics'] = parse_contents(metrics_content)
        status_msg += f"Loaded Metrics ({metrics_name}). "
    if transcript_content:
        data_store['transcript'] = parse_contents(transcript_content)
        status_msg += f"Loaded NLP Transcript ({transcript_name})."
        
    empty_fig = go.Figure()
    empty_fig.update_layout(**get_base_layout())
    empty_fig.update_xaxes(showgrid=False, zeroline=False, visible=False)
    empty_fig.update_yaxes(showgrid=False, zeroline=False, visible=False)
    
    kpis = []
    fig_pie = empty_fig
    fig_bar = empty_fig
    fig_timeline = empty_fig
    fig_gantt = empty_fig

    metrics = data_store['metrics']
    transcript = data_store['transcript']

    if metrics:
        kpis = [
            dbc.Col(html.Div([html.Div("Total Duration", className="kpi-title"), html.Div(f"{metrics.get('meeting_duration_seconds', 0):.1f}s", className="kpi-value val-duration")], className="sci-card"), width=12, md=2, className="px-2"),
            dbc.Col(html.Div([html.Div("Silence Ratio", className="kpi-title"), html.Div(f"{metrics.get('silence_ratio', 0)*100:.1f}%", className="kpi-value val-silence")], className="sci-card"), width=12, md=2, className="px-2"),
            dbc.Col(html.Div([html.Div("Gini Centrality", className="kpi-title"), html.Div(f"{metrics.get('centralization_gini', 0):.3f}", className="kpi-value val-gini")], className="sci-card"), width=12, md=3, className="px-2"),
            dbc.Col(html.Div([html.Div("Interruptions", className="kpi-title"), html.Div(f"{metrics.get('interruptions', 0)}", className="kpi-value val-interrupt")], className="sci-card"), width=12, md=2, className="px-2"),
            dbc.Col(html.Div([html.Div("Avg Latency", className="kpi-title"), html.Div(f"{metrics.get('average_response_latency_seconds', 0):.2f}s", className="kpi-value val-latency")], className="sci-card"), width=12, md=3, className="px-2"),
        ]

        # 1. Pie Chart
        talk_times = metrics.get("total_talk_time_by_speaker", {})
        if talk_times:
            df_pie = pd.DataFrame(list(talk_times.items()), columns=['Speaker', 'Talk Time'])
            fig_pie = px.pie(df_pie, names='Speaker', values='Talk Time', hole=0.6, color_discrete_sequence=sci_palette)
            fig_pie.update_traces(textposition='inside', textinfo='percent+label', hoverinfo='label+value', marker=dict(line=dict(color='#1E293B', width=2)))
            fig_pie.update_layout(**get_base_layout())
            fig_pie.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10))

    if transcript:
        df_trans = pd.DataFrame(transcript)
        
        # 2. Bar Chart
        if 'dialogue_act' in df_trans.columns and 'speaker' in df_trans.columns:
            act_counts = df_trans.groupby(['speaker', 'dialogue_act']).size().reset_index(name='count')
            fig_bar = px.bar(act_counts, x='speaker', y='count', color='dialogue_act', barmode='stack', color_discrete_sequence=sci_palette)
            fig_bar.update_layout(**get_base_layout())
            fig_bar.update_xaxes(title="")
            fig_bar.update_yaxes(title="Count")

        # 3. Timeline Scatter
        if 'start' in df_trans.columns and 'sentiment_shift' in df_trans.columns:
            mask = (df_trans['sentiment_shift'].isin(['Anxious', 'Frustrated'])) | (df_trans['psychological_safety'].isin(['Hedging', 'Permission-Seeking']))
            df_events = df_trans[mask].copy()
            if not df_events.empty:
                df_events['Event'] = df_events.apply(lambda row: f"Sentiment: {row['sentiment_shift']}" if row['sentiment_shift'] in ['Anxious', 'Frustrated'] else f"Safety: {row['psychological_safety']}", axis=1)
                
                # Custom color mapping for events
                event_colors = {"Sentiment: Anxious": "#F59E0B", "Sentiment: Frustrated": "#F43F5E", "Safety: Hedging": "#8B5CF6", "Safety: Permission-Seeking": "#06B6D4"}
                
                fig_timeline = px.scatter(df_events, x='start', y='speaker', color='Event', hover_data=['text'], color_discrete_map=event_colors)
                fig_timeline.update_traces(marker=dict(size=14, symbol='diamond', line=dict(width=1, color='#F8FAFC')), hovertemplate="<b>%{y}</b><br>Time: %{x}s<br>Utterance: <i>%{customdata[0]}</i><extra></extra>")
                fig_timeline.update_layout(**get_base_layout())
                fig_timeline.update_yaxes(title="")
                fig_timeline.update_xaxes(title="Timeline (Seconds)")
            else:
                fig_timeline.update_layout(title="No Anxious/Frustrated or Hedging events detected.")

        # 4. Gantt Chart
        if 'start' in df_trans.columns and 'end' in df_trans.columns:
            df_trans['start_dt'] = pd.to_datetime(df_trans['start'], unit='s')
            df_trans['end_dt'] = pd.to_datetime(df_trans['end'], unit='s')
            fig_gantt = px.timeline(df_trans, x_start="start_dt", x_end="end_dt", y="speaker", color="speaker", color_discrete_sequence=sci_palette)
            fig_gantt.update_xaxes(tickformat="%M:%S", title="Timeline (MM:SS)")
            fig_gantt.update_yaxes(title="")
            # Thicken the Gantt bars for visibility
            fig_gantt.update_traces(width=0.6, hovertemplate="<b>%{y}</b><br>%{customdata[0]}<extra></extra>", customdata=df_trans[['text']].values)
            fig_gantt.update_layout(**get_base_layout())
            fig_gantt.update_layout(showlegend=False)

    return status_msg, kpis, fig_pie, fig_bar, fig_timeline, fig_gantt


if __name__ == '__main__':
    print("initializing telemetry dashboard on http://127.0.0.1:8050...")
    app.run(debug=True, port=8050)
