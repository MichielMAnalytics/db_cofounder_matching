#!/usr/bin/env python3
"""
Antler Cofounder Matching Dashboard
Simple but insightful dashboard for visualizing Antler participant data
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from collections import Counter
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="Antler Cofounder Dashboard",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load environment variables
load_dotenv()

@st.cache_resource
def init_connection():
    """Initialize MongoDB connection"""
    mongo_uri = os.getenv('MONGO_URI')
    if not mongo_uri:
        st.error("MongoDB URI not found in .env file")
        return None
    try:
        client = MongoClient(mongo_uri)
        return client['last-recruiter-mvp']
    except Exception as e:
        st.error(f"Failed to connect to MongoDB: {e}")
        return None

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_data():
    """Load candidate data from MongoDB"""
    db = init_connection()
    if db is None:
        return pd.DataFrame()
    
    try:
        collection = db['users']
        candidates = list(collection.find({}))
        
        # Convert to DataFrame
        df = pd.DataFrame(candidates)
        
        # Clean and prepare data
        if '_id' in df.columns:
            df['_id'] = df['_id'].astype(str)
        
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

def main():
    # Password protection
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        st.title("🔐 Antler Dashboard Access")
        st.markdown("### Please enter the dashboard password")
        
        password = st.text_input("Password", type="password", key="password_input")
        
        if st.button("Login"):
            # Get password from environment variable or use default
            correct_password = os.getenv('DASHBOARD_PASSWORD', 'antler2024')
            
            if password == correct_password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Incorrect password. Please try again.")
        
        st.info("💡 Contact the dashboard administrators for access credentials.")
        return
    
    # Add logout button in sidebar
    with st.sidebar:
        if st.button("🚪 Logout"):
            st.session_state.authenticated = False
            st.rerun()
    
    # Title and description
    st.title("🚀 Antler Cofounder Matching Dashboard")
    st.markdown("### Discover potential cofounders and explore the Antler cohort")
    
    # Load data
    df = load_data()
    
    if df.empty:
        st.warning("No data available. Please check your MongoDB connection.")
        return
    
    # Sidebar filters
    st.sidebar.header("🔍 Filters")
    
    # Status filter
    status_options = ['All'] + list(df['status'].unique()) if 'status' in df.columns else ['All']
    selected_status = st.sidebar.selectbox("Team Status", status_options)
    
    # Founder type filter
    if 'founder_type' in df.columns:
        founder_type_options = ['All'] + sorted(df['founder_type'].dropna().unique().tolist())
        selected_founder_type = st.sidebar.selectbox("Founder Type", founder_type_options)
    else:
        selected_founder_type = 'All'
    
    # Location filter
    if 'location' in df.columns:
        location_options = ['All'] + sorted(df['location'].dropna().unique().tolist())
        selected_location = st.sidebar.selectbox("Location", location_options)
    else:
        selected_location = 'All'
    
    # Apply filters
    filtered_df = df.copy()
    if selected_status != 'All' and 'status' in df.columns:
        filtered_df = filtered_df[filtered_df['status'] == selected_status]
    if selected_founder_type != 'All' and 'founder_type' in df.columns:
        filtered_df = filtered_df[filtered_df['founder_type'] == selected_founder_type]
    if selected_location != 'All' and 'location' in df.columns:
        filtered_df = filtered_df[filtered_df['location'] == selected_location]
    
    # Key metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Participants", len(filtered_df))
    
    with col2:
        if 'status' in df.columns:
            looking_count = len(filtered_df[filtered_df['status'] == 'Looking for co-founder'])
            st.metric("Looking for Cofounder", looking_count)
    
    with col3:
        if 'founder_type' in df.columns:
            technical_count = len(filtered_df[filtered_df['founder_type'] == 'technical'])
            st.metric("Technical Founders", technical_count)
    
    with col4:
        if 'founder_type' in df.columns:
            business_count = len(filtered_df[filtered_df['founder_type'] == 'business'])
            st.metric("Business Founders", business_count)
    
    with col5:
        if 'location' in df.columns:
            unique_locations = filtered_df['location'].nunique()
            st.metric("Unique Locations", unique_locations)
    
    st.markdown("---")
    
    # Main content area with tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "👥 Candidates", "🎯 Skills Analysis", "📍 Location Insights"])
    
    with tab1:
        # First row - three main charts
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Status distribution bar chart
            st.subheader("Team Status Distribution")
            if 'status' in df.columns:
                status_counts = filtered_df['status'].value_counts()
                fig_status = px.bar(
                    x=status_counts.index,
                    y=status_counts.values,
                    labels={'x': 'Status', 'y': 'Count'},
                    color=status_counts.index,
                    color_discrete_map={
                        'Looking for co-founder': '#10B981',
                        'In a team': '#3B82F6'
                    },
                    text=status_counts.values
                )
                fig_status.update_traces(texttemplate='%{text}', textposition='outside')
                fig_status.update_layout(showlegend=False, height=400)
                st.plotly_chart(fig_status, use_container_width=True)
            else:
                st.info("Status information not available")
        
        with col2:
            # Founder type distribution bar chart
            st.subheader("Founder Type Distribution")
            if 'founder_type' in df.columns:
                founder_type_counts = filtered_df['founder_type'].value_counts()
                fig_founder_type = px.bar(
                    x=founder_type_counts.index,
                    y=founder_type_counts.values,
                    labels={'x': 'Founder Type', 'y': 'Count'},
                    color=founder_type_counts.index,
                    color_discrete_map={
                        'technical': '#8B5CF6',  # Purple for technical
                        'business': '#F59E0B'    # Orange for business
                    },
                    text=founder_type_counts.values
                )
                fig_founder_type.update_traces(texttemplate='%{text}', textposition='outside')
                fig_founder_type.update_layout(showlegend=False, height=400)
                st.plotly_chart(fig_founder_type, use_container_width=True)
            else:
                st.info("Founder type information not available")
        
        with col3:
            # Location distribution
            st.subheader("Top Locations")
            if 'location' in df.columns:
                location_counts = filtered_df['location'].value_counts().head(8)  # Show fewer to fit in smaller column
                fig_location = px.bar(
                    y=location_counts.index,
                    x=location_counts.values,
                    orientation='h',
                    labels={'x': 'Count', 'y': 'Location'},
                    color=location_counts.values,
                    color_continuous_scale='Viridis',
                    text=location_counts.values
                )
                fig_location.update_traces(texttemplate='%{text}', textposition='outside')
                fig_location.update_layout(showlegend=False, height=400)
                st.plotly_chart(fig_location, use_container_width=True)
            else:
                st.info("Location information not available")
        
        # Second row - Cofounder matching insights
        st.markdown("---")
        st.subheader("🤝 Available for Cofounder Matching")
        
        # Center the chart in a single column
        if 'status' in df.columns and 'founder_type' in df.columns:
            # Filter for those looking for cofounders
            looking_df = filtered_df[filtered_df['status'] == 'Looking for co-founder']
            
            if len(looking_df) > 0:
                looking_founder_types = looking_df['founder_type'].value_counts()
                
                fig_looking = px.bar(
                    x=looking_founder_types.index,
                    y=looking_founder_types.values,
                    labels={'x': 'Founder Type', 'y': 'Count'},
                    title="Technical vs Business Founders Looking for Cofounders",
                    color=looking_founder_types.index,
                    color_discrete_map={
                        'technical': '#8B5CF6',  # Purple for technical
                        'business': '#F59E0B'    # Orange for business
                    },
                    text=looking_founder_types.values
                )
                fig_looking.update_traces(texttemplate='%{text}', textposition='outside')
                fig_looking.update_layout(showlegend=False, height=400)
                st.plotly_chart(fig_looking, use_container_width=True)
                
                # Show percentages and matching insights in columns
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown("**📊 Breakdown:**")
                    total_looking = len(looking_df)
                    for founder_type, count in looking_founder_types.items():
                        percentage = (count / total_looking * 100) if total_looking > 0 else 0
                        st.write(f"• **{founder_type.title()}**: {count} founders ({percentage:.1f}%)")
                
                with col2:
                    st.markdown("**🎯 Matching Opportunities:**")
                    if len(looking_founder_types) >= 2:
                        tech_count = looking_founder_types.get('technical', 0)
                        biz_count = looking_founder_types.get('business', 0)
                        
                        if abs(tech_count - biz_count) > 2:  # If difference is more than 2
                            if tech_count > biz_count:
                                st.write("⚠️ More technical founders looking")
                                st.write("💡 Great opportunity for business founders!")
                            else:
                                st.write("⚠️ More business founders looking") 
                                st.write("💡 Great opportunity for technical founders!")
                        else:
                            st.write("✅ Balanced availability!")
                            st.write("🤝 Good matching potential")
                
                with col3:
                    st.markdown("**💼 Total Available:**")
                    st.metric("Total Available", f"{total_looking} founders", help="Total founders looking for cofounders")
                    if total_looking > 0:
                        cohort_percentage = (total_looking / len(filtered_df) * 100) if len(filtered_df) > 0 else 0
                        st.write(f"({cohort_percentage:.1f}% of cohort)")
            else:
                st.info("No founders currently looking for cofounders with the applied filters")
        else:
            st.info("Status or founder type information not available")
        
    
    with tab2:
        st.subheader("👥 Candidate Profiles")
        
        # Search box
        search_term = st.text_input("🔍 Search by name or skills", "")
        
        # Filter candidates based on search
        display_df = filtered_df.copy()
        if search_term:
            mask = display_df['name'].str.contains(search_term, case=False, na=False)
            if 'skills' in display_df.columns:
                skills_mask = display_df['skills'].apply(
                    lambda x: any(search_term.lower() in str(skill).lower() for skill in x) if isinstance(x, list) else False
                )
                mask = mask | skills_mask
            display_df = display_df[mask]
        
        # Display candidates in a grid
        st.write(f"Showing {len(display_df)} candidates")
        
        # Create columns for candidate cards
        num_cols = 3
        for i in range(0, len(display_df), num_cols):
            cols = st.columns(num_cols)
            for j, col in enumerate(cols):
                if i + j < len(display_df):
                    candidate = display_df.iloc[i + j]
                    with col:
                        # Enhanced card styling with circular profile picture
                        st.markdown(
                            """
                            <style>
                            .candidate-card {
                                background: white;
                                padding: 1rem;
                                border-radius: 10px;
                                border: 1px solid #e0e0e0;
                                margin-bottom: 1rem;
                            }
                            .profile-pic {
                                border-radius: 50%;
                                width: 60px;
                                height: 60px;
                                object-fit: cover;
                            }
                            </style>
                            """,
                            unsafe_allow_html=True
                        )
                        
                        with st.container():
                            # Profile picture and name in horizontal layout
                            col_avatar, col_info = st.columns([1, 4])
                            
                            with col_avatar:
                                if 'avatar_url' in candidate and pd.notna(candidate['avatar_url']) and candidate['avatar_url']:
                                    st.markdown(
                                        f'<img src="{candidate["avatar_url"]}" class="profile-pic">',
                                        unsafe_allow_html=True
                                    )
                                else:
                                    st.markdown(
                                        '<div style="width: 60px; height: 60px; border-radius: 50%; background-color: #f0f0f0; display: flex; align-items: center; justify-content: center; font-size: 24px;">👤</div>',
                                        unsafe_allow_html=True
                                    )
                            
                            with col_info:
                                st.markdown(f"**{candidate.get('name', 'Unknown')}**")
                            
                            # Status and founder type on the same line
                            status_founder_line = ""
                            if 'status' in candidate:
                                status_color = "🟢" if candidate['status'] == 'Looking for co-founder' else "🔵"
                                status_founder_line = f"{status_color} {candidate['status']}"
                            
                            if 'founder_type' in candidate and pd.notna(candidate['founder_type']):
                                founder_type_emoji = "💻" if candidate['founder_type'] == 'technical' else "💼"
                                founder_type_text = f"{founder_type_emoji} {candidate['founder_type'].title()}"
                                if status_founder_line:
                                    status_founder_line += f" | {founder_type_text}"
                                else:
                                    status_founder_line = founder_type_text
                            
                            if status_founder_line:
                                st.markdown(status_founder_line)
                            
                            if 'location' in candidate:
                                st.markdown(f"📍 {candidate.get('location', 'N/A')}")
                            
                            if 'tagline' in candidate and pd.notna(candidate['tagline']):
                                st.markdown(f"*{candidate['tagline']}*")
                            
                            if 'skills' in candidate and isinstance(candidate['skills'], list):
                                # Create skills badges
                                skills_html = ""
                                for skill in candidate['skills']:
                                    skills_html += f'<span style="display: inline-block; background-color: #e8f4f8; color: #1f77b4; padding: 2px 8px; margin: 2px; border-radius: 12px; font-size: 12px; border: 1px solid #d0e8f2;">{skill}</span>'
                                st.markdown(skills_html, unsafe_allow_html=True)
                            
                            st.markdown("---")
    
    with tab3:
        st.subheader("🎯 Skills Analysis")
        
        if 'skills' in df.columns:
            # Extract all skills
            all_skills = []
            for skills in filtered_df['skills'].dropna():
                if isinstance(skills, list):
                    all_skills.extend(skills)
            
            if all_skills:
                # Count skills
                skill_counts = Counter(all_skills)
                top_skills = dict(skill_counts.most_common(15))
                
                # Create bar chart for top skills
                fig_skills = px.bar(
                    x=list(top_skills.values()),
                    y=list(top_skills.keys()),
                    orientation='h',
                    labels={'x': 'Number of Candidates', 'y': 'Skill'},
                    title="Top 15 Skills in the Cohort",
                    color=list(top_skills.values()),
                    color_continuous_scale='Teal',
                    text=list(top_skills.values())
                )
                fig_skills.update_traces(texttemplate='%{text}', textposition='outside')
                fig_skills.update_layout(showlegend=False, height=500)
                st.plotly_chart(fig_skills, use_container_width=True)
                
                # Skills by status
                col1, col2 = st.columns(2)
                
                with col1:
                    if 'status' in df.columns:
                        st.markdown("#### Skills Distribution by Status")
                        looking_df = filtered_df[filtered_df['status'] == 'Looking for co-founder']
                        team_df = filtered_df[filtered_df['status'] == 'In a team']
                        
                        looking_skills = []
                        for skills in looking_df['skills'].dropna():
                            if isinstance(skills, list):
                                looking_skills.extend(skills)
                        
                        team_skills = []
                        for skills in team_df['skills'].dropna():
                            if isinstance(skills, list):
                                team_skills.extend(skills)
                        
                        if looking_skills:
                            st.markdown("**Top skills among those looking:**")
                            looking_top = Counter(looking_skills).most_common(5)
                            for skill, count in looking_top:
                                st.write(f"- {skill}: {count}")
                        
                        if team_skills:
                            st.markdown("**Top skills among those in teams:**")
                            team_top = Counter(team_skills).most_common(5)
                            for skill, count in team_top:
                                st.write(f"- {skill}: {count}")
                
                with col2:
                    # Skill categories distribution
                    if 'categories' in df.columns:
                        st.markdown("#### Category Distribution")
                        all_categories = []
                        for cats in filtered_df['categories'].dropna():
                            if isinstance(cats, list):
                                all_categories.extend(cats)
                        
                        if all_categories:
                            cat_counts = Counter(all_categories)
                            fig_cats = px.pie(
                                values=list(cat_counts.values()),
                                names=list(cat_counts.keys()),
                                title="Domain Categories"
                            )
                            st.plotly_chart(fig_cats, use_container_width=True)
        else:
            st.info("Skills information not available")
    
    with tab4:
        st.subheader("📍 Location Insights")
        
        if 'location' in df.columns:
            col1, col2 = st.columns(2)
            
            with col1:
                # Location by status
                if 'status' in df.columns:
                    st.markdown("#### Team Formation by Location")
                    location_status = filtered_df.groupby(['location', 'status']).size().reset_index(name='count')
                    
                    # Get top 10 locations
                    top_locations = filtered_df['location'].value_counts().head(10).index
                    location_status_filtered = location_status[location_status['location'].isin(top_locations)]
                    
                    fig_location_status = px.bar(
                        location_status_filtered,
                        x='location',
                        y='count',
                        color='status',
                        title="Status Distribution by Location",
                        color_discrete_map={
                            'Looking for co-founder': '#10B981',
                            'In a team': '#3B82F6'
                        }
                    )
                    fig_location_status.update_layout(height=400)
                    st.plotly_chart(fig_location_status, use_container_width=True)
            
            with col2:
                # Location concentration
                st.markdown("#### Geographic Concentration")
                location_counts = filtered_df['location'].value_counts()
                
                # Calculate concentration metrics
                top_3_concentration = (location_counts.head(3).sum() / location_counts.sum() * 100) if len(location_counts) > 0 else 0
                st.metric("Top 3 Cities Concentration", f"{top_3_concentration:.1f}%")
                
                # Show location distribution table
                st.markdown("**Candidate Distribution:**")
                location_table = pd.DataFrame({
                    'Location': location_counts.index[:10],
                    'Count': location_counts.values[:10],
                    'Percentage': (location_counts.values[:10] / location_counts.sum() * 100).round(1)
                })
                st.dataframe(location_table, hide_index=True, use_container_width=True)
        else:
            st.info("Location information not available")
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: gray;'>
            Antler Cofounder Dashboard | V1.0.0 | By <a href="https://www.linkedin.com/in/hidde-kehrer/" target="_blank" style="color: #0077B5; text-decoration: none;">Hidde Kehrer</a> & <a href="https://www.linkedin.com/in/michiel-voortman/" target="_blank" style="color: #0077B5; text-decoration: none;">Michiel Voortman</a> ❤️
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()