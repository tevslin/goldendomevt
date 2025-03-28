# -*- coding: utf-8 -*-
"""
Created on Wed Dec 25 15:39:33 2024

@author: tevsl
"""


import os
import logging
import json

logging.basicConfig(
    level=logging.DEBUG,  # Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda function to start with JSON transcript in bucket and create both
    transcript dictionary to store in transcript bucket and smarttranscript to go in display bucket.
    triggered by arrival of JSON file.
    """

    # Deepgram API Key from environment variable

    for record in event['Records']:
        try:
            bucket_name = record['s3']['bucket']['name']
            file_key = record['s3']['object']['key']
            if bucket_name.startswith('test'):
                prefix='TEST_'
            else:
                prefix=''
            display_bucket=os.environ.get(prefix+'DISPLAY_BUCKET')
            transcript_bucket=os.environ.get(prefix+'TRANSCRIPT_BUCKET')
            url=os.environ.get(prefix+'DISPLAY_URL')
            if file_key.endswith('.json'):
                logger.info(f"Processing file: {file_key} in bucket: {bucket_name}")
                process_request(bucket_name, file_key,transcript_bucket=transcript_bucket,display_bucket=display_bucket,url=url)
            else:
                logger.info(f"Skipped unsupported file type {file_key}")
        except Exception as e:
            logger.error(f"Error processing record: {record}")
            logger.error(f"Exception: {e}")
            
def process_request(bucket_name,file_key,transcript_bucket="testdeepgramtranscript",
                    display_bucket="testgoldy",weekly_list="weekly.pk1",url="https://testgoldy.s3.us-east-1.amazonaws.com"):
    #because no values from caller may override
    from bototools import retrieve_from_s3,pickle_object_from_s3,pickle_object_to_s3,upload_object_to_s3
    from meetingreporter import add_speaker_names_to_transcript,make_smart_transcript_data,make_summary_data
    

    split=file_key.split(".")
    header_data=pickle_object_from_s3(bucket_name,split[0]+'.pk1')
    deepgram_result=retrieve_from_s3(bucket_name,split[0]+'.json')
    committee=split[0].split('_')[0]
    meeting_date=split[0].split('_')[1]

    try:
        hint_list=retrieve_from_s3(display_bucket,committee+'.txt')
        hint_list="Committee Members:\n"+hint_list
    except:
        hint_list=None
    if weekly_list:
        try:
            weekly=pickle_object_from_s3(display_bucket,weekly_list)
        except:
            weekly=None
            details=None
    if weekly:
        details=weekly.get(committee,None)
        if details:
            assistants=details.get("assistants")
            if assistants:
                hint_list+="\nAssistants:\n"+'\n'.join(assistants)
            witnesses=details.get("speakers")
            if witnesses:
                witness_list=next((d for d in witnesses if d.get("date") == meeting_date), None)
                if witness_list:
                    hint_list+='\nWhitnesses:\n'+'\n'.join(witness_list.get('speakers',[]))
    print(f"hint list {hint_list}")
    special_instructions="""
    This is a meeting of committee of the Vermont Legislature.
    Each committee has members who serve as Chair, Vice Chair, and usually a Clerk.
    The committee also has an assistant who is often called the legislative counselor
    and may have other assistants as well. A committe also takes testimony from witnesses.
    When assigning names, use the committee role of the person and their full name if you know both from
    context or from the hints which may be provided. For example, Sen. Joe Smith would be Chair Joe Smith
    if he happens to be chair but Member Joe Smith if he is a member of the committee but not Chair,
    Vice Chair, or Clerk. Other roles to use are Assistant and Witness. Always use those titles for
    the Chair, the Vice Chair, and the Clerk. if there are assistants or witnesses in the
    hint list and you have a reasonable match with the speaker, give roles for them as well.
    However, you may omit a role and use just the name if you
    are uncertain.
    """
    final_text,timing_list,speaker_dict=add_speaker_names_to_transcript(
            json.loads(deepgram_result)['results'],hint_list=hint_list,special_instructions=special_instructions, 
            silence_limit=15)
    timing_dir={
            "video_url":header_data['video'],
            "title":header_data['title'], 
            "final_text":final_text,
            "timing_list":timing_list,
            "speaker_dict":speaker_dict
            }
    pickle_object_to_s3(transcript_bucket,timing_dir,split[0]+'.pk1')
    make_summary_data(timing_dir,display_bucket,split[0],url=url)
    html=make_smart_transcript_data(final_text,timing_list,speaker_dict,header_data['title'],"",header_data['video'])
    upload_object_to_s3(display_bucket,html,split[0]+'.html',ContentType='text/html')
if __name__ == '__main__':
    process_request("proddeepgramaudio","VTHouseCommEcoDev_2025-03-14_14-30.json",
                    transcript_bucket="proddeepgramtranscript",display_bucket="goldendomevt.com")
    
    
    
        