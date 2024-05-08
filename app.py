import os
import praw
import pandas as pd
from datetime import datetime, timezone
import re
from watchBrands import watch_brands
import psycopg2

def run_scrapper():
    reddit = praw.Reddit(
        client_id=os.getenv('reddit_client_id'),
        client_secret=os.getenv('reddit_client_secret'),
        user_agent=os.getenv('reddit_user_agent'),
        username=os.getenv('reddit_username'),
        password=os.getenv('reddit_password'),
    )

    subreddit = reddit.subreddit("watchexchange")
    posts_data = []
    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    for submission in subreddit.new(limit=100):
        submission_time = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
        if submission_time >= start_of_day:
            post_details = {
                "id": submission.id,
                "created_utc": submission_time.strftime('%Y-%m-%d %H:%M:%S'),
                "username": submission.author.name if submission.author else "N/A",
                "num_comments": submission.num_comments,
                "upvotes": submission.score,
                "title": submission.title,
            }
            posts_data.append(post_details)

    posts_df = pd.DataFrame(posts_data)
    posts_df[['brand', 'price']] = posts_df['title'].apply(lambda title: pd.Series(find_brand_and_price(title)))

    # Insert data into PostgreSQL database
    insert_posts(posts_df)

def find_brand_and_price(title):
    brand = None
    for brand_name in watch_brands:
        if brand_name.lower() in title.lower():
            brand = brand_name
            break
    price_pattern = r'\$(\d+)|USD\s(\d+)'
    price_matches = re.findall(price_pattern, title)
    if price_matches:
        price = [int(num) for tup in price_matches for num in tup if num][0]
    else:
        price = None
    return brand, price

def insert_posts(df):
    conn = psycopg2.connect(
        host=os.getenv('pg_host'),
        database=os.getenv('pg_database'),
        user=os.getenv('pg_user'),
        password=os.getenv('pg_password')
    )
    cur = conn.cursor()
    for _, row in df.iterrows():
        cur.execute("""
            INSERT INTO watchexchange_posts (id, created_utc, username, num_comments, upvotes, title, brand, price)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING;
        """, (row['id'], row['created_utc'], row['username'], row['num_comments'], row['upvotes'], row['title'], row['brand'], row['price']))
    conn.commit()
    cur.close()
    conn.close()

import time 
if __name__ == "__main__":
    run_scrapper()
    time.sleep(300)
