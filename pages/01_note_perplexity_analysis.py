import streamlit as st
import pandas as pd
from io import StringIO
import plotly.express as px

# Set page title
st.title('Note Perplexity Analysis')

@st.cache_data
def load_data():
    # First read the raw file and handle the escaped commas
    processed_lines = []
    with open('zettel_perplexity.csv', 'r') as file:
        # Add header as first line
        processed_lines.append(next(file).strip())

        for line in file:
            # Replace escaped commas with a temporary marker
            processed = line.replace('\\,', '<<COMMA>>')
            processed_lines.append(processed)

    # Create a string buffer with processed lines
    processed_data = '\n'.join(processed_lines)

    # Read the processed data with pandas
    df = pd.read_csv(StringIO(processed_data))

    # Restore the original commas in the filename
    df['Filename'] = df['Filename'].str.replace('<<COMMA>>', ',')

    return df

df = load_data()

# Create an interactive bar chart using Plotly
fig = px.bar(
    df.sort_values('Perplexity'),  # Sort by perplexity
    x='Filename',
    y='Perplexity',
    title='Perplexity Values by Note',
    hover_data=['Cross Entropy']  # Show cross entropy on hover
)

# Customize the layout
fig.update_layout(
    xaxis_title="Note Filename",
    yaxis_title="Perplexity",
    xaxis_tickangle=-45  # Rotate x-axis labels for better readability
)

# Display the plot
st.plotly_chart(fig, use_container_width=True)

# Optional: Display the raw data below the chart
if st.checkbox('Show raw data', key='show_raw_data'):
    st.dataframe(df)

# Basic statistical summary
st.header("Statistical Analysis")
st.write(f"""
- Mean perplexity: {df['Perplexity'].mean():.2f}
- Median perplexity: {df['Perplexity'].median():.2f}
- Standard deviation: {df['Perplexity'].std():.2f}
""")

# Distribution analysis
import plotly.figure_factory as ff

fig_dist = ff.create_distplot(
    [df['Perplexity']],
    ['Perplexity'],
    bin_size=5,
    show_rug=True
)
st.subheader("Perplexity Distribution")
st.plotly_chart(fig_dist, use_container_width=True)

# Identify statistical outliers using IQR method
Q1 = df['Perplexity'].quantile(0.25)
Q3 = df['Perplexity'].quantile(0.75)
IQR = Q3 - Q1
outliers = df[
    (df['Perplexity'] < (Q1 - 1.5 * IQR)) |
    (df['Perplexity'] > (Q3 + 1.5 * IQR))
]

if not outliers.empty:
    st.subheader("Statistical Outliers (1.5 IQR method)")
    st.dataframe(
        outliers[['Filename', 'Perplexity', 'Cross Entropy']]
        .sort_values('Perplexity', ascending=False)
    )


# Create filtered dataset without outliers
df_filtered = df[
    (df['Perplexity'] >= (Q1 - 1.5 * IQR)) &
    (df['Perplexity'] <= (Q3 + 1.5 * IQR))
]

st.subheader("Distribution Without Outliers")

# Create distribution plot for filtered data
fig_dist_filtered = ff.create_distplot(
    [df_filtered['Perplexity']],
    ['Perplexity (Outliers Removed)'],
    bin_size=5,
    show_rug=True
)
st.plotly_chart(fig_dist_filtered, use_container_width=True)

# Show basic stats for filtered data
st.write(f"""
- Mean perplexity (without outliers): {df_filtered['Perplexity'].mean():.2f}
- Median perplexity (without outliers): {df_filtered['Perplexity'].median():.2f}
- Standard deviation (without outliers): {df_filtered['Perplexity'].std():.2f}
""")


# Create an interactive bar chart using Plotly
filtered_fig = px.bar(
    df_filtered.sort_values('Perplexity'),  # Sort by perplexity
    x='Filename',
    y='Perplexity',
    title='Perplexity Values by Note',
    hover_data=['Cross Entropy']  # Show cross entropy on hover
)

# Customize the layout
filtered_fig.update_layout(
    xaxis_title="Note Filename",
    yaxis_title="Perplexity",
    xaxis_tickangle=-45  # Rotate x-axis labels for better readability
)

# Display the plot
st.plotly_chart(filtered_fig, use_container_width=True)

# Optional: Display the raw data below the chart
if st.checkbox('Show filtered data', key='filtered_data'):
    st.dataframe(df_filtered)
