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
    
    # Create a helper function to get effective cofounder type
    def get_effective_type(row):
        """Get cofounder type with fallback logic"""
        types = []
        
        # First try antler_cofounder_type
        if 'antler_cofounder_type' in row and isinstance(row['antler_cofounder_type'], list) and len(row['antler_cofounder_type']) > 0:
            types = row['antler_cofounder_type']
        # Fallback to founder_type
        elif 'founder_type' in row and pd.notna(row['founder_type']):
            founder_type = row['founder_type']
            # Map founder_type to antler format
            if founder_type in ['technical', 'technology']:
                types = ['Technology']
            elif founder_type == 'business':
                types = ['Business']
        
        return types

    # Add effective type column for filtering
    if 'antler_cofounder_type' in df.columns or 'founder_type' in df.columns:
        df['effective_cofounder_type'] = df.apply(get_effective_type, axis=1)
        
        # Extract all unique types from effective types
        all_types = []
        for types in df['effective_cofounder_type']:
            if isinstance(types, list):
                all_types.extend(types)
        unique_types = sorted(list(set(all_types)))
        antler_type_options = ['All'] + unique_types
        selected_antler_type = st.sidebar.selectbox("Cofounder Type", antler_type_options)
    else:
        selected_antler_type = 'All'
    
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
    if selected_antler_type != 'All' and 'effective_cofounder_type' in filtered_df.columns:
        # Filter based on effective cofounder type containing the selected type
        mask = filtered_df['effective_cofounder_type'].apply(
            lambda x: selected_antler_type in x if isinstance(x, list) else False
        )
        filtered_df = filtered_df[mask]
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
        if 'effective_cofounder_type' in filtered_df.columns:
            tech_mask = filtered_df['effective_cofounder_type'].apply(
                lambda x: 'Technology' in x if isinstance(x, list) else False
            )
            technical_count = tech_mask.sum()
            st.metric("Technology Founders", technical_count)
    
    with col4:
        if 'effective_cofounder_type' in filtered_df.columns:
            biz_mask = filtered_df['effective_cofounder_type'].apply(
                lambda x: 'Business' in x if isinstance(x, list) else False
            )
            business_count = biz_mask.sum()
            st.metric("Business Founders", business_count)
    
    with col5:
        if 'location' in df.columns:
            unique_locations = filtered_df['location'].nunique()
            st.metric("Unique Locations", unique_locations)
    
    st.markdown("---")
    
    # Enhanced tab styling - more visible buttons
    st.markdown("""
        <style>
        .stTabs [data-baseweb="tab-list"] {
            gap: 12px;
            margin-bottom: 30px;
            border-bottom: 2px solid #2e3440;
            padding-bottom: 0;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 55px;
            padding-left: 28px;
            padding-right: 28px;
            background-color: #3b4252;
            color: #d8dee9;
            font-size: 20px;
            font-weight: 700;
            border: none;
            border-radius: 8px 8px 0 0;
            margin-bottom: -2px;
            transition: all 0.2s ease;
            cursor: pointer;
        }
        
        .stTabs [data-baseweb="tab"]:hover {
            background-color: #4c566a;
            color: #eceff4;
            transform: translateY(-2px);
        }
        
        .stTabs [aria-selected="true"] {
            background-color: #5e81ac !important;
            color: #ffffff !important;
            border-bottom: 2px solid #5e81ac !important;
            transform: translateY(-2px);
        }
        
        .stTabs [data-baseweb="tab-panel"] {
            padding-top: 30px;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Main content area with tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "👥 Candidates", "🎯 Skills Analysis", "📍 Location Insights"])
    
    with tab1:
        # First row - three main charts
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Status distribution bar chart
            st.subheader("Founder Status Distribution")
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
            # Cofounder type distribution bar chart
            st.subheader("Cofounder Type Distribution")
            if 'effective_cofounder_type' in filtered_df.columns:
                # Count occurrences of each type across all effective arrays
                type_counts = {}
                for types in filtered_df['effective_cofounder_type']:
                    if isinstance(types, list):
                        for t in types:
                            type_counts[t] = type_counts.get(t, 0) + 1
                
                if type_counts:
                    fig_founder_type = px.bar(
                        x=list(type_counts.keys()),
                        y=list(type_counts.values()),
                        labels={'x': 'Cofounder Type', 'y': 'Count'},
                        color=list(type_counts.keys()),
                        color_discrete_map={
                            'Technology': '#8B5CF6',  # Purple for Technology
                            'Business': '#F59E0B',    # Orange for Business
                            'Domain': '#10B981'       # Green for Domain
                        },
                        text=list(type_counts.values())
                    )
                    fig_founder_type.update_traces(texttemplate='%{text}', textposition='outside')
                    fig_founder_type.update_layout(showlegend=False, height=400)
                    st.plotly_chart(fig_founder_type, use_container_width=True)
                else:
                    st.info("No cofounder type data available")
            else:
                st.info("Cofounder type information not available")
        
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
        if 'status' in df.columns and 'effective_cofounder_type' in filtered_df.columns:
            # Filter for those looking for cofounders
            looking_df = filtered_df[filtered_df['status'] == 'Looking for co-founder']
            
            if len(looking_df) > 0:
                # Count effective cofounder types among those looking for cofounders
                type_counts = {}
                for types in looking_df['effective_cofounder_type']:
                    if isinstance(types, list):
                        for t in types:
                            type_counts[t] = type_counts.get(t, 0) + 1
                
                if type_counts:
                    fig_looking = px.bar(
                        x=list(type_counts.keys()),
                        y=list(type_counts.values()),
                        labels={'x': 'Antler Cofounder Type', 'y': 'Count'},
                        title="Antler Cofounder Types Looking for Partners",
                        color=list(type_counts.keys()),
                        color_discrete_map={
                            'Technology': '#8B5CF6',  # Purple for Technology
                            'Business': '#F59E0B',    # Orange for Business
                            'Domain': '#10B981'       # Green for Domain
                        },
                        text=list(type_counts.values())
                    )
                    fig_looking.update_traces(texttemplate='%{text}', textposition='outside')
                    fig_looking.update_layout(showlegend=False, height=400)
                    st.plotly_chart(fig_looking, use_container_width=True)
                    
                    # Show percentages and matching insights in columns
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.markdown("**📊 Breakdown:**")
                        total_looking = len(looking_df)
                        total_type_counts = sum(type_counts.values())
                        for antler_type, count in type_counts.items():
                            percentage = (count / total_type_counts * 100) if total_type_counts > 0 else 0
                            st.write(f"• **{antler_type}**: {count} founders ({percentage:.1f}%)")
                    
                    with col2:
                        st.markdown("**🎯 Matching Opportunities:**")
                        tech_count = type_counts.get('Technology', 0)
                        biz_count = type_counts.get('Business', 0)
                        domain_count = type_counts.get('Domain', 0)
                        
                        if tech_count > biz_count and tech_count > domain_count:
                            st.write("⚠️ More Technology founders looking")
                            st.write("💡 Great opportunity for Business/Domain founders!")
                        elif biz_count > tech_count and biz_count > domain_count:
                            st.write("⚠️ More Business founders looking") 
                            st.write("💡 Great opportunity for Technology/Domain founders!")
                        elif domain_count > tech_count and domain_count > biz_count:
                            st.write("⚠️ More Domain founders looking")
                            st.write("💡 Great opportunity for Technology/Business founders!")
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
                    st.info("No cofounder type data available for candidates looking for cofounders")
            else:
                st.info("No founders currently looking for cofounders with the applied filters")
        else:
            st.info("Status or cofounder type information not available")
        
    
    with tab2:
        st.subheader("👥 Candidate Profiles")
        
        # Add lunch mode checkbox and search in the same row
        col_search, col_checkbox = st.columns([3, 1])
        
        with col_search:
            # Search box with placeholder text that changes based on lunch mode
            search_placeholder = "🔍 Search by name or skills"
            search_term = st.text_input("Search", "", placeholder=search_placeholder, label_visibility="collapsed")
        
        with col_checkbox:
            lunch_mode = st.checkbox("🍽️ Lunch Mode", help="Enable to search for multiple people at once and see expanded profiles. Perfect for lunch meetings!")
        
        # Filter candidates based on search
        display_df = filtered_df.copy()
        
        if search_term:
            if lunch_mode:
                # In lunch mode, split the search term by spaces and search for each name
                # This allows pasting multiple names at once
                names = search_term.replace(',', ' ').split()
                
                # Create a mask for any name that matches
                mask = pd.Series([False] * len(display_df))
                for name in names:
                    if name.strip():  # Skip empty strings
                        name_mask = display_df['name'].str.contains(name.strip(), case=False, na=False)
                        mask = mask | name_mask
                
                display_df = display_df[mask]
            else:
                # Normal search mode - search in name and skills
                mask = display_df['name'].str.contains(search_term, case=False, na=False)
                if 'skills' in display_df.columns:
                    skills_mask = display_df['skills'].apply(
                        lambda x: any(search_term.lower() in str(skill).lower() for skill in x) if isinstance(x, list) else False
                    )
                    mask = mask | skills_mask
                display_df = display_df[mask]
        
        # Display candidates in a grid
        st.write(f"Showing {len(display_df)} candidates")
        
        # Different display modes for lunch mode vs normal mode
        if lunch_mode and len(display_df) > 0:
            # Lunch mode: Show expanded profiles in a vertical list
            st.markdown("### 🍽️ Lunch Group Profiles")
            
            for idx, candidate in display_df.iterrows():
                # Create an expander for each person with more information
                with st.container():
                    # Create a card-like container with more info
                    col_main, col_details = st.columns([1, 2])
                    
                    with col_main:
                        # Profile section
                        if 'avatar_url' in candidate and pd.notna(candidate['avatar_url']) and candidate['avatar_url']:
                            st.markdown(
                                f'<img src="{candidate["avatar_url"]}" style="border-radius: 50%; width: 100px; height: 100px; object-fit: cover;">',
                                unsafe_allow_html=True
                            )
                        else:
                            st.markdown(
                                '<div style="width: 100px; height: 100px; border-radius: 50%; background-color: #f0f0f0; display: flex; align-items: center; justify-content: center; font-size: 48px;">👤</div>',
                                unsafe_allow_html=True
                            )
                        
                        st.markdown(f"### {candidate.get('name', 'Unknown')}")
                        
                        # Status
                        if 'status' in candidate:
                            status_color = "🟢" if candidate['status'] == 'Looking for co-founder' else "🔵"
                            st.markdown(f"{status_color} **{candidate['status']}**")
                        
                        # Location
                        if 'location' in candidate:
                            st.markdown(f"📍 **Location:** {candidate.get('location', 'N/A')}")
                    
                    with col_details:
                        # Cofounder type
                        effective_types = get_effective_type(candidate)
                        if effective_types and len(effective_types) > 0:
                            type_emojis = {
                                'Technology': '💻',
                                'Business': '💼', 
                                'Domain': '🎯'
                            }
                            type_texts = []
                            for atype in effective_types:
                                emoji = type_emojis.get(atype, '🏷️')
                                type_texts.append(f"{emoji} {atype}")
                            st.markdown(f"**Type:** {' | '.join(type_texts)}")
                        
                        # Tagline
                        if 'tagline' in candidate and pd.notna(candidate['tagline']):
                            st.markdown(f"**Tagline:** *{candidate['tagline']}*")
                        
                        # Bio/Description if available
                        if 'bio' in candidate and pd.notna(candidate['bio']):
                            st.markdown(f"**About:** {candidate['bio']}")
                        elif 'description' in candidate and pd.notna(candidate['description']):
                            st.markdown(f"**About:** {candidate['description']}")
                        
                        # Skills
                        if 'skills' in candidate and isinstance(candidate['skills'], list) and len(candidate['skills']) > 0:
                            st.markdown("**Skills:**")
                            skills_html = ""
                            for skill in candidate['skills'][:10]:  # Limit to 10 skills for readability
                                skills_html += f'<span style="display: inline-block; background-color: #e8f4f8; color: #1f77b4; padding: 4px 10px; margin: 3px; border-radius: 15px; font-size: 14px; border: 1px solid #d0e8f2;">{skill}</span>'
                            st.markdown(skills_html, unsafe_allow_html=True)
                        
                        # LinkedIn if available
                        if 'linkedin' in candidate and pd.notna(candidate['linkedin']):
                            st.markdown(f"🔗 [LinkedIn Profile]({candidate['linkedin']})")
                        
                        # Email if available  
                        if 'email' in candidate and pd.notna(candidate['email']):
                            st.markdown(f"✉️ **Email:** {candidate['email']}")
                        
                        # Categories if available
                        if 'categories' in candidate and isinstance(candidate['categories'], list) and len(candidate['categories']) > 0:
                            st.markdown(f"**Industries:** {', '.join(candidate['categories'][:5])}")
                    
                    st.markdown("---")
        
        else:
            # Normal mode: Display in grid as before
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
                                
                                # Use effective cofounder type (with fallback logic)
                                effective_types = get_effective_type(candidate)
                                if effective_types and len(effective_types) > 0:
                                    # Handle array of cofounder types
                                    type_emojis = {
                                        'Technology': '💻',
                                        'Business': '💼', 
                                        'Domain': '🎯'
                                    }
                                    type_texts = []
                                    for atype in effective_types:
                                        emoji = type_emojis.get(atype, '🏷️')
                                        type_texts.append(f"{emoji} {atype}")
                                    
                                    type_text = " | ".join(type_texts)
                                    if status_founder_line:
                                        status_founder_line += f" | {type_text}"
                                    else:
                                        status_founder_line = type_text
                                
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