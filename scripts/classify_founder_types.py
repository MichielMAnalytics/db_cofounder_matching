#!/usr/bin/env python3
"""
Script to classify founders as 'technical' or 'business' using OpenAI API
Analyzes tagline, about_me, skills, and categories fields to determine founder type
"""

import os
import json
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime, timezone
from typing import Dict, List, Optional
import time

# Load environment variables
load_dotenv()

def setup_openai():
    """Initialize OpenAI client"""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in .env file")
    
    from openai import OpenAI
    return OpenAI(api_key=api_key)

def classify_founder(founder_data: Dict, client) -> str:
    """
    Classify a founder as 'technical' or 'business' using OpenAI
    
    Args:
        founder_data: Dictionary containing founder information
        client: OpenAI client
        
    Returns:
        'technical' or 'business'
    """
    # Extract relevant fields
    name = founder_data.get('name', 'Unknown')
    tagline = founder_data.get('tagline', '')
    about_me = founder_data.get('about_me', '')
    skills = founder_data.get('skills', [])
    categories = founder_data.get('categories', [])
    
    # Create a profile summary for the LLM
    profile_text = f"""
    Name: {name}
    Tagline: {tagline}
    About: {about_me}
    Skills: {', '.join(skills) if skills else 'None listed'}
    Categories: {', '.join(categories) if categories else 'None listed'}
    """
    
    # Create the prompt for classification
    prompt = f"""You are an expert at analyzing founder profiles to determine if they are primarily technical or business-oriented founders.

Analyze the following founder profile and classify them as either 'technical' or 'business'.

Technical founders typically have:
- Software development, engineering, or data science skills
- Experience building products, coding, or system architecture
- Technical degrees or certifications
- Focus on product development, algorithms, or technical solutions

Business founders typically have:
- Marketing, sales, strategy, or finance skills
- Experience in business development, operations, or management
- Business degrees (MBA, etc.) or business-focused backgrounds
- Focus on growth, partnerships, revenue, or business model

Profile to analyze:
{profile_text}

Based on this profile, classify this founder as either 'technical' or 'business'.
Consider their skills, background, and focus areas.

Return ONLY one word: either 'technical' or 'business'.
"""

    try:
        # Use OpenAI Chat Completion
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using GPT-4o-mini for better accuracy
            messages=[
                {"role": "system", "content": "You are an expert at classifying founder types based on their profiles."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # Low temperature for consistent classification
            max_tokens=10,  # We only need one word
        )
        
        # Extract and clean the response
        classification = response.choices[0].message.content.strip().lower()
        
        # Validate the response
        if classification not in ['technical', 'business']:
            print(f"Warning: Unexpected classification '{classification}' for {name}, defaulting to 'business'")
            classification = 'business'
        
        return classification
        
    except Exception as e:
        print(f"Error classifying {name}: {e}")
        # Default to business if there's an error
        return 'business'

def main():
    """Main function to classify all founders in the database"""
    
    # Setup MongoDB connection
    mongo_uri = os.getenv('MONGO_URI')
    if not mongo_uri:
        print("Error: MONGO_URI not found in environment variables")
        return
    
    # Setup OpenAI
    try:
        client = setup_openai()
    except Exception as e:
        print(f"Error setting up OpenAI client: {e}")
        print("Make sure you have 'openai' package installed: pip install openai")
        return
    
    try:
        # Connect to MongoDB
        print("Connecting to MongoDB...")
        mongo_client = MongoClient(mongo_uri)
        db = mongo_client['last-recruiter-mvp']
        collection = db['users']
        
        print(f"Connected to database: {db.name}")
        print(f"Working with collection: {collection.name}")
        
        # Get all documents that don't have founder_type yet or have null/empty values
        query = {
            "$or": [
                {"founder_type": {"$exists": False}},
                {"founder_type": None},
                {"founder_type": ""}
            ]
        }
        unclassified_count = collection.count_documents(query)
        
        if unclassified_count == 0:
            print("All founders are already classified!")
            
            # Show statistics of existing classifications
            technical_count = collection.count_documents({"founder_type": "technical"})
            business_count = collection.count_documents({"founder_type": "business"})
            print(f"\nCurrent distribution:")
            print(f"  Technical founders: {technical_count}")
            print(f"  Business founders: {business_count}")
            return
        
        print(f"Found {unclassified_count} unclassified founders")
        
        # Ask for confirmation
        confirm = input(f"\nProceed with classifying {unclassified_count} founders? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Classification cancelled.")
            return
        
        print("\nStarting classification...")
        
        # Process each unclassified founder
        founders = list(collection.find(query))
        
        technical_count = 0
        business_count = 0
        errors = 0
        
        for i, founder in enumerate(founders, 1):
            try:
                name = founder.get('name', 'Unknown')
                print(f"\n[{i}/{unclassified_count}] Classifying: {name}")
                
                # Classify the founder
                founder_type = classify_founder(founder, client)
                
                # Update the database
                result = collection.update_one(
                    {"_id": founder["_id"]},
                    {
                        "$set": {
                            "founder_type": founder_type,
                            "founder_type_classified_at": datetime.now(timezone.utc)
                        }
                    }
                )
                
                if result.modified_count > 0:
                    print(f"  → Classified as: {founder_type}")
                    if founder_type == 'technical':
                        technical_count += 1
                    else:
                        business_count += 1
                else:
                    print(f"  ✗ Failed to update database")
                    errors += 1
                
                # Rate limiting to avoid hitting API limits
                # OpenAI has rate limits, so we add a small delay
                if i < unclassified_count:
                    time.sleep(0.5)  # 500ms delay between requests
                    
            except Exception as e:
                print(f"  ✗ Error processing {founder.get('name', 'Unknown')}: {e}")
                errors += 1
                continue
        
        # Print summary
        print("\n" + "="*50)
        print("Classification Complete!")
        print("="*50)
        print(f"Total processed: {unclassified_count}")
        print(f"Technical founders: {technical_count}")
        print(f"Business founders: {business_count}")
        if errors > 0:
            print(f"Errors: {errors}")
        
        # Show overall distribution
        total_technical = collection.count_documents({"founder_type": "technical"})
        total_business = collection.count_documents({"founder_type": "business"})
        total_classified = total_technical + total_business
        
        print(f"\nOverall distribution in database:")
        print(f"  Technical: {total_technical} ({total_technical/total_classified*100:.1f}%)")
        print(f"  Business: {total_business} ({total_business/total_classified*100:.1f}%)")
        
        # Show some examples
        print("\nSample classifications:")
        samples = list(collection.find({"founder_type": {"$exists": True}}).limit(5))
        for sample in samples:
            print(f"  - {sample.get('name', 'Unknown')}: {sample.get('founder_type', 'N/A')}")
            if sample.get('tagline'):
                print(f"    Tagline: {sample['tagline'][:60]}...")
        
    except Exception as e:
        print(f"Error during classification: {e}")
    finally:
        try:
            mongo_client.close()
            print("\nDatabase connection closed.")
        except:
            pass

if __name__ == "__main__":
    print("="*50)
    print("Founder Type Classification Script")
    print("="*50)
    print("\nThis script will classify founders as 'technical' or 'business'")
    print("based on their profile information using OpenAI GPT-4o-mini.\n")
    
    # Check for OpenAI API key
    if not os.getenv('OPENAI_API_KEY'):
        print("ERROR: OPENAI_API_KEY not found in .env file")
        print("\nPlease add your OpenAI API key to the .env file:")
        print("OPENAI_API_KEY=your-api-key-here")
        print("\nYou can get an API key from: https://platform.openai.com/api-keys")
    else:
        main()