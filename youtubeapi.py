# -*- coding: utf-8 -*-
"""
Created on Thu Dec  5 10:15:13 2024

@author: tevsl
"""

from googleapiclient.discovery import build
from datetime import datetime, timezone
import pytz
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os

load_dotenv()
API_KEY=os.getenv("YOUTUBE_API_KEY")

def convert_time_string(utc_time_str,tz='America/New_York'):

    # Parse the input time string as UTC
    utc_time = datetime.strptime(utc_time_str, '%Y-%m-%dT%H:%M:%SZ')
    utc_time = pytz.utc.localize(utc_time)  # Localize as UTC
    # Convert to localtimezone
    local_tz = pytz.timezone(tz)
    local_time = utc_time.astimezone(local_tz)
    #print(local_time.strftime('%Y-%m-%d_%H-%M'))
    return local_time.strftime('%Y-%m-%d_%H-%M')

def get_youtube_video_duration(api_key=None,video_ids=[]):
    import isodate
    
    if not api_key:
        api_key=API_KEY
    youtube = build('youtube', 'v3', developerKey=api_key)
    stats = {}
    # Process the video IDs in batches of 50
    for i in range(0, len(video_ids), 50):
        # Get the current batch of up to 50 video IDs
        batch_ids = video_ids[i:i + 50]
        # Join the list of video IDs into a comma-separated string
        video_ids_str = ','.join(batch_ids)
        # Make the API request to retrieve video details
        response = youtube.videos().list(
            part='contentDetails',
            id=video_ids_str
        ).execute()
        # Process and store the view counts for each video
        for item in response.get('items', []):
            video_id = item['id']
            duration_iso = item['contentDetails']['duration']
            duration = isodate.parse_duration(duration_iso).total_seconds()
            stats[video_id] = duration
    return stats

def resolve_channel_id(api_key=None, channel_handle=None):
    if not api_key:
        api_key=API_KEY
    youtube = build('youtube', 'v3', developerKey=api_key)
    request = youtube.channels().list(
        forHandle=channel_handle,
        part="id"
    )
    response = request.execute()

    if response["items"]:
        #return response["items"][0]["snippet"]["channelId"]
        return response["items"][0]["id"]
    else:
        return None

def get_youtube_id(video):
    "extracts the id from all 3 forms of the youtube url. returns none if not youtube"
    from urllib.parse import urlparse, parse_qs
    video_id=None   
    if 'youtube.com' in video or 'youtu.be' in video:
        parsed_url=urlparse(video)
        
        if parsed_url.netloc == 'youtu.be':
            video_id=parsed_url.path.lstrip('/')
        elif parsed_url.path=='/watch':
            query_params=parse_qs(parsed_url.query)
            video_id=query_params.get('v', [None])[0]
        else:
            video_id=parsed_url.path.split('/')[-1]
    return video_id

def get_all_video_ids(api_key=None, channel_id="", published_after=None,pages=False,maximum=10):
    if not published_after:
        published_after=datetime(2024, 5, 1, tzinfo=ZoneInfo('America/New_York'))
    if not api_key:
        api_key=API_KEY
    youtube = build('youtube', 'v3', developerKey=api_key)
    video_ids = []
    next_page_token = None

    # Retrieve the uploads playlist ID
    channel_response = youtube.channels().list(
        part='contentDetails',
        id=channel_id
    ).execute()
    uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

    while True:
        playlist_response = youtube.playlistItems().list(
            part='contentDetails',
            playlistId=uploads_playlist_id,
            maxResults=maximum,
            pageToken=next_page_token
        ).execute()

        for item in playlist_response['items']:
            video_id = item['contentDetails']['videoId']
            video_published_at = datetime.strptime(
                item["contentDetails"]["videoPublishedAt"],
                '%Y-%m-%dT%H:%M:%SZ'
            ).replace(tzinfo=timezone.utc)
            eastern_time = video_published_at.astimezone(ZoneInfo('America/New_York'))
            #print(eastern_time,item["contentDetails"]["videoPublishedAt"]) ###debug
            #print(published_after)
            if eastern_time >= published_after:
                video_ids.append(video_id)
                #print (eastern_time)

        next_page_token = playlist_response.get('nextPageToken')
        if not next_page_token or not pages or len(video_ids)>=maximum:
            break
    video_ids=video_ids[:maximum]
    return video_ids


def get_video_titles(api_key=None, video_ids=[]):
    """Gets titles and durations in seconds, excluding live sessions."""
    import isodate
    if not api_key:
        api_key = API_KEY
    youtube = build('youtube', 'v3', developerKey=api_key)
    request = youtube.videos().list(
        part='snippet,contentDetails',
        id=','.join(video_ids)
    )
    response = request.execute()
    videos = []
    for item in response['items']:
        if item['snippet'].get('liveBroadcastContent', 'none') != 'live':
            video_id = item['id']
            title = item['snippet']['title']
            published_at = convert_time_string(item['snippet']['publishedAt'])
            duration_iso = item['contentDetails']['duration']
            duration_td = isodate.parse_duration(duration_iso)
            duration_seconds = duration_td.total_seconds()
            videos.append((video_id, title, published_at, duration_seconds))
    return videos


def get_video_statistics(api_key=None, video_ids=[]):
    "get mumber of views for video ids in list"
    if not api_key:
        api_key=API_KEY
    youtube = build('youtube', 'v3', developerKey=api_key)
    stats = {}
    # Process the video IDs in batches of 50
    for i in range(0, len(video_ids), 50):
        # Get the current batch of up to 50 video IDs
        batch_ids = video_ids[i:i + 50]
        # Join the list of video IDs into a comma-separated string
        video_ids_str = ','.join(batch_ids)
        # Make the API request to retrieve video details
        response = youtube.videos().list(
            part='statistics',
            id=video_ids_str
        ).execute()
        # Process and store the view counts for each video
        for item in response.get('items', []):
            video_id = item['id']
            view_count = item['statistics'].get('viewCount', 'N/A')
            stats[video_id] = view_count
    return stats

def get_meetings(api_key=None,channel_handle="",channel_id="",maximum=10,published_after=None):
    if not api_key:
        api_key=API_KEY
    if not channel_id:
        channel_id = resolve_channel_id(api_key,channel_handle)
    if channel_id:
        video_ids=get_all_video_ids(api_key,channel_id,maximum=maximum,published_after=published_after)
        titles=get_video_titles(api_key,video_ids)
        return titles
    print (f"Couldn't get channel_id for {channel_handle}")

if __name__ == '__main__':
    print(get_meetings(channel_id='UCpAxisSP5q5VadHDrMdMcyg'))
    #print(get_meetings(channel_handle='VTHouseOfReps'))

    #get_video_titles(api_key=API_KEY,video_ids=["6MzdeKCiy-k"])
    #print(resolve_channel_id(channel_handle='VTSenateAg'))
    #print(get_video_statistics(video_ids=["jQN7H9dW14M"]))
    #print(get_youtube_video_duration(video_ids=['vjmqVlDa7R8']))
    