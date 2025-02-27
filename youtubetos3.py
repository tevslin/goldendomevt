# -*- coding: utf-8 -*-
"""
Created on Tue Dec 24 10:51:21 2024

@author: tevsl
"""
import os
import logging
from mylogger import setup_logging
import time
from datetime import datetime
from pathlib import Path
from bototools import list_keys_in_bucket,pickle_object_to_s3,upload_file_to_s3,get_presigned_url,upload_object_to_s3

def get_s3_video_duration(bucket_name,object_key):
    import ffmpeg
    presigned_url=get_presigned_url(bucket_name,object_key)
    try:
        probe = ffmpeg.probe(presigned_url)
        format_info = probe.get('format', {})
        duration = format_info.get('duration', 'Unknown')
        return float(duration)
    except ffmpeg.Error as e:
        print(f"An error occurred: {e.stderr.decode()}")
        return None
    
def get_local_video_duration(file_path):
    import ffmpeg
    try:
        # Use ffprobe to retrieve metadata
        probe = ffmpeg.probe(file_path)
        # Extract the duration from the format information
        duration = float(probe['format']['duration'])
        return duration
    except ffmpeg.Error as e:
        print(f"An error occurred: {e}")
        return None

def get_ytdlp_video_duration(share_link):
    import yt_dlp
    
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # Extract video information
        info_dict = ydl.extract_info(share_link, download=False)
    return info_dict.get('duration')
    
    
def download_youtube(share_link, output_file):
    """
    Downloads the best available audio from YouTube, ensures mono audio,
    and returns the full path of the generated file including its extension.
    """
    import yt_dlp

    # Remove any existing extension from the output file
    o_f = output_file.split(".")[0]

    # yt-dlp options for best audio download with mono conversion
    ydl_opts = {
        'format': 'bestaudio',  # Download the best available audio
        'outtmpl': f"{o_f}.%(ext)s",  # Dynamically use the correct extension
        'postprocessor_args': ['-ac', '1'],  # Convert audio to mono (1 channel)
        'noplaylist': True,  # Ensure only the single video is downloaded
    }

    # Create a yt-dlp object with the specified options
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # Extract video info (includes metadata) and download the file
        info = ydl.extract_info(share_link, download=True)

        # Generate the actual output file path based on metadata
        generated_file_path = ydl.prepare_filename(info)

    return generated_file_path



def main(maximum=5, display_bucket='testgoldy', destination_bucket='testdeepgramaudio', front='google', 
         loop_time=200,start_on='24-05-01',backoff=12,channel="",max_delta=60,console=False):
    import pickle
    from dateutil import parser
    from zoneinfo import ZoneInfo
    from dateutil.relativedelta import relativedelta
    from youtubeapi import get_meetings
    from bototools import list_keys_in_bucket,pickle_object_to_s3,upload_file_to_s3,get_presigned_url,upload_object_to_s3
    
    no_date_backoff=2 #days tyo backoff if calcing date and there is no last_date file
    
    setup_logging()
    logger = logging.getLogger("example_logger")
    
    logger.info(f"Maximum: {maximum}")
    logger.info(f"Test Bucket: {display_bucket}")
    logger.info(f"Destination Bucket: {destination_bucket}")
    logger.info(f"Front: {front}")
    logger.info(f"Loop Time: {loop_time}") 
    logger.info(f"Start On: {start_on}")
    logger.info(f"Backoff: {backoff}")
    logger.info(f"Channel: {channel}")
    logger.info(f"Max_delta: {max_delta}")

    test_bucket=display_bucket

    temp_name='temp'
    my_timezone = ZoneInfo("America/New_York")
    started_at=datetime.now(my_timezone)
    if start_on: #if start time specified, use it    
        parsed_date=parser.parse(start_on)
        start_time=parsed_date.replace(tzinfo=my_timezone)
    else: #if supposed to calulate time
        try: #see if the file is there
            with open("lasttime.pk1","rb") as f:
                last_start=pickle.load(f)
            start_time=last_start-relativedelta(hours=backoff)
        except:
            logger.warning("No last date file.")
            print ("no last date file")
            start_time=started_at-relativedelta(days=no_date_backoff)
        
    logger.info(f"Looking for postings after {start_time}")
    print (f"Looking for postings after {start_time}")
    with open("committees.pk1",'rb') as f:
        all_channels=pickle.load(f)
    if channel: #if only processing one channel
        if channel in all_channels:
            channels={channel:all_channels[channel]}
        else:
            logger.error(f"channel {channel} is not recognized and won't be processed")
            print(f"channel {channel} is not recognized and won't be processed")
            return
    else: #if doing all channels
        channels=all_channels
    fully_done=list_keys_in_bucket(test_bucket)
    in_progress=list_keys_in_bucket(destination_bucket)
    upload_count=0
    for channel_handle,channel_id in channels.items():
        print(f"Processing {channel_handle}")
        if console:
            user_input=input("enter to continue")
        meeting_list=get_meetings(channel_id=channel_id,published_after=start_time,maximum=maximum)
        logger.info (f"{len(meeting_list)} found for {channel_handle}.")
        for item in meeting_list:
            try: #need to be bulletproof
                key=item[0]
                video_url=f"https://www.youtube.com/live/{key}"
                dt = item[2]
                file=f"{channel_handle}_{dt}"
                if file+'.html' in fully_done:
                    logger.info(f"file {file} is fully processed.")
                elif file+'.pk1' in in_progress:
                    logger.warning (f" file {file} is in process")
                elif key+"._ph" in in_progress: #if this is a reload
                    logger.info(f"Key {key} has been reloaded.")
                    print(f"Key {key} has been reloaded.")
                else:
                    ytdlp_duration=get_ytdlp_video_duration(video_url)
                    delta=abs(ytdlp_duration-item[3])
                    if delta>max_delta:
                        logger.error (f'{key} posted at {dt} for {channel_handle} skipped  because the difference between ytdlp duration {ytdlp_duration} and youtube duration {item[3]} is too great. ')
                        continue
                    begin_time=time.time()
                    logger.info(f"Beginning download for {file}")
                    out_name=download_youtube(video_url, temp_name)
                    ffmpeg_duration=get_local_video_duration(out_name)
                    delta=abs(ffmpeg_duration-item[3])
                    if delta>max_delta:
                        logger.error (f'{key} posted at {dt} for {channel_handle} skipped  because the difference between ffmpeg duration {ffmpeg_duration} and youtube duration {item[3]} is too great. ')
                    else:
                        upload_file_to_s3(destination_bucket, out_name,file+Path(out_name).suffix)
                        place_holder={"video":video_url,"title":item[1],"channel":channel_handle,"timestamp":datetime.now(),"front":front,"duration":item[3]}
                        pickle_object_to_s3(destination_bucket,place_holder,file+'.pk1')
                        upload_object_to_s3(destination_bucket,file,key+'._ph')
                        upload_count+=1
                    os.remove(out_name)
                    elapsed_time=time.time()-begin_time
                    sleep_time=loop_time-elapsed_time
                    if sleep_time>0:
                        logger.info(f"sleeping {sleep_time} seconds.")
                        time.sleep(sleep_time)
            except Exception as e:
                #import pdb; pdb.set_trace()
                logger.error(f"Video {video_url} {item[1]} for {channel_handle} skipped because of error {e}")
                #print (time_part,date_part)
    with open("lasttime.pk1","wb") as f:
              pickle.dump(started_at,f)
    logger.info (f"Finished. {upload_count} files uploaded to s3")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description="Download videos to s3")

    # Add arguments with defaults
    parser.add_argument("--maximum", type=int, default=5, help="Maximum videos per run (default: 5)")
    parser.add_argument("--display_bucket", type=str, default='goldendomevt.com', help="Test bucket name (default: 'goldendomevt.com')")
    parser.add_argument("--destination_bucket", type=str, default='proddeepgramaudio', help="Working bucket name (default: 'proddeepgramaudio')")
    parser.add_argument("--front", type=str, default='google', help="where front end is running(default: 'google')")
    parser.add_argument("--loop_time", type=int, default=200, help="Loop time in seconds (minimum time between downloads, default: 200)")
    parser.add_argument("--start_on",type=str,default='',help="First date/time to process (default= ''). empty string means calc from file.")
    parser.add_argument("--backoff",type=int,default=12,help="hours to backoff from start of last run to calculate start_on. default:12")
    parser.add_argument("--channel", type=str, default="", 
                        help="Channel handle if processing only one channel (default: null string meaning process all channels)")
    parser.add_argument("--max_delta", type=int, default=60, help="Maximum difference in seconds allowed between ffmpeg and youtube durations (default: 60)")
    # Parse command line arguments
    args = parser.parse_args()

    # Call the main function with parsed arguments
    main(maximum=args.maximum, display_bucket=args.display_bucket, 
         destination_bucket=args.destination_bucket, front=args.front, loop_time=args.loop_time,start_on=args.start_on,
         backoff=args.backoff,channel=args.channel,max_delta=args.max_delta)
