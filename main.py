import os
import logging
from src.curator import EnhancedArticleCurator
from src.email_digest import EmailDigest
from src.utils import setup_logging
from dotenv import load_dotenv
load_dotenv()  # This loads the .env file

def main():
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Initialize curator
        curator = EnhancedArticleCurator(
            gemini_api_key=os.environ['GEMINI_API_KEY'],
            reddit_client_id=os.environ['REDDIT_CLIENT_ID'],
            reddit_client_secret=os.environ['REDDIT_CLIENT_SECRET']
        )
        
        # Get curated articles
        logger.info("Starting article curation...")
        articles = curator.curate_articles()
        logger.info(f"Found {len(articles)} articles")
        
        # Initialize email digest
        email_config = {
            'server': 'smtp.gmail.com',
            'port': 465,
            'username': os.environ['SMTP_USERNAME'],
            'password': os.environ['SMTP_PASSWORD']
        }
        
        emailer = EmailDigest(email_config)
        
        # Send digest
        logger.info("Sending email digest...")
        success = emailer.send_digest(
            articles,
            to_email=os.environ['RECIPIENT_EMAIL']
        )
        
        if success:
            logger.info("Email digest sent successfully")
        else:
            logger.error("Failed to send email digest")
            
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main()