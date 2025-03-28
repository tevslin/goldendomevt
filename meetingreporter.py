# -*- coding: utf-8 -*-
"""
Created on Tue Aug  6 18:15:31 2024

@author: tevsl
"""
import pickle
import os
import sys


import logging


from datetime import datetime
from urllib.parse import urlparse, parse_qs



#logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.propagate=False
# Set the logger's level to INFO
logger.setLevel(logging.INFO)

# Check if a handler already exists and add only if it's missing
if not logger.handlers:
    # Create a stream handler for stdout
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


class NewsOrg:
    def __init__(self,bucket,public_bucket,base_url,entities,filenames=('transcript.html','newsstory.html'),
                 storage='S3',sc=None,refresh=True):
        import pandas as pd
        if storage=='S3': #if storing on Amazon S3
            import bototools as bt #use the S3 support routines
        else: #otherwise assume local
            import fakeboto_tools as bt #and simulate s3 locally
        self.storage=storage
        self.bt =bt
        if sc:
            self.sc=sc
        else:
            import scraper as sc #the build will put the right scraper in
            self.sc=sc
        self.meetings_directory='meetings.pk1'
        self.bucket=bucket
        self.public_bucket=public_bucket
        self.url=base_url
        self.entities=entities
        self.filenames=filenames
        bt.check_bucket_exists(self.bucket) # will error out if no bucket
        bt.check_bucket_exists(self.public_bucket)
        self.meetings=bt.pickle_object_from_s3(self.bucket,self.meetings_directory)
        
        if not self.meetings is None:
            self.last_update=bt.get_last_modified_date(self.bucket,self.meetings_directory)
        else:
            self.last_update = None
            self.meetings=pd.DataFrame(columns=['Entity','Date'])
        if refresh:
            self.update_directory()
            
    def process_reports(self):
        """
        Function to process each row in the self.meetings DataFrame and update with correct URLs if files are found.
        also generates 'Download Video' item if needed (this code might be better at point where transcript actually downloaded)
        """
        import pandas as pd
        import numpy as np
        update = False  # Initialize the update flag
    
        # Retrieve all keys from the S3 bucket in one call
        bucket_keys = self.bt.list_keys_in_bucket(self.public_bucket)
        
        # Iterate through each row in the DataFrame
        for index, row in self.meetings.iterrows():
            if 'Download Video' not in row or pd.isna(row['Download Video']): # if we haven't located download url
                #if row['Origin'] !="manual":
                    self.meetings.at[index,"Download Video"]=self.sc.get_download_url(self.url,row['Video URL'])
                    update=True
            entity = row['Entity']
            date = row['Date']
    
            # Get the meeting ID using the provided routine
            meeting_id = get_meeting_id(entity, date.strftime('%Y-%m-%d %H:%M:%S'))
    
            # Check for each filename in self.filenames
            for filename in self.filenames:
                file_key = f"{meeting_id}_{filename}"
                file_column = os.path.splitext(filename)[0]  # Get the filename without the suffix (e.g., transcript.html -> transcript)
                if file_column not in self.meetings: #allow files to be added semindynamically
                    self.meetings[file_column]=np.nan
                    update=True
                # Check if the key exists in the retrieved S3 key list
                if file_key in bucket_keys:
                    #this should be changed so that boto and fakeboto can be used and the difference is at that level
                    if self.storage=='S3':
                        file_url = self.bt.get_s3_url(self.public_bucket, file_key)
                    else:
                        file_url=self.storage+"/"+self.public_bucket+"/"+file_key
                    ###
                    # Update the DataFrame if the value has changed
                    if self.meetings.at[index, file_column] != file_url:
                        self.meetings.at[index, file_column] = file_url
                        update = True  # Mark update as True if any change happens
                else:
                    # If no key matches, set the column to NaN
                    if not pd.isna(self.meetings.at[index, file_column]): #if file has been deleted
                        self.meetings.at[index, file_column] = np.nan
                        update = True  # Mark update as True if any change happens
    
        return update  # Return whether any changes were made
    
    def update_directory(self):
        import pandas as pd
        newdf=self.sc.extract_meeting_data(self.url,orgs=self.entities)
        col1='Entity'
        col2='Date'
        update=False
        for _, update_row in newdf.iterrows():
            mask = (self.meetings[col1] == update_row[col1]) & (self.meetings[col2] == update_row[col2])
            if mask.any():
            # Find the matching row
                old_row = self.meetings[mask].iloc[0]            
            # Copy over any columns from the old row that are missing or None in the update row
                for col in old_row.index:
                    if col not in update_row.index or pd.isna(update_row[col]) or update_row[col] is None:
                        update_row[col] = old_row[col]
                        
                self.meetings = self.meetings[~mask]

            else:
                update=True
            self.meetings = pd.concat([self.meetings, pd.DataFrame([update_row])], ignore_index=True)
        if self.process_reports():
            update=True
        if update: #if actually changed something
            self.bt.pickle_object_to_s3(self.bucket, self.meetings, self.meetings_directory)
            
    def get_meeting(self,entity, date):
        import pandas as pd
        "returns a meeting row from the index"
        if not isinstance(date,pd.Timestamp): #if we were passed a string
            date=pd.to_datetime(date) #convert it
        return self.meetings[(self.meetings['Entity'] == entity) & (self.meetings['Date'] == date)].iloc[0]
    
    def add_meeting(self,entity,date,time,title,video_url,origin="manual"):
        import pandas as pd
        "adds a manually supplied entity row to the table"
        timestamp=pd.to_datetime(f"{date} {time}")
        new_row=pd.DataFrame({
        'Entity': [entity],
        'Title': [title],
        'Date': [timestamp],
        'Video URL': [video_url],
        'Download Video':[video_url],
        'Origin':[origin]
        })
        self.meetings=pd.concat([self.meetings,new_row],ignore_index=True)
        self.bt.pickle_object_to_s3(self.bucket, self.meetings, self.meetings_directory)
        
    def delete_meeting(self,entity,datetime):
        "deletes a meeting row"
        import pandas as pd
        if not isinstance(datetime,pd.Timestamp): #if we were passed a string
            datetime=pd.to_datetime(datetime) #convert it
        old_length=len(self.meetings)
        self.meetings=self.meetings[~((self.meetings['Entity']==entity)&(self.meetings['Date']==datetime))]
        if len(self.meetings)<old_length:
            self.bt.pickle_object_to_s3(self.bucket, self.meetings, self.meetings_directory)
            logger.info(f"deleted {entity} {datetime}")
            return True
        logger.info(f"did not delete {entity} {datetime}")
        return False
        
        
    def delete_column(self,column_name):
        "utility functio for debugging"
        self.meetings=self.meetings.drop(column_name,axis=1)
        self.bt.pickle_object_to_s3(self.bucket, self.meetings, self.meetings_directory)
            
def get_meeting_id(entity,date):
    "makes a meeting id from the name of the entity holding the meeting and the datetime stamp of the meeting"
    return f"{entity.replace(' ','_')}{date.replace(' ','_').replace(':','-')}"

def format_yield(theMessage,timestamp=True):
    "formats a message in the correct form for flask yield"
    logger.info(theMessage)
    if timestamp:
        return(f"data: {datetime.now().strftime('%Y %m %d %H:%M:%S')} {theMessage}\n\n")
    else:
        return(f"data: {theMessage}\n\n")




def download_audio_direct(m3u8_url, output_file,loglevel='warning'):
    import ffmpeg
    logger.info("down_load_audio_direct entered")
    (
        ffmpeg
        .input(m3u8_url) #for debugging
        .output(output_file, 
                acodec='pcm_s16le',  # audio codec
                ar='44100',          # audio sampling rate
                ac=1,                # number of audio channels
                vn=None)             # no video
        .global_args('-loglevel',loglevel)
        .global_args('-threads', '0')  # Automatically use all available CPUs
        .global_args('-fflags', '+discardcorrupt')
        .global_args('-err_detect', 'ignore_err')
        .global_args('-rw_timeout', '60000000')   # 60 seconds read/write timeout
        #.global_args('-stimeout', '60000000')     # 60 seconds socket timeout
        .global_args('-reconnect', '1')           # Enable automatic reconnect
        .global_args('-reconnect_streamed', '1')  # Reconnect after stream starts
        .global_args('-reconnect_delay_max', '5') # Max delay of 5 seconds between reconnect attempts
        .run(overwrite_output=True)
    )
    logger.info("down_load_audio_direct ended")


           
def download_audio(m3u8_url,output_file):
    import subprocess
    from collections import deque
    command = [
        'ffmpeg',
        '-i', m3u8_url,
        #"-ss","01:00:00",
        #'-t',"00:45:00", #just for testing
        '-y', #overwrite if needed
        '-vn',  # no video
        '-acodec', 'pcm_s16le',  # audio codec
        '-ar', '44100',  # audio sampling rate
        '-ac', '1',  # number of audio channels
        output_file
    ]

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    output_lines = deque(maxlen=20)

    while True:
        output = process.stderr.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            output_lines.append(output.strip())
            yield f"data: {'<br>'.join(output_lines)}\n\n"

    # Send the remaining buffered lines if any
    for line in output_lines:
        yield f"data: {'<br>'.join(output_lines)}\n\n"
    return_code=process.poll()
    if return_code == 0:
        # Indicate successful completion and show "Next" button
        yield f"data: AUDIO_EXTRACTED:{output_file}\n\n"
    else:
        # Indicate failure and include error details
        yield f"data: ERROR:ffmpeg process failed with return code {return_code}\n\n"

def download_youtube(share_link,output_file):
    """downloads audio of you tube from share link"""         
    import yt_dlp
    
    o_f=output_file.split(".") #in case there's a ".wav' at the end which would be redundent

    ydl_opts = {
        'format': 'bestaudio/best',  # Download the best available audio
        'outtmpl': o_f[0],  # Specify the full output path and filename
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',  # Convert to WAV
            'preferredquality': '192',  # Set preferred quality (optional)
            }],        
        'postprocessor_args': ['-ac', '1'],  # Convert to mono (1 channel)
        }
    
    # Create a yt-dlp object with the specified options
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([share_link])
        
def consume_generator(the_function,console=True):
    for output in the_function:
        if console:
            print(output)
            
def download_audio_flex(url,output_file):
    if get_youtube_id(url):
        download_youtube(url,output_file)
    else:
        download_audio_direct(url,output_file)

def add_speaker_labels_to_transcription(words,silence_limit=None,bucket=None,file=None):
    # Initialize an empty string to hold the final transcript
    final_text = ""
    timing_list=[]
    speaker_dict={}
    current_speaker=''
    current_time=0
        
    for word in words:
        if silence_limit:   #if checking silences
            gap=word['start']-current_time #compute silence
            if gap>silence_limit*1000: #If too long
                timing_list.append((len(final_text),current_time,word['start']))
                final_text+=f"\n[{round(gap/1000)} seconds of silence]\n"
        speaker=word['speaker']
        if speaker!=current_speaker: # if new speaker
            
            if len(current_speaker)>0: # if not the beginning of text
                timing_list.append((len(final_text),word['start'],word['start'])) #deliberately zero duration
                final_text+='\n\n'
            timing_list.append((len(final_text),word['start'],word['start'])) #deliberately zero duration
            final_text+=f"[Speaker {speaker}]: "
            current_speaker=speaker
            speaker_dict[speaker]='yes'
        timing_list.append((len(final_text),word['start'],word['end']))
        final_text+=word['text']+" "
        timing_list.append((len(final_text),word['end'],word['end'])) #deliberately zero duration
        current_time=word['end']
    return final_text, timing_list,speaker_dict

def add_speaker_labels_to_transcription_dg(results,speaker_map=None,silence_limit=None,bucket=None,file=None):
    # Initialize an empty string to hold the final transcript
    final_text = ""
    timing_list=[]
    speaker_dict={}
    current_speaker=-1
    current_time=0
        
    for paragraph in results['channels'][0]['alternatives'][0]['paragraphs']['paragraphs']:
        if silence_limit:   #if checking silences
            gap=paragraph['start']-current_time #compute silence
            if gap>silence_limit: #If too long
                timing_list.append((len(final_text),current_time,paragraph['start']))
                final_text+=f"\n[{round(gap)} seconds of silence]\n"
        speaker=paragraph['speaker']
        if speaker!=current_speaker: # if new speaker
            speaker_name= f"Speaker {str(speaker)} "
            timing_list.append((len(final_text),paragraph['start'],paragraph['start'])) #deliberately zero duration
            if speaker_map:
                for person in speaker_map:
                    if person['speaker_id']==speaker and person['speaker_name']:
                        if person.get("confidence_level",0)>4:
                            speaker_name=person['speaker_name']
                        break
            current_speaker=speaker
            final_text+=f"[{speaker_name}]: "
            speaker_dict[speaker_name]='yes' #changed 12/13/24
        for sentence in paragraph['sentences']:
            timing_list.append((len(final_text),sentence['start'],sentence['end']))
            final_text+=sentence['text']+' '
            #timing_list.append((len(final_text),word['end'],word['end'])) #deliberately zero duration
            current_time=sentence['end']
        timing_list.append((len(final_text),paragraph['end'],paragraph['end'])) #deliberately zero duration
        final_text+='\n\n'
    timing_list = [(t[0],t[1]*1000,t[2]*1000) for t in timing_list] #convert to milliseconds
    return final_text, timing_list,speaker_dict

def deepgram_transcribe(input_file,output_file=None,topics=False):
    from tenacity import retry, stop_after_attempt, wait_fixed, after_log, before_log, RetryError
    import functools
    import httpx
    from deepgram.utils import verboselogs
    from deepgram import (
        DeepgramClient,
        DeepgramClientOptions,
        PrerecordedOptions,
        FileSource,
        )
 
    @retry(
        stop=stop_after_attempt(3),                  # Stop after 3 attempts
        wait=wait_fixed(2),                          # Wait 2 seconds between retries
        before=before_log(logger, logging.INFO),     # Log before each retry attempt
        after=after_log(logger, logging.INFO)        # Log after each retry attempt
        )

    def call_deepgram(func, *args, **kwargs):
        logger.info(f"call deepgram called with input {input_file}")
        response=func(*args,**kwargs)
        logger.info('good return')
        #logger.info(f"keys: {response.results.to_dict()['channels'][0]['alternatives'][0].keys()}")
        return response
          
    if 'DEEPGRAM_API_KEY' not in os.environ:
        from dotenv import load_dotenv
        load_dotenv()
    assert 'DEEPGRAM_API_KEY' in os.environ,"no API Key for Deepgram!"

    config: DeepgramClientOptions = DeepgramClientOptions(
            verbose=verboselogs.WARNING,
        )
    deepgram: DeepgramClient = DeepgramClient("", config)

    with open(input_file, "rb") as file:
        buffer_data = file.read()

    payload: FileSource = {
            "buffer": buffer_data,
        }
    print('nova3-3 test')
    keyterms=["Hinsdale","Rutland"]
    options: PrerecordedOptions = PrerecordedOptions(
        #model="nova-2-meeting",
        model="nova-3",
        topics=topics,
        keyterm=keyterms,
        utterances=True,
        punctuate=True,
        diarize=True,
        paragraphs=True
        )
    transcribe_func = functools.partial(
        deepgram.listen.rest.v("1").transcribe_file,
        payload, options, timeout=httpx.Timeout(600.0, connect=100.0)
    )

    response = call_deepgram(transcribe_func)
    logger.info("returned from deepgram")
    #logger.info(json.dumps(response.results.to_dict()['channels'][0]['alternatives'][0]['paragraphs']['paragraphs'][0]))

    if output_file:    #if supposed to save output
        with open(output_file,'wb') as f:
            pickle.dump(response.results.to_dict(),f)
    
    return response


    
def assemblyai_transcribe(url_or_path,speaker_labels=True,speakers_expected=10,file=None):
    import assemblyai as aai
    import os
    
    if 'ASSEMBLYAI_KEY' not in os.environ:
        from dotenv import load_dotenv
        load_dotenv()
    assert 'ASSEMBLYAI_KEY' in os.environ,"no API Key!"
    aai.settings.api_key =os.getenv('ASSEMBLYAI_KEY')
    aai.settings.http_timeout = None #added per assemblyai support to avoide starlink timeout    
    transcriber = aai.Transcriber()
    config = aai.TranscriptionConfig(speaker_labels=speaker_labels,speakers_expected=speakers_expected)
    transcript = transcriber.transcribe(url_or_path, config)
    payload=transcript.json_response
    if file:    #if supposed to save output
        with open(file,'wb') as f:
            pickle.dump(payload,f)
    return payload

def make_smart_transcript(text, timing_file, title, output, video):
    # Load the text from the file
    with open(text, 'r') as file:
        text_content = file.read()

    # Load the word_table from the pickled file
    with open(timing_file, 'rb') as f:
        word_times = pickle.load(f)
    make_smart_transcript_data(text_content,word_times,title,output,video)

def get_youtube_id(video):
    "extracts the id from all 3 forms of the youtube url. returns none if not youtube"
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

def video_to_transcript(video_url,title,output_file,delete_temp=True,smart_names=False,hint_list=None,
                        topics=False,
                        temp_file=None):
    from pathlib import Path
    import tempfile
    if not temp_file:
        fd,temp_file=tempfile.mkstemp(suffix=".wav")
        os.close(fd)
    download_audio_flex(video_url, temp_file)
    result=deepgram_transcribe(temp_file,topics=topics)
    if smart_names:
        final_text,timing_list,speaker_dict=add_speaker_names_to_transcript(
            result.results.to_dict(),hint_list=hint_list,silence_limit=15)
    else:
        final_text,timing_list,speaker_dict=add_speaker_labels_to_transcription_dg(
            result.results.to_dict(),silence_limit=15)
    output_file=Path(output_file)
    if output_file.suffix.lstrip('.')=='html': #if want actual smart transcript
        make_smart_transcript_data(final_text,timing_list,title,output_file,video_url)
    else:   #otherwise making pickle file for later processing
        timing_dir={
            "video_url":video_url,
            "title":title,
            "final_text":final_text,
            "timing_list":timing_list,
            "speaker_dict":speaker_dict
            }
        with open(output_file,"wb") as f:
            pickle.dump(timing_dir,f)
    if delete_temp:
        os.remove(temp_file)
def add_speaker_names_to_transcript(result,hint_list=None,special_instructions="",silence_limit=None,bucket=None,file=None):
    "uses llm to map speaker numbers to names"
    
    #from pydantic import BaseModel
    import json
    from openai import OpenAI
    if 'OPENAI_API_KEY' not in os.environ:
        from dotenv import load_dotenv
        load_dotenv()
    try:
        client=OpenAI()
    except Exception as e:
        logger.error(f"Error logging on to OpenAI: {e}")
        raise
    #get a draft of transcript with speaker numbers     
    final_text,timing_list,speaker_dict=add_speaker_labels_to_transcription_dg(result)
    system_prompt="""
    
    You are a careful reader and have good deductive skills. You will be provided with a transcript of
    a meeting in which speakers are identified in the form "Speaker 0", "Speaker 1" etc. The number is the speaker id.
    Your job is to deduce from
    the content of the transcript the apparent names of the various speakers and provide structured output assigning
    a name to a speaker id wherever possible and give a reason for your assignment as well as a confidence indicator
    between one 0 and 10 where ten is the highest confidence.
    You may also be given a hint which will be the names and roles of the offical members of the body which is meeting.
    They may or may not be at the meeting for which the transcript is made. A roll call, if there is one, will help
    you know who is in attendance.
    The first person to speak may well not be the person who opens the meeting. They may be a technician or just someone caught onmike when recording began. 
    The person who opens the meeting should be identified by the fact that they did some sort of call to order or made
    some introductory remarkor described what will happen or who will appear before the meeting.
    You should assume that the person who opens the meeting (who may not be the first person to speak)
    is the chair unless there is evidence to the contrary and should use the
    name of that person if you have enough information to know what the nanme is. If you are confident that he
    vice chair opened the meeting, use their name
    The transcript you are given is phonetic and so it is quite possible that it will contain misspelled names.
    If a name is phonetically close to one of the names in the hint list, you should use the name from the hint list rather
    than the misspelled name from the transcript. For example, if the transcript includes the chair recognizing Representative
    "Chadwicky" when there is no representative Chadwicky in the hint but there is a "Satcowitz", you shoud supply Satcowitz as
    the speaker who spoke after being recognized.
    Always make a list entry for each speaker in the transcript. These are the speakers you will find in 
    this transcript:
        {'.\n'.join(speaker_dict.keys())}
    You must have an entry for each of them in your answer even if you cannot make an identification.
    If you cannot make an identification, set a null string as the name and assign a confidence of zero.
    """
    
    
    json_schema={"type": "json_schema",
     "name": "speakers_array",
      "schema": {
        "type": "object",
        "properties": {
          "speakers": {
            "type": "array",
            "description": "An array of speakers.",
            "items": {
              "type": "object",
              "properties": {
                "speaker_id": {
                  "type": "number",
                  "description": "ID assigned by transcription."
                },
                "speaker_name": {
                  "type": "string",
                  "description": "Best guess at the name. This may be an empty string."
                },
                "reason": {
                  "type": "string",
                  "description": "The reason you have assigned the particular name to this speaker."
                },
                "confidence_level": {
                  "type": "number",
                  "description": "Value from 1 to 10 indicating confidence in the name mapping. 10 is high."
                }
              },
              "required": [
                "speaker_id",
                "speaker_name",
                "reason",
                "confidence_level"
              ],
              "additionalProperties": False
            }
          }
        },
        "required": [
          "speakers"
        ],
        "additionalProperties": False
      },
      "strict": True
    }



    user_prompt=f"""
    {special_instructions}
    <begin transcript>
    {final_text}
    <end transcript>
    """
    if hint_list:
        hints='\n'.join(hint_list)
        user_prompt+=f"""
        <begin hint>
        {hints}
        <end hint>
        """
    try:
        completion = client.responses.create(
        model="gpt-4o-2024-08-06",
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text={"format":json_schema}
        )
    except Exception as e:
        logger.error(f"ChatGPt call failed: {e}")
        raise
    answer=json.loads(completion.output_text)
    logger.info(answer)
    
    return(add_speaker_labels_to_transcription_dg(result,
        speaker_map=answer['speakers'],silence_limit=silence_limit,
        bucket=bucket,file=file))

def make_summary(inbucket,outbucket,meeting,subdirectory="summaries",
                 url="https://testgoldy.s3.us-east-1.amazonaws.com"):
    from bototools import pickle_object_from_s3
    
    meeting_dir=pickle_object_from_s3(inbucket,meeting+'.pk1')
    make_summary_data(meeting_dir,outbucket,meeting,subdirectory)
    
def make_summary_data(meeting_dir,outbucket,meeting,subdirectory="summaries",
                 url="https://testgoldy.s3.us-east-1.amazonaws.com"):
    from bototools import upload_object_to_s3
    the_summary=make_smart_summary(meeting_dir)
    summary_title=f"AI Summary of Vermont {meeting_dir['title']}"
    the_summary=f"<h1>{summary_title}</h1>{the_summary}</br><a href='/{meeting}.html'>Open SmartTranscript of {meeting}</a>"
    #print(the_summary)
    #now make a whole page
    summary_page=f"""
    <!DOCTYPE html>
    <html lang=en>
    <head>
    <meta charset="UTF-8">
    <title>{summary_title}</title>
    <meta name="description" content={summary_title}/>
    <meta property="og:type" content="article" />
    <meta property="og:url" content="{url}/{subdirectory}/{meeting}.html" />
    <meta property="og:image" content="https://goldendomevt.com/statehouse.png" />
    <meta name="twitter:card" content="summary" />
    <meta name="twitter:title" content="{summary_title}" />
    <meta name="twitter:description" content="{summary_title}" />
    <meta name="twitter:image" content="https://goldendomevt.com/statehouse.png" />
    <script type="application/ld+json">
        {{
      "@context": "https://schema.org",
      "@type": "Article",
      "headline": "{summary_title}",
      "datePublished": "{meeting.split('_')[1]}",      
      "creator": {{
        "@type": "Organization",
        "name": "OpenAI",
        "alternateName": "ChatGPT-4"
      }},
      "isBasedOn": {{
        "@type": "VideoObject",
        "name": "{summary_title}",
        "url": "{meeting_dir['video_url']}",
        "uploadDate":"{meeting.split('_')[1]}",
        "thumbnailUrl":"https://img.youtube.com/{get_youtube_id(meeting_dir['video_url'])}/default.jpg"
      }}
    }}
    </script>
    <script>
  function loadOptionalScript(url) {{
  const script = document.createElement('script');
  script.src = url;
  script.type = 'text/javascript';
  script.async = true;

  // Define the onload event handler
  script.onload = () => {{
    console.log(`Script loaded successfully: ${url}`);
    // You can add additional logic here to execute after the script loads
  }};

  // Define the onerror event handler
  script.onerror = () => {{
    console.warn(`Failed to load script: ${url}`);
    // Handle the error or provide fallback functionality here
  }};

  // Append the script to the document's head or body
  document.head.appendChild(script);
}}


loadOptionalScript('https://example.com/optional-script.js');
</script>
    </head>
    <body>
    <div id="summary-content" style="max-width: 7.5in;">
    {the_summary}
    </div>
    </br></br>
    <h3>Explanation:</h3>
    <p>This summary was made using ChatGPT to summarize a transcript of a Vermont legislative session.</p>
    <p>The transcript itself was made by DeepGram from the offical YouTube video of the session. Speaker IDs were deduced by ChatGPT.</p>
    <p>Neither the transcript nor the summary have been checked by humans and will contain some errors. However, you can use the link above to open a SmartTranscript of the meeting which will give you access both to the full transcription and the video from which it was made.</p>
    <p> You can see summaries and SmartTranscripts of all 2025 Vermont legislative meetings at <a href="https://goldendomeVT.com"> GoldenDomeVT.com</a>, a free non-commercial, non-partisan website developed to make the workings of Vermont state government more accessible. No registration is required and no personal data is collected.</p> 
    </body>
    </html>
    """
    upload_object_to_s3(outbucket,summary_page,subdirectory+'/'+meeting+'.html',ContentType='text/html')
    print (f"{meeting} uploaded to {outbucket}/{subdirectory}")
     
def make_smart_summary(timing_dir,length=200,format="html"):
    #make a summary (not yet smart) from the timing dictionary which includes transcript of meeting
    from openai import OpenAI
    if 'OPENAI_API_KEY' not in os.environ:
        from dotenv import load_dotenv
        load_dotenv()
    try:
        client=OpenAI()
    except Exception as e:
        logger.error(f"Error logging on to OpenAI: {e}")
        raise
    bolding_instruction =""
    if format=='html':
        
        bolding_instruction="""
        use '<strong>...</strong>' for bolding.
        use <p>...</p> for paragraphs.
        these are the only html tags to use.
        do not enclose your output in '<html>....</html>' or '<body>...</body> tags.
        Do not insert newline characters. Spacing will be done based on <p> tags.
        """
    elif format=='md':
        bolding_instruction= "use '**...**' for bolding."
        
    system_prompt=f"""
        You are a good reader and good at summarization. The user will give you a transcript of a meeting.
        Your job is to produce a {length} word summary of the meeting a {format} snippet. You do not editorialize in any way.
        Do not generate a title.
        Do not repeat the name of the meeting or its date and time in the summary since they will be shown elsewhere.
        Do not use any subtitles in the summary. It should be at most three paragraphs long.
        Proper names in the summary should always be bolded as should the names of legislation discussed.
        {bolding_instruction}
        Legislation will often be referred to as, for example, S. 345 or H. 98 indicating a bill from the house or the senate
        or "<something> Act".
        Just report direct facts from the meeting.
        Do NOT enclose your answer in back ticks(```).s.
        Use only simple apostrophes and quotation marks so that they will be rendered properly in all browsers and fonts.
        DO NOT use curled apostrophes or quotation marks.
    """
    user_prompt=f"""
        The title of the meeting is {timing_dir['title']}.
        <transcript>
        {timing_dir['final_text']}
        <end trancript>
        """
    try:
        completion = client.responses.create(
        model="gpt-4o-2024-08-06",
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        )
    except Exception as e:
        logger.error(f"ChatGPt call failed: {e}")
        raise
    #print (system_prompt)
    return(completion.output_text)
        
    
    
def make_smart_transcript_data(text_content,word_times,speaker_list,title, output=None,video=""):
    # Determine the video type based on the file extension
    video_type = ''
    video_id=get_youtube_id(video)
    if video_id: #if is youtube
        video_type="youtube"
    elif video.endswith('.mp4'):
        video_type = 'video/mp4'
    elif video.endswith('.webm'):
        video_type = 'video/webm'
    elif video.endswith('.m3u8'):
        video_type = 'application/x-mpegURL'

    

    # Basic HTML structure
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <link rel="stylesheet" href="smart_transcript.css">
        <link rel="stylesheet" href="search_dropdown_styles.css">

    """
    if video_type == 'application/x-mpegURL':
        html_content += """
            <script src='https://cdn.jsdelivr.net/npm/hls.js@latest'></script>
    """
    html_content+=f"""
    </head>
    <body>
    <header>
    <nav>    </nav>


    </header>
    <div id="main-container">
    <div id="header-container">
        <h1>SmartTranscript of {title}</h1>
        <h3 style="margin-top: 20px;">Select text to play as a video clip.</h3>
    </div>
        <div id="container">
        <div id="text-container">{text_content}</div>
        <div id="video-player">
        <div id="time-range">Select text if you'd like to play only a clip.</div>
        <button id="play-clip-button" class="control-button" disabled>Play Clip</button>
        <button id="play-full-video-button" class="control-button">Play Full Video</button>
        <button id="pause-resume-button" class="control-button" disabled>Pause</button>
        

    """
    if video_type=='youtube':
        html_content+=f"""
        <div id="playerContainer"></div>
        <script src="youtubePlayer.js"></script>
        <script type="text/javascript">
        let videoPlayer = new VideoPlay('{video_id}', 'playerContainer');
        </script>
        
    """
    else:      
        html_content+=f"""
      
        <video id="playerContainer" controls>
            <source id="video-source" src="{video}" type="{video_type}">
            Your browser does not support the video tag.
        </video>
        <script type="text/javascript">
        let videoPlayer = document.getElementById("playerContainer");;
        </script>
        
    """
    html_content+=f"""
        <script src="search_dropdown_script.js"></script>
        <div>
        <p>This transcript was computer-produced using some AI. Like closed-captioning, it won't be fully accurate. Always verify anything important by playing a clip.</p>
        <p> </p>
        <p>Speaker IDs are still experimental</p>
        </div>
         <div id="footer" class="footer3"></div>
        </div>

        <script src=standardVideo.js></script>
        <script src="footer_loader_script.js"></script>
        <div id="email-subject" style="display: none;">SmartTranscript of {title}</div>
        <div id="email-body" style="display: none;">This is useful for seeing what happened at the meeting without wading through the whole transcript: </div>
        <!-- Invisible table with word timings -->
        <table id="word-timings" class="invisible">
    """

    # Add rows to the invisible table for each word's start and end time
    for word_time in word_times:
        position=word_time[0]
        start_time = word_time[1]
        end_time = word_time[2]
        html_content += f"<tr><td>{position}</td><td>{start_time}</td><td>{end_time}</td></tr>"

    html_content += """
        </table>

        <table id="speaker-id" class="invisible">
        """
    for key in speaker_list:
        html_content += f"<tr><td>{key}</td></tr>"
    html_content +="""
        </table>     
    """
    if video_type == 'application/x-mpegURL':
        html_content += f"""
        <script type="text/javascript">
            if (Hls.isSupported()) {{
                var video = document.getElementById('playerContainer');
                var hls = new Hls();
                hls.loadSource('{video}');
                hls.attachMedia(video);
            }}
        </script>
    """
    html_content += """
    </body>
    </html>
    """

 

    # Write the HTML content to the specified output file
    if output:
        with open(output, 'w') as file:
            file.write(html_content)
    else:
        return html_content 

if __name__ == '__main__':
    WORKING_DIRECTORY = "meetingdocs"
    PUBLIC_DIRECTORY="meeting"
    BASE_URL= "https://www.orcamedia.net/local-government"
    ENTITIES=['Berlin Selectboard', 'Bethel Selectboard', 'Calais Selectboard', 'East Montpelier Selectboard',
          'Middlesex Selectboard', 'Montpelier City Council', 'Moretown Selectboard', 'Randolph Selectboard', 
          'Rochester Selectboard', 'Waterbury Municipal Meetings']
    #import orca_scraper as sc
    #no=NewsOrg(WORKING_DIRECTORY,PUBLIC_DIRECTORY,BASE_URL,
               #['Berlin Selectboard'],storage=r"C:\Users\tevsl\Documents\orcaroot",sc=sc)
   
    import pickle
    url = "https://cambridgema.granicus.com/ViewPublisher.php?view_id=1"
    url = "https://cambridgema.granicus.com/"
    #url='https://archive-stream.granicus.com/OnDemand/_definst_/mp4:archive/cambridgema/cambridgema_c51d6384-8ad4-4b02-9982-26fd91d22a19.mp4/playlist.m3u8'
    bucket="caimeetingdocs"
    mod="Bethel_9-23-24"
    #url="https://youtu.be/e7bVMxL251E?si=K1y9Xun-_OklcJWK"
    wav_file=rf"C:\Users\tevsl\Downloads\{mod}.wav"
    wav_file=r"C:\Users\tevsl\docker\mr\onetrack.wav"
    #wav_file=r"C:\Users\tevsl\Downloads\Randolph8-8.wav"
    wav_file=f"{mod}.wav"
    words_file=f"{mod}words.pk1"
    text_file=f"{mod}text.txt"
    timings_file=f"{mod}timings.pk1"
    public="ccmeeting"
    """
    #consume_generator(download_audio(downloadurl,wav_file),console=True)
    #download_youtube(url,mod)
    #response=deepgram_transcribe(wav_file,f"{mod}.pk1")
    #final_text,timing_list,speaker_dict=add_speaker_labels_to_transcription_dg(response.results.to_dict(),silence_limit=15)
   
    with open(f"{mod}.pk1","rb") as f:
        results=pickle.load(f)
    final_text,timing_list,speaker_dict=add_speaker_labels_to_transcription_dg(results,silence_limit=15)
    with open(f"{mod}.pk1","rb") as f:
        results=pickle.load(f)
    make_smart_transcript_data(final_text,
                timing_list,f"Bethel 9/23/24 Selectboard",f"{mod}.html",url)
                
                      
    
    #latest_date=get_meetings_df(bucket)["Meeting Date"].max()
    org=NewsOrg(bucket,public,url,["City Council"])
    
    transcript=assemblyai_transcribe(wav_file)
    with open(words_file,'wb') as f:
        pickle.dump(transcript["words"],f)
    print(transcript["words"][:100])
    #with open ("randolph8-8words.pk1",'rb') as f:
        #text=pickle.load(f)
    final_text,timing_list,speaker_dict=add_speaker_labels_to_transcription(transcript['words'],silence_limit=15)
    #with open (timings_file,'wb') as f: 
        #pickle.dump(timing_list,f)
   # with open(text_file,'w') as f:
        #f.write(final_text)


    title=mod
    output=f"{mod}videox.html"
    in_file_path = r"https://archive-stream.granicus.com/OnDemand/_definst_/mp4:archive/cambridgema/cambridgema_1167ead5-c909-44e0-a560-4390a9368b71.mp4/playlist.m3u8"
    make_smart_transcript_data(final_text,
                    timing_list,
                          title,output,in_file_path)
    
    #print (org.meetings)
    #org.update_directory()
    #print(org.meetings)

    process_and_upload_df("caimeetingdocs", df)
    
    upload_file_to_s3("caimeetingdocs","omniwhisper..py","testy/testy.py")
    
    the_object=[1,2,3]
    pickle_object_to_s3("caimeetingdocs", the_object, "testy/testy.pk1")
    
    latest_date=get_meetings_df(bucket)["Meeting Date"].max()
    if latest_date:
        print(f"The latest date in the folders is: {latest_date}")
    else:
        print("No valid folders found.")
    """
    