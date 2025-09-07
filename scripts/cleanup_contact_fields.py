#!/usr/bin/env python3
"""
Script to clean up contact information fields in the MongoDB users collection.
This script will:
1. Remove 'email' and 'linkedin' fields completely from all user documents
2. Set the 'phone' field to empty string for all user documents
3. Remove any existing 'contact_fields_cleaned_at' fields
"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv

def main():
    """Clean up contact fields in the users collection"""
    
    # Load environment variables
    load_dotenv()
    
    # MongoDB connection
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
        
        # Get initial count of documents
        total_docs = collection.count_documents({})
        print(f"Total documents in collection: {total_docs}")
        
        if total_docs == 0:
            print("No documents found in the collection.")
            return
        
        # Check current state - count documents with email, linkedin, phone, or cleanup timestamp
        docs_with_email = collection.count_documents({"email": {"$exists": True}})
        docs_with_linkedin = collection.count_documents({"linkedin": {"$exists": True}}) 
        docs_with_phone = collection.count_documents({"phone": {"$exists": True, "$ne": ""}})
        docs_with_cleanup_timestamp = collection.count_documents({"contact_fields_cleaned_at": {"$exists": True}})
        
        print(f"\\nCurrent state:")
        print(f"  Documents with 'email' field: {docs_with_email}")
        print(f"  Documents with 'linkedin' field: {docs_with_linkedin}")
        print(f"  Documents with non-empty 'phone' field: {docs_with_phone}")
        print(f"  Documents with 'contact_fields_cleaned_at' field: {docs_with_cleanup_timestamp}")
        
        # Ask for confirmation
        print(f"\\nThis will:")
        print(f"  - Remove 'email' field from {docs_with_email} documents")
        print(f"  - Remove 'linkedin' field from {docs_with_linkedin} documents") 
        print(f"  - Set 'phone' field to empty string in all {total_docs} documents")
        print(f"  - Remove 'contact_fields_cleaned_at' field from {docs_with_cleanup_timestamp} documents")
        
        confirm = input("\\nProceed with cleanup? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Cleanup cancelled.")
            return
        
        print("\\nStarting cleanup operations...")
        
        # Operation 1: Remove 'email' field from all documents
        if docs_with_email > 0:
            print(f"Removing 'email' field from {docs_with_email} documents...")
            result = collection.update_many(
                {"email": {"$exists": True}},
                {"$unset": {"email": ""}}
            )
            print(f"  ✓ Modified {result.modified_count} documents (removed email field)")
        else:
            print("  ✓ No 'email' fields to remove")
        
        # Operation 2: Remove 'linkedin' field from all documents  
        if docs_with_linkedin > 0:
            print(f"Removing 'linkedin' field from {docs_with_linkedin} documents...")
            result = collection.update_many(
                {"linkedin": {"$exists": True}},
                {"$unset": {"linkedin": ""}}
            )
            print(f"  ✓ Modified {result.modified_count} documents (removed linkedin field)")
        else:
            print("  ✓ No 'linkedin' fields to remove")
        
        # Operation 3: Set 'phone' field to empty string for all documents
        print(f"Setting 'phone' field to empty string for all documents...")
        result = collection.update_many(
            {},  # Match all documents
            {"$set": {"phone": ""}}
        )
        print(f"  ✓ Modified {result.modified_count} documents (cleared phone field)")
        
        # Operation 4: Remove 'contact_fields_cleaned_at' field from all documents
        if docs_with_cleanup_timestamp > 0:
            print(f"Removing 'contact_fields_cleaned_at' field from {docs_with_cleanup_timestamp} documents...")
            result = collection.update_many(
                {"contact_fields_cleaned_at": {"$exists": True}},
                {"$unset": {"contact_fields_cleaned_at": ""}}
            )
            print(f"  ✓ Modified {result.modified_count} documents (removed cleanup timestamp field)")
        else:
            print("  ✓ No 'contact_fields_cleaned_at' fields to remove")
        
        # Verify final state
        print("\\nVerifying final state...")
        final_docs_with_email = collection.count_documents({"email": {"$exists": True}})
        final_docs_with_linkedin = collection.count_documents({"linkedin": {"$exists": True}})
        final_docs_with_phone = collection.count_documents({"phone": {"$exists": True, "$ne": ""}})
        final_docs_with_cleanup_timestamp = collection.count_documents({"contact_fields_cleaned_at": {"$exists": True}})
        
        print(f"Final state:")
        print(f"  Documents with 'email' field: {final_docs_with_email}")
        print(f"  Documents with 'linkedin' field: {final_docs_with_linkedin}")
        print(f"  Documents with non-empty 'phone' field: {final_docs_with_phone}")
        print(f"  Documents with 'contact_fields_cleaned_at' field: {final_docs_with_cleanup_timestamp}")
        
        if final_docs_with_email == 0 and final_docs_with_linkedin == 0 and final_docs_with_phone == 0 and final_docs_with_cleanup_timestamp == 0:
            print("\\n✅ Cleanup completed successfully!")
        else:
            print("\\n⚠️  Cleanup may not be complete - some fields still exist")
        
        # Sample a few documents to show the result
        print("\\nSample of cleaned documents:")
        sample_docs = list(collection.find({}).limit(3))
        for i, doc in enumerate(sample_docs, 1):
            print(f"  Sample {i}: name='{doc.get('name', 'N/A')}', phone='{doc.get('phone', 'N/A')}', email={doc.get('email', 'REMOVED')}, linkedin={doc.get('linkedin', 'REMOVED')}")
        
    except Exception as e:
        print(f"Error during cleanup: {e}")
    finally:
        try:
            client.close()
            print("\\nDatabase connection closed.")
        except:
            pass

if __name__ == "__main__":
    main()