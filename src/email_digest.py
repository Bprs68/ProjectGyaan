import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List

TAG_COLORS = {
    "DEEP": "#f59e0b",
    "FEATURE": "#06b6d4",
    "ANALYSIS": "#3b82f6",
    "RESEARCH": "#a855f7",
    "BRIEF": "#22c55e",
}


class EmailDigest:
    def __init__(self, smtp_config: Dict):
        self.smtp_config = smtp_config

    def _tag_style(self, article_type: str) -> str:
        color = TAG_COLORS.get(article_type.upper(), "#888888")
        return (
            f"display:inline-block;padding:2px 8px;border:1px solid {color};"
            f"color:{color};font-size:11px;font-family:monospace;border-radius:3px;"
            f"text-transform:uppercase;letter-spacing:0.05em;"
        )

    def format_article_html(self, articles: List[Dict], week_summary: str = "") -> str:
        now = datetime.now()
        week_end = now.strftime("%b %d, %Y")

        articles_html = ""
        for idx, a in enumerate(articles, 1):
            article_type = a.get("article_type", "ANALYSIS").upper()
            insights = a.get("key_insights", [])
            insights_html = "".join(
                f"<li style='margin-bottom:6px;color:#ccc;'>{i}</li>"
                for i in insights[:3]
            )
            summary = a.get("summary", "")
            score_pct = a.get("score_pct", 0)
            reading_time = a.get("reading_time_mins", 0)

            articles_html += f"""
<div style="margin-bottom:32px;padding:24px;border:1px solid #2a2a2a;border-radius:6px;background:#1a1a1a;">
  <div style="margin-bottom:12px;">
    <span style="{self._tag_style(article_type)}">{article_type}</span>
    <span style="color:#888;font-size:13px;margin-left:10px;">{a.get('topic_name','')}</span>
    <span style="color:#555;font-size:13px;"> · {a.get('source','')}</span>
    <span style="float:right;color:#888;font-size:13px;">
      ⏱ {reading_time} min &nbsp;
      <span style="color:#f59e0b;font-weight:600;">{score_pct}%</span>
    </span>
  </div>
  <div style="font-size:11px;color:#666;margin-bottom:10px;">#{idx:02d}</div>
  <h3 style="margin:0 0 10px 0;font-size:18px;font-weight:600;line-height:1.4;">
    <a href="{a['url']}" style="color:#f0f0f0;text-decoration:none;">{a['title']}</a>
  </h3>
  {f'<p style="color:#aaa;font-size:14px;line-height:1.6;margin:0 0 12px 0;">{summary}</p>' if summary else ''}
  {f'<ul style="margin:0;padding-left:18px;">{insights_html}</ul>' if insights_html else ''}
</div>"""

        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Project Gyaan — Weekly Digest</title>
</head>
<body style="margin:0;padding:0;background:#0f0f0f;color:#f0f0f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <div style="max-width:680px;margin:0 auto;padding:40px 20px;">
    <div style="margin-bottom:40px;border-bottom:1px solid #2a2a2a;padding-bottom:24px;">
      <div style="font-size:13px;color:#f59e0b;font-family:monospace;letter-spacing:0.1em;margin-bottom:8px;">
        PROJECT GYAAN
      </div>
      <h1 style="margin:0 0 8px 0;font-size:32px;font-weight:700;">Weekly Intelligence Digest</h1>
      <p style="margin:0;color:#888;font-size:14px;">{week_end} &nbsp;·&nbsp; {len(articles)} curated from this week's collection</p>
    </div>
    {f'<div style="margin-bottom:40px;padding:24px;background:#161616;border-left:3px solid #f59e0b;border-radius:0 6px 6px 0;"><div style="font-size:11px;color:#f59e0b;font-family:monospace;letter-spacing:0.1em;margin-bottom:12px;">WEEK IN REVIEW</div><p style="margin:0;color:#ccc;font-size:15px;line-height:1.8;">{week_summary}</p></div>' if week_summary else ''}
    {articles_html}
    <div style="margin-top:40px;padding-top:24px;border-top:1px solid #2a2a2a;color:#555;font-size:12px;">
      Curated by Project Gyaan &nbsp;·&nbsp; Ranked by research depth, source credibility, and your preference signals.
    </div>
  </div>
</body>
</html>"""

    def format_no_articles_html(self) -> str:
        return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Project Gyaan</title></head>
<body style="background:#0f0f0f;color:#f0f0f0;font-family:sans-serif;padding:40px;max-width:680px;margin:0 auto;">
  <h1>Weekly Digest — {datetime.now().strftime('%b %d, %Y')}</h1>
  <p style="color:#888;">No articles met the quality threshold this week. The pipeline continues to monitor for high-depth content.</p>
</body>
</html>"""

    def send_digest(self, articles: List[Dict], to_email: str, week_summary: str = "") -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"Project Gyaan — Weekly Digest {datetime.now().strftime('%b %d, %Y')}"
            msg["From"] = self.smtp_config["username"]
            msg["To"] = to_email

            html = (
                self.format_article_html(articles, week_summary=week_summary)
                if articles
                else self.format_no_articles_html()
            )
            msg.attach(MIMEText(html, "html"))

            with smtplib.SMTP_SSL(
                self.smtp_config["server"], self.smtp_config["port"]
            ) as server:
                server.login(self.smtp_config["username"], self.smtp_config["password"])
                server.send_message(msg)

            return True
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Email send error: {e}")
            return False
