import dash
from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objs as go

# Prepare data
df1 = pd.read_csv("food-greenhouse-gas-emissions-across-the-supply-chain.csv")
df2 = pd.read_csv("freshwater-withdrawals-per-kilogram-of-food-product.csv")
df3 = pd.read_csv("land-use-per-kilogram-of-food-product.csv")

for df in [df1, df2, df3]:
    df['Entity'] = df['Entity'].astype(str).str.strip().str.lower()

common_items = set(df1['Entity']) & set(df2['Entity']) & set(df3['Entity'])
df1 = df1[df1['Entity'].isin(common_items) & (df1['Entity'] != 'nuts')]
df2 = df2[df2['Entity'].isin(common_items) & (df2['Entity'] != 'nuts')]
df3 = df3[df3['Entity'].isin(common_items) & (df3['Entity'] != 'nuts')]

df = df1.merge(df2, on='Entity').merge(df3, on='Entity')
df['Entity'] = df['Entity'].str.title()

# Calculate Environmental scores
scored_df = df.copy()
scored_df['Water Score'] = scored_df['water used per kilogram'].rank(method='min', ascending=True)
scored_df['Water Score'] = (scored_df['Water Score'] - 1) / (scored_df['Water Score'].max() - 1) * 100
scored_df['Land Score'] = scored_df['land used per kilogram'].rank(method='min', ascending=True)
scored_df['Land Score'] = (scored_df['Land Score'] - 1) / (scored_df['Land Score'].max() - 1) * 100

ghg_cols = ["Land use", "Farm", "Animal feed", "Processing", "Transport", "Retail", "Packaging", "Losses"]
scored_df['GHG Total'] = scored_df[ghg_cols].sum(axis=1)
scored_df['GHG Score'] = scored_df['GHG Total'].rank(method='min', ascending=True)
scored_df['GHG Score'] = (scored_df['GHG Score'] - 1) / (scored_df['GHG Score'].max() - 1) * 100
scored_df['Environmental Score'] = (scored_df['Water Score'] + scored_df['Land Score'] + scored_df['GHG Score']) / 3
scored_df['Star Rating'] = scored_df['Environmental Score'].apply(lambda s: 5 if s <= 20 else 4 if s <= 40 else 3 if s <= 60 else 2 if s <= 80 else 1)

food_groups = {
    "vegetables_fruits": ["Apples", "Bananas", "Citrus Fruit", "Berries And Grapes", "Onions And Leeks", "Peas", "Tomatoes", "Root Vegetables"],
    "proteins": ["Eggs", "Pig Meat", "Poultry Meat", "Cheese", "Beef (Dairy Herd)", "Beef (Beef Herd)", "Fish (Farmed)", "Lamb And Mutton", "Tofu"],
    "carbs": ["Wheat & Rye", "Rice", "Potatoes", "Maize", "Barley"],
    "drinks": ["Wine", "Milk", "Soy Milk", "Coffee"]
}

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.FLATLY], suppress_callback_exceptions=True)

app.layout = dbc.Container([
    html.H1("🌿 Environmental Impact of Food Products", style={"textAlign": "center", "marginTop": "30px", "color": "#2C3E50"}),

    dbc.Tabs([
        dbc.Tab(label="Overview", tab_id="tab-overview"),
        dbc.Tab(label="Interactive Impact Viewer", tab_id="tab-impact"),
        dbc.Tab(label="Environmental Scoring", tab_id="tab-score"),
    ], id="tabs", active_tab="tab-overview", className="mb-4"),

    html.Div(id="tabs-content")
], fluid=True)

@app.callback(Output("tabs-content", "children"), Input("tabs", "active_tab"))
def render_tab(tab):
    if tab == "tab-overview":
        return dbc.Card([
            dbc.CardBody([
                html.H4("Explore the Environmental Impact", className="card-title text-primary"),
                html.P("This dashboard lets you explore how different food products impact the environment in terms of greenhouse gas emissions, water use, and land use."),
            ])
        ], className="shadow-sm")

    elif tab == "tab-impact":
        return dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.Label("Select Environmental Metric:"),
                    dcc.Dropdown(id="impact-type", options=[
                        {"label": "Greenhouse Gas Emissions (CO2eq/kg)", "value": "ghg"},
                        {"label": "Water Usage (L/kg)", "value": "water"},
                        {"label": "Land Usage (m²/kg)", "value": "land"}
                    ], value="ghg", clearable=False, style={"marginBottom": "20px"}),

                    html.Label("Select Food Categories:"),
                    dcc.Checklist(id="category-selector", options=[
                        {"label": "Vegetables and Fruits", "value": "vegetables_fruits"},
                        {"label": "Proteins", "value": "proteins"},
                        {"label": "Carbohydrates", "value": "carbs"},
                        {"label": "Drinks", "value": "drinks"}
                    ], value=[])
                ])
            ], className="shadow-sm"), width=4),

            dbc.Col(dbc.Card([
                dbc.CardBody([dcc.Graph(id="impact-graph")])
            ], className="shadow-sm"), width=8)
        ])

    elif tab == "tab-score":
        return dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.Label("Select Food Item:"),
                    dcc.Dropdown(id="food-selector-score", options=[{"label": item, "value": item} for item in scored_df['Entity']], value=scored_df['Entity'].iloc[0], style={"marginBottom": "20px"}),
                    html.Div(id="score-output")
                ])
            ], className="shadow-sm"), width=4),

            dbc.Col(dbc.Card([
                dbc.CardBody([dcc.Graph(id="score-bar-graph")])
            ], className="shadow-sm"), width=8)
        ])

@app.callback(Output("impact-graph", "figure"), [Input("impact-type", "value"), Input("category-selector", "value")])
def update_graph(impact_type, selected_categories):
    selected_items = set()
    for category in selected_categories:
        selected_items.update(food_groups.get(category, []))

    filtered_df = df[df['Entity'].isin(selected_items)].copy()

    if impact_type == "ghg":
        keep_cols = ["Farm", "Transport", "Losses"]
        other_cols = list(set(["Land use", "Farm", "Animal feed", "Processing", "Transport", "Retail", "Packaging", "Losses"]) - set(keep_cols))
        filtered_df["Other"] = filtered_df[other_cols].sum(axis=1)
        stacked_cols = ["Farm", "Transport", "Losses", "Other"]
        filtered_df["Total"] = filtered_df[stacked_cols].sum(axis=1)
        filtered_df = filtered_df.sort_values("Total", ascending=False).head(10)

        fig = go.Figure()
        colors = {'Farm': '#D2B48C', 'Transport': '#FF6F61', 'Losses': '#AAAAAA', 'Other': '#F4D03F'}

        for col in stacked_cols:
            fig.add_trace(go.Bar(
                y=filtered_df['Entity'],
                x=filtered_df[col],
                name=col,
                orientation='h',
                marker=dict(color=colors[col])
            ))

        fig.update_layout(barmode='stack', title="Greenhouse Gas Emissions by Food Item (CO2eq/kg)", yaxis=dict(autorange="reversed"),xaxis_title="CO2 Emissions (kg per kg of food)", yaxis_title="Food Item",)
        return fig

    elif impact_type == "water":
        filtered_df = filtered_df.sort_values("water used per kilogram", ascending=False).head(10)
        return go.Figure(go.Bar(
            y=filtered_df['Entity'],
            x=filtered_df['water used per kilogram'],
            orientation='h',
            marker=dict(color='#6699CC')
        )).update_layout(title="Water Usage by Food Item (L/kg)", yaxis=dict(autorange="reversed"), xaxis_title="Liters of Water per kg", yaxis_title="Food Item",)

    elif impact_type == "land":
        filtered_df = filtered_df.sort_values("land used per kilogram", ascending=False).head(10)
        return go.Figure(go.Bar(
            y=filtered_df['Entity'],
            x=filtered_df['land used per kilogram'],
            orientation='h',
            marker=dict(color='#A0522D')
        )).update_layout(title="Land Usage by Food Item (m²/kg)", yaxis=dict(autorange="reversed"), xaxis_title="Land Used (m² per kg)",yaxis_title="Food Item")

@app.callback(
    [Output("score-output", "children"), Output("score-bar-graph", "figure")],
    Input("food-selector-score", "value")
)
def display_score(selected_food):
    row = scored_df[scored_df['Entity'] == selected_food].iloc[0]
    stars = "★" * row['Star Rating'] + "☆" * (5 - row['Star Rating'])
    color_map = {5: "#4CAF50", 4: "#8BC34A", 3: "#FFC107", 2: "#FF7043", 1: "#D32F2F"}
    labels = {5: "Excellent", 4: "Good", 3: "Moderate", 2: "Poor", 1: "Very Poor"}

    fig = go.Figure(go.Bar(
        x=['Water Score', 'Land Score', 'GHG Score'],
        y=[row['Water Score'], row['Land Score'], row['GHG Score']],
        marker=dict(color=['#6699CC', '#A0522D', '#555555']),
        width=[0.4, 0.4, 0.4]
    ))
    fig.update_layout(yaxis=dict(range=[0, 100]), xaxis_title="Impact Type", yaxis_title="Score (0 - 100)")

    return html.Div([
        html.H3(f"Environmental Score for {selected_food}"),
        html.H4(f"Overall: {row['Environmental Score']:.1f}"),
        html.Div(stars, style={"fontSize": "48px", "color": color_map[row['Star Rating']]}),
        html.P(f"Rating: {labels[row['Star Rating']]}" , style={"fontSize": "24px", "color": color_map[row['Star Rating']]})
    ]), fig

if __name__ == '__main__':
    app.run(debug=True)

























