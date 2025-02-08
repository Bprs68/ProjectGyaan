# Project Gyaan

Project Gyaan is an intelligent article curator that automatically discovers, evaluates, and delivers high-quality, thought-provoking content straight to your inbox. The name "Gyaan" comes from the Sanskrit word for "knowledge" or "wisdom", reflecting the project's goal of surfacing truly insightful content from across the internet.

## Features

- **Multi-source Monitoring**:
  - Academic papers from arXiv
  - Quality discussions from curated subreddits
  - Top articles from Hacker News
  - RSS feeds from major publications (Nature, Science, MIT Tech Review, etc.)

- **Intelligent Evaluation**:
  - Uses Google's Gemini AI to evaluate content
  - Scores articles on impact, originality, and depth
  - Estimates reading time and value proposition
  - Filters out low-quality or superficial content

- **Weekly Email Digest**:
  - Beautifully formatted summaries
  - Key insights extraction
  - Direct links to original content
  - Quality and time investment indicators

## Local Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/project-gyaan.git
cd project-gyaan
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with the following credentials:
```env
# Gemini API credentials
GEMINI_API_KEY=your_gemini_api_key

# Reddit API credentials
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret

# Gmail credentials (for sending digests)
SMTP_USERNAME=your_gmail_address
SMTP_PASSWORD=your_gmail_app_password
RECIPIENT_EMAIL=your_email_address
```

5. Run the curator:
```bash
python main.py
```

## Getting the Required API Keys

1. **Gemini API Key**:
   - Visit: https://makersuite.google.com/app/apikey
   - Create a new API key

2. **Reddit API Credentials**:
   - Go to: https://www.reddit.com/prefs/apps
   - Click "create another app..."
   - Select "script"
   - Fill in required details
   - Get client_id and client_secret

3. **Gmail App Password**:
   - Enable 2-factor authentication in your Google Account
   - Go to Security → App Passwords
   - Generate app password for "Mail"

## Testing

To test the setup, run:
```bash
python test_curator.py
```

This will:
- Test Reddit article extraction
- Test content processing
- Test Gemini evaluation
- Send a test email digest

## Configuration

Key parameters can be adjusted in the code:
- `batch_size`: Number of articles evaluated together (default: 3)
- `min_score`: Minimum quality scores (impact: 7, originality: 6)
- Sleep delays between API calls (adjustable for rate limiting)

## Current Limitations

- Runs locally only (no GitHub Actions deployment yet)
- Some paywalled content may be inaccessible
- Rate limits on various APIs may affect processing time

## Contributing

Feel free to:
- Open issues for bugs or suggestions
- Submit pull requests with improvements
- Add support for new content sources
- Improve evaluation criteria

## Future Plans

- Add GitHub Actions for automated weekly runs
- Implement content archiving
- Add more sophisticated filtering
- Create web interface for browsing articles
- Add support for more content sources

## License

MIT License