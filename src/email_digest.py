from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from typing import List, Dict
import markdown
from datetime import datetime

class EmailDigest:
    def __init__(self, smtp_config: Dict):
        self.smtp_config = smtp_config

    def format_article_html(self, articles: List[Dict]) -> str:
        """Create a well-formatted HTML digest of articles."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Weekly Curated Articles</title>
        </head>
        <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
            <div style="margin-bottom: 30px;">
                <h1>Weekly Curated Articles</h1>
                <div style="color: #666; font-size: 16px;">{datetime.now().strftime("%B %d, %Y")}</div>
            </div>
        """

        # Add each article
        for idx, article in enumerate(articles, 1):
            eval_data = article['evaluation']
            html += f"""
            <div style="margin-bottom: 30px; padding: 20px; border: 1px solid #eee; border-radius: 5px;">
                <div style="color: #2c5282; font-size: 20px; margin-bottom: 10px;">
                    {idx}. <a href="{article['url']}">{article['title']}</a>
                </div>
                <div style="color: #666; font-size: 14px; margin-bottom: 10px;">
                    <span>Source: {article['source']}</span> | 
                    <span style="display: inline-block; padding: 3px 8px; border-radius: 3px; background: #ebf8ff;">
                        Impact: {eval_data['impact_score']}/10
                    </span> | 
                    <span style="display: inline-block; padding: 3px 8px; border-radius: 3px; background: #ebf8ff;">
                        Originality: {eval_data['originality_score']}/10
                    </span> |
                    <span style="color: #666; font-style: italic;">
                        Reading time: {eval_data['estimated_reading_time']} mins
                    </span>
                </div>
                <div style="margin-top: 15px;">
                    <strong>Key Insights:</strong>
                    <ul>
                        {"".join(f"<li>{insight}</li>" for insight in eval_data['key_insights'])}
                    </ul>
                </div>
                <div>
                    <strong>Time Value:</strong> {eval_data['time_value_assessment']}
                </div>
            </div>
            """

        # Close HTML
        html += """
        </body>
        </html>
        """

        return html

    def format_no_articles_html(self) -> str:
        """Create HTML for when no articles are found."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Weekly Curation Update</title>
        </head>
        <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
            <h1>Weekly Curation Update</h1>
            <p>No articles met our quality threshold this week. The curator will continue monitoring for high-quality content.</p>
            <p>Date: {datetime.now().strftime("%B %d, %Y")}</p>
        </body>
        </html>
        """

    def send_digest(self, articles: List[Dict], to_email: str) -> bool:
        """Send the article digest via email."""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'Weekly Curated Articles - {datetime.now().strftime("%B %d, %Y")}'
            msg['From'] = self.smtp_config['username']
            msg['To'] = to_email

            # Choose content based on whether articles were found
            html_content = self.format_article_html(articles) if articles else self.format_no_articles_html()
            msg.attach(MIMEText(html_content, 'html'))

            with smtplib.SMTP_SSL(self.smtp_config['server'], self.smtp_config['port']) as server:
                server.login(self.smtp_config['username'], self.smtp_config['password'])
                server.send_message(msg)
                print("Email sent successfully!")
            return True
        except Exception as e:
            print(f"Error sending email: {e}")
            return False