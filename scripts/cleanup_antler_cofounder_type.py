#!/usr/bin/env python3
"""
Script to clean up antler_cofounder_type field in the MongoDB users collection.
This script will:
1. Remove the 'antler_cofounder_type' field completely from all user documents
"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv

def main():
    """Main function to clean up antler_cofounder_type field"""
    
    # Load environment variables
    load_dotenv()
    
    mongo_uri = os.getenv('MONGO_URI')
    if not mongo_uri:
        print("Error: MONGO_URI not found in environment variables")
        return
    
    try:
        # Connect to MongoDB
        print("Connecting to MongoDB...")
        client = MongoClient(mongo_uri)
        db = client['last-recruiter-mvp']
        collection = db['users']
        
        print(f"Connected to database: {db.name}")
        print(f"Working with collection: {collection.name}")
        
        # Get total document count
        total_docs = collection.count_documents({})
        
        if total_docs == 0:
            print("No documents found in the collection.")
            return
        
        # Check current state - count documents with antler_cofounder_type
        docs_with_antler_type = collection.count_documents({"antler_cofounder_type": {"$exists": True}})
        
        print(f"\nCurrent state:")
        print(f"  Total documents: {total_docs}")
        print(f"  Documents with 'antler_cofounder_type' field: {docs_with_antler_type}")
        
        if docs_with_antler_type == 0:
            print("\nNo documents have 'antler_cofounder_type' field. Nothing to clean up!")
            return
        
        # Ask for confirmation
        print(f"\nThis will:")
        print(f"  - Remove 'antler_cofounder_type' field from {docs_with_antler_type} documents")
        
        confirm = input("\nProceed with cleanup? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Cleanup cancelled.")
            return
        
        print("\nStarting cleanup...")
        
        # Remove antler_cofounder_type field from all documents
        print(f"Removing 'antler_cofounder_type' field from {docs_with_antler_type} documents...")
        result = collection.update_many(
            {"antler_cofounder_type": {"$exists": True}},
            {"$unset": {"antler_cofounder_type": ""}}
        )
        print(f"  ✓ Modified {result.modified_count} documents (removed antler_cofounder_type field)")
        
        # Verify final state
        print("\nVerifying final state...")
        final_docs_with_antler_type = collection.count_documents({"antler_cofounder_type": {"$exists": True}})
        
        print(f"Final state:")
        print(f"  Documents with 'antler_cofounder_type' field: {final_docs_with_antler_type}")
        
        if final_docs_with_antler_type == 0:
            print("\n✅ Cleanup completed successfully!")
        else:
            print("\n⚠️  Cleanup may not be complete - some fields still exist")
        
        # Sample a few documents to show the result
        print("\nSample of cleaned documents:")
        sample_docs = list(collection.find({}).limit(3))
        for i, doc in enumerate(sample_docs, 1):
            antler_type_status = "REMOVED" if "antler_cofounder_type" not in doc else doc.get("antler_cofounder_type", "N/A")
            print(f"  Sample {i}: name='{doc.get('name', 'N/A')}', antler_cofounder_type={antler_type_status}")
        
    except Exception as e:
        print(f"Error during cleanup: {e}")
    finally:
        try:
            client.close()
            print("\nDatabase connection closed.")
        except:
            pass

if __name__ == "__main__":
    main()