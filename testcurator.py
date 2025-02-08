# test_curator.py
import os
from dotenv import load_dotenv
from src.curator import EnhancedArticleCurator
from src.email_digest import EmailDigest
import time

def test_single_source():
    """Test with just one source to verify the pipeline."""
    load_dotenv()  # Load environment variables
    
    # Initialize curator with just Reddit for testing
    curator = EnhancedArticleCurator(
        gemini_api_key=os.getenv('GEMINI_API_KEY'),
        reddit_client_id=os.getenv('REDDIT_CLIENT_ID'),
        reddit_client_secret=os.getenv('REDDIT_CLIENT_SECRET')
    )
    
    # Test Reddit extraction
    print("\nTesting Reddit extraction...")
    reddit_articles = curator.reddit_extractor.get_articles(days_ago=1)
    print(f"Found {len(reddit_articles)} Reddit articles")
    if reddit_articles:
        print("Sample article:", reddit_articles[0]['title'])
    
    # Test content extraction for one article
    if reddit_articles:
        print("\nTesting content extraction...")
        content = curator.extract_article_content(reddit_articles[0]['url'])
        print(f"Content length: {len(content) if content else 0} characters")
    
    # Test Gemini evaluation for one article
    if reddit_articles and content:
        print("\nTesting Gemini evaluation...")
        
        # Prepare article data for batch evaluation
        articles_data = [{
            "title": reddit_articles[0]['title'],
            "content": content[:3000],
            "source": "Reddit",
            "is_paywalled": False
        }]
        
        # Get evaluations
        evaluations = curator.batch_evaluate_articles(articles_data, batch_size=1)
        print("Evaluation result:", evaluations[0] if evaluations else "No evaluation")
        
        time.sleep(2)  # Add delay before email
    
        # Test email sending with a single article
        if evaluations:
            print("\nTesting email sending...")
            email_config = {
                'server': 'smtp.gmail.com',
                'port': 465,
                'username': os.getenv('SMTP_USERNAME'),
                'password': os.getenv('SMTP_PASSWORD')
            }
            
            emailer = EmailDigest(email_config)
            test_article = {
                'title': reddit_articles[0]['title'],
                'url': reddit_articles[0]['url'],
                'source': 'Reddit',
                'evaluation': evaluations[0]
            }
            
            success = emailer.send_digest(
                [test_article],
                to_email=os.getenv('RECIPIENT_EMAIL')
            )
            print(f"Email sent: {success}")

if __name__ == "__main__":
    test_single_source()