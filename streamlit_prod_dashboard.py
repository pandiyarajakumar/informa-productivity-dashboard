import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import io

# Page configuration
st.set_page_config(
    page_title="Informa Productivity Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main {
        background-color: #f8fafc;
    }
    .stMetric {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    div[data-testid="stMetricValue"] {
        font-size: 28px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if 'raw_data' not in st.session_state:
    st.session_state.raw_data = None
if 'lookup_data' not in st.session_state:
    st.session_state.lookup_data = None
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None

def parse_csv_file(uploaded_file):
    """Parse uploaded CSV file"""
    try:
        df = pd.read_csv(uploaded_file, encoding='utf-8')
        return df
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(uploaded_file, encoding='latin-1')
            return df
        except Exception as e:
            st.error(f"Error reading file with latin-1 encoding: {str(e)}")
            return None
    except Exception as e:
        st.error(f"Error reading file: {str(e)}")
        return None

def clean_column_names(df):
    """Clean column names by stripping whitespace"""
    df.columns = df.columns.str.strip()
    return df

def process_production_data(raw_df, lookup_df=None):
    """Process production data with team mapping"""
    try:
        # Clean column names
        raw_df = clean_column_names(raw_df)
        if lookup_df is not None:
            lookup_df = clean_column_names(lookup_df)
        
        st.info(f"Processing {len(raw_df)} rows from CSV...")
        
        # Show available columns for debugging
        st.write("Available columns:", list(raw_df.columns))
        
        processed_data = []
        
        for idx, row in raw_df.iterrows():
            # Get agent name - try multiple column names
            agent_name = None
            for col in ['Disp', 'Employee name', 'Agent', 'Name']:
                if col in row and pd.notna(row[col]) and str(row[col]).strip():
                    agent_name = str(row[col]).strip()
                    break
            
            if not agent_name:
                continue
            
            # Default team to UK
            team = 'UK'
            
            # Try to find team from lookup data
            if lookup_df is not None and not lookup_df.empty:
                for _, lookup_row in lookup_df.iterrows():
                    lookup_name = str(lookup_row.get('Employee name', '')).strip()
                    if agent_name.lower() in lookup_name.lower() or lookup_name.lower() in agent_name.lower():
                        team = lookup_row.get('Team', 'UK')
                        break
            
            # Parse numeric values - try multiple column name variations
            cont_processed = 0
            for col in ['Cont Procsd', 'Cont Procsd ', 'Contacts Processed', 'Contact Processed']:
                if col in row:
                    val = pd.to_numeric(row[col], errors='coerce')
                    if pd.notna(val):
                        cont_processed = int(val)
                        break
            
            target = 0
            for col in ['Cont Proc - Target', 'Contact Processed Target', 'Target']:
                if col in row:
                    val = pd.to_numeric(row[col], errors='coerce')
                    if pd.notna(val):
                        target = int(val)
                        break
            
            eff_cont = 0
            for col in ['Eff   Cont', 'Eff Cont', 'Eff   Cont ', 'Effective Contacts', 'Effective Contacts Achieved']:
                if col in row:
                    val = pd.to_numeric(row[col], errors='coerce')
                    if pd.notna(val):
                        eff_cont = int(val)
                        break
            
            # Parse productivity percentage
            prod_percent = 0
            for col in ['Cont Proc - Prod%', 'Productivity Achieved %', 'Productivity']:
                if col in row:
                    val = str(row[col]).replace('%', '').strip()
                    val = pd.to_numeric(val, errors='coerce')
                    if pd.notna(val):
                        prod_percent = float(val)
                        break
            
            net_cont = 0
            for col in ['Net Cont', 'Net Contacts']:
                if col in row:
                    val = pd.to_numeric(row[col], errors='coerce')
                    if pd.notna(val):
                        net_cont = int(val)
                        break
            
            # Get other fields
            prod_hours = row.get('Prod Hours', '0:00:00')
            level = row.get('Level', 'L2')
            
            processed_data.append({
                'Agent': agent_name,
                'Team': team,
                'Contacts_Processed': cont_processed,
                'Target': target,
                'Deficit': target - cont_processed,
                'Productivity': prod_percent,
                'Effective_Contacts': eff_cont,
                'Net_Contacts': net_cont,
                'Prod_Hours': prod_hours,
                'Level': level,
                'Date': datetime.now().strftime('%Y-%m-%d')
            })
        
        result_df = pd.DataFrame(processed_data)
        st.success(f"✅ Successfully processed {len(result_df)} agent records!")
        return result_df
    
    except Exception as e:
        st.error(f"❌ Error processing data: {str(e)}")
        st.exception(e)  # Show full error trace
        return pd.DataFrame()

def get_productivity_color(productivity):
    """Return color based on productivity level"""
    if productivity >= 100:
        return '#10b981'  # Green
    elif productivity >= 80:
        return '#f59e0b'  # Orange
    else:
        return '#ef4444'  # Red

def create_summary_metrics(df):
    """Create summary metric cards"""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_contacts = df['Contacts_Processed'].sum()
        total_target = df['Target'].sum()
        st.metric(
            label="📞 Total Contacts Processed",
            value=f"{total_contacts:,}",
            delta=f"Target: {total_target:,}"
        )
    
    with col2:
        total_deficit = df['Deficit'].sum()
        status = "Surplus" if total_deficit <= 0 else "Deficit"
        st.metric(
            label=f"📊 {status}",
            value=f"{abs(total_deficit):,}",
            delta="vs Target",
            delta_color="normal" if total_deficit <= 0 else "inverse"
        )
    
    with col3:
        avg_productivity = df['Productivity'].mean()
        st.metric(
            label="⚡ Average Productivity",
            value=f"{avg_productivity:.1f}%",
            delta=f"{len(df)} agents"
        )
    
    with col4:
        achievers = len(df[df['Productivity'] >= 100])
        achievement_rate = (achievers / len(df) * 100) if len(df) > 0 else 0
        st.metric(
            label="🎯 Achievement Rate",
            value=f"{achievement_rate:.1f}%",
            delta=f"{achievers}/{len(df)} agents"
        )

def create_productivity_chart(df):
    """Create productivity bar chart"""
    fig = px.bar(
        df.sort_values('Productivity', ascending=True),
        x='Productivity',
        y='Agent',
        orientation='h',
        title='Productivity by Agent',
        color='Productivity',
        color_continuous_scale=['#ef4444', '#f59e0b', '#10b981'],
        labels={'Productivity': 'Productivity %', 'Agent': 'Agent Name'}
    )
    fig.update_layout(
        height=max(400, len(df) * 30),
        showlegend=False,
        xaxis_title="Productivity %",
        yaxis_title="",
        plot_bgcolor='white'
    )
    return fig

def create_contacts_chart(df):
    """Create contacts processed vs target chart"""
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        name='Processed',
        x=df['Agent'],
        y=df['Contacts_Processed'],
        marker_color='#10b981'
    ))
    
    fig.add_trace(go.Bar(
        name='Target',
        x=df['Agent'],
        y=df['Target'],
        marker_color='#f59e0b'
    ))
    
    fig.update_layout(
        title='Contacts Processed vs Target',
        xaxis_title="Agent",
        yaxis_title="Number of Contacts",
        barmode='group',
        height=500,
        plot_bgcolor='white',
        xaxis={'tickangle': -45}
    )
    
    return fig

def create_team_comparison(df):
    """Create team-wise comparison"""
    team_summary = df.groupby('Team').agg({
        'Contacts_Processed': 'sum',
        'Target': 'sum',
        'Productivity': 'mean',
        'Agent': 'count'
    }).reset_index()
    team_summary.columns = ['Team', 'Total_Contacts', 'Total_Target', 'Avg_Productivity', 'Agent_Count']
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        name='Avg Productivity',
        x=team_summary['Team'],
        y=team_summary['Avg_Productivity'],
        marker_color='#667eea',
        text=team_summary['Avg_Productivity'].round(1),
        textposition='outside',
        texttemplate='%{text}%'
    ))
    
    fig.update_layout(
        title='Team-wise Average Productivity',
        xaxis_title="Team",
        yaxis_title="Average Productivity %",
        height=400,
        plot_bgcolor='white',
        showlegend=False
    )
    
    return fig, team_summary

def create_detailed_table(df):
    """Create detailed performance table"""
    # Add productivity status
    df['Status'] = df['Productivity'].apply(
        lambda x: '🟢 Achieved' if x >= 100 else ('🟠 Close' if x >= 80 else '🔴 Below')
    )
    
    # Format the dataframe for display
    display_df = df[[
        'Agent', 'Team', 'Level', 'Contacts_Processed', 'Target', 
        'Deficit', 'Productivity', 'Effective_Contacts', 'Status'
    ]].copy()
    
    display_df.columns = [
        'Agent Name', 'Team', 'Level', 'Processed', 'Target', 
        'Deficit', 'Productivity %', 'Eff. Contacts', 'Status'
    ]
    
    return display_df

def export_to_csv(df):
    """Export filtered data to CSV"""
    output = io.BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)
    return output

# Main App
def main():
    # Header
    st.title("📊 Informa Agentwise Productivity Dashboard")
    st.markdown("### Real-time productivity tracking and analytics")
    
    # Sidebar for file upload and filters
    with st.sidebar:
        st.header("📁 Data Upload")
        
        # Production data upload
        prod_file = st.file_uploader(
            "Upload Production Data (CSV)",
            type=['csv'],
            help="Upload your daily production statistics CSV file",
            key="prod_upload"
        )
        
        if prod_file is not None:
            raw_df = parse_csv_file(prod_file)
            if raw_df is not None:
                st.session_state.raw_data = raw_df
                st.success(f"✅ Loaded {len(st.session_state.raw_data)} records")
                
                # Show preview
                with st.expander("📋 Preview Data"):
                    st.dataframe(st.session_state.raw_data.head())
        
        # Lookup data upload (optional)
        lookup_file = st.file_uploader(
            "Upload Lookup Data (CSV) - Optional",
            type=['csv'],
            help="Upload team assignment lookup file",
            key="lookup_upload"
        )
        
        if lookup_file is not None:
            lookup_df = parse_csv_file(lookup_file)
            if lookup_df is not None:
                st.session_state.lookup_data = lookup_df
                st.success(f"✅ Loaded {len(st.session_state.lookup_data)} lookup records")
        
        st.markdown("---")
        
        # Process data button
        if st.session_state.raw_data is not None:
            if st.button("🔄 Process Data", type="primary", use_container_width=True):
                with st.spinner("Processing data..."):
                    st.session_state.processed_data = process_production_data(
                        st.session_state.raw_data,
                        st.session_state.lookup_data
                    )
                
                if st.session_state.processed_data is not None and not st.session_state.processed_data.empty:
                    st.balloons()
        else:
            st.info("👆 Upload production data first")
    
    # Main content area
    if st.session_state.processed_data is not None and not st.session_state.processed_data.empty:
        df = st.session_state.processed_data
        
        # Filters in sidebar
        with st.sidebar:
            st.header("🔍 Filters")
            
            # Team filter
            teams = ['ALL'] + sorted(df['Team'].unique().tolist())
            selected_team = st.selectbox("Select Team", teams)
            
            # Agent filter
            if selected_team != 'ALL':
                agents = ['ALL'] + sorted(df[df['Team'] == selected_team]['Agent'].unique().tolist())
            else:
                agents = ['ALL'] + sorted(df['Agent'].unique().tolist())
            selected_agent = st.selectbox("Select Agent", agents)
            
            # Apply filters
            filtered_df = df.copy()
            if selected_team != 'ALL':
                filtered_df = filtered_df[filtered_df['Team'] == selected_team]
            if selected_agent != 'ALL':
                filtered_df = filtered_df[filtered_df['Agent'] == selected_agent]
            
            st.markdown("---")
            
            # Export button
            if len(filtered_df) > 0:
                csv_data = export_to_csv(filtered_df)
                st.download_button(
                    label="📥 Export Report",
                    data=csv_data,
                    file_name=f"productivity_report_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        
        # Display summary metrics
        st.markdown("### 📈 Key Metrics")
        create_summary_metrics(filtered_df)
        
        st.markdown("---")
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.plotly_chart(create_productivity_chart(filtered_df), use_container_width=True)
        
        with col2:
            if selected_team == 'ALL' and selected_agent == 'ALL':
                team_chart, team_summary = create_team_comparison(filtered_df)
                st.plotly_chart(team_chart, use_container_width=True)
                
                # Team summary table
                st.markdown("#### Team Summary")
                st.dataframe(
                    team_summary.style.format({
                        'Total_Contacts': '{:,.0f}',
                        'Total_Target': '{:,.0f}',
                        'Avg_Productivity': '{:.1f}%',
                        'Agent_Count': '{:.0f}'
                    }),
                    use_container_width=True,
                    hide_index=True
                )
        
        # Contacts chart
        st.markdown("### 📊 Contacts Processed vs Target")
        st.plotly_chart(create_contacts_chart(filtered_df), use_container_width=True)
        
        # Detailed table
        st.markdown("### 📋 Detailed Agent Performance")
        detailed_table = create_detailed_table(filtered_df)
        
        # Style the dataframe
        st.dataframe(
            detailed_table.style.format({
                'Processed': '{:,.0f}',
                'Target': '{:,.0f}',
                'Deficit': '{:,.0f}',
                'Productivity %': '{:.1f}',
                'Eff. Contacts': '{:,.0f}'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Footer with last update time
        st.markdown("---")
        st.markdown(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        
    else:
        # Welcome screen
        st.info("👋 Welcome! Please upload your production data CSV file using the sidebar to get started.")
        
        st.markdown("""
        ### 📝 How to Use:
        
        1. **Upload Production Data**: Click on the file uploader in the sidebar and select your daily production CSV file
        2. **Upload Lookup Data (Optional)**: Upload team assignment lookup file if you have one
        3. **Process Data**: Click the "🔄 Process Data" button to analyze your data
        4. **Explore**: Use filters to view specific teams or agents
        5. **Export**: Download reports as needed
        
        ### 📊 Features:
        - ✅ Real-time productivity tracking
        - ✅ Team-wise and agent-wise analysis
        - ✅ Interactive charts and visualizations
        - ✅ Export functionality
        - ✅ Color-coded performance indicators
        """)

if __name__ == "__main__":
    main()
