# GoldenDomeVT

## WIP
is being loaded with the code which implements GoldenDomeVT.com and SmartTranscripts.

This repository is particular to the site GoldenDomeVT.com and the factory for creating and serving SmartTranscripts of committee and floor meetings of the Vermont Legislature. SmartTrancripts are text transcripts linked to actual videos in such a way that a user can select text and immediately play the corresponding video clip in an imbedded viewer appropriate to the video type. Much of the code is general and can be used to create SmartTranscripts from a variety of online video sources, but some of it uses specific S3 Buckets and URLs whose names are hardcoded as defaults. These need to be replaced with folders or your own s3 buckets to run the code for other meetings. GoldenDomeVT ruins off a list of YouTube channels used by the Vermont Legislature so, at least, needs a different channel list for meetings of other entities. It also uses a number of other files created from the webpages of the Vermont Legislature. Sample of these files are in the samples folder on this repository.
## The Factory
The factory currently runs partly on a Google debian instance and partly on AWS. Storage for the factory is S3 buckets. The part which runs on Google would run on any Linux system. The only real Linux dependency is the cron job. Absent that, the code would run whereever Python is supported. Similarly the code which runs on AWS is dependent for triggering on S3 bucket events but, other than the triggering dependency, can be called in any Python environment.

![The Factory](/assets/factory.png)

## Python Code
1. **bototools3.py**
 - function: tools for working with s3 buckets
 - implementation in goldendomevt: used in youtubetos3.py as well as the lambda routines s3deepgrams3.py and jsontohtml.py for all bucket interaction
 - dependendencies:
   - boto3
   - botocore.exceptions
   - AWS credentials either in environmental variables or ~/.aws/credentials and ~/.aws/config files.

2. **jsontohtml.py**
-functions:
 - parses JSON from DeepGram to format transcript with speaker diarization 
 - invokes ChatGPT to deduce actual speaker names from context and hint files
 - uploads transcript and metadata to designated bucket
 - formats final transcript as SmartTranscrpt HTML and puts in public S3 bucket
 - calls ChatGPT to create summary of transcript and puts that in public S3 bucket as well
- implementation in goldendoemvt:
 - the code contains a wrapper so it can be invoked as an AWS lambda function triggred by the arrival of a JSON file in a specified bucket
 - the interface to ChatGPT and the formatting of the HTML file are separated from the lambda function wrapper so that the code can also be used in other contexts
-dependencies:
 - bototools
 - meetingreporter
 - \<committeename>.txt (optional)
 - weekly.pk1 (optional)

3. **meetingreporter.py**
-functions (as used in jsontohtml):
 - parse JSON returned by DeepGram and create draft transcript with embedded speaker IDs
 - call ChatGPT to deduce actual speaker name
 - call ChatGPT to create summary HTML
 - create SmartTranscript HTML
-other functions: contains a medly of routines not used in the production factory such as non-AWS dependent calls to Deepgram and AssemblyAI, downloads for video formats other than youtube, and other rouines (some deprecated) you may find useful
-implementation in goldendomevt: packaged with jsontohtml lambda function for purposes above
-dependencies:
 - OpenAI API key assumed to be available as os.environ.get('DEEPGRAM_API_KEY') or .env.
 - pydantic (must be the right version for the execution platform)
 - openai

4. **mylogger.py**
- function: Sets up logging configuration to output JSON-formatted logs in Google Cloud format
    to both the console and separate disk files for syslog and syserr, with default paths
    based on the operating system. If no log files are specified on a Linux instance,
    logs are sent directly to Google Cloud Logging.
-implementation in goldendomevt: used by youtubetos3 to log activity

5. **s3deepgrams3.py**
- function: invokes DeepGram API to upload audio file from and S3 bucket to DG for transcription and have DeepGram put the resulting JSON back in the same S3 bucket using a presigned URL.
- implementation in goldendoemvt:
 - the code contains a wrapper so it can be invoked as an AWS lambda function triggered by the arrival of an audio file in a specified bucket
 - the interface to DG is separated from the lambda function wrapper so that the code can also be used in other contexts
- limitations:
  - the interface to DeepGram is specific to S3 buckets.
  - only handles .wav,.mp4,.webm, and .m4a file types
  - needs requisite permissions when operating on AWS
-dependencies:
  - DeepGram API key assumed to be available as os.environ.get('DEEPGRAM_API_KEY'). Supplied to AWS in my.env as part of building the lambda function.
  - boto3
  - botocore.exceptions
  - deepgram
   
6. **youtubeapi.py**
- function: interface to googleapiclent routines for YouTube information access
- implementation in goldendomevt:
  - used by youytubetos3 to retrieve list of videos for channel and info about videos.
  - used by utilities to get youtube statistics and to map channle handles to channel ids.
- limitations:
  - assumes all times are Esatern US timezone
  - subject to YouTube limits of API requets per day per API key
- dependencies:
  - API key (from Google). Assumed to be in .env as YOUTUBE_API_KEY.
  - googleapiclient.discovery
  - pytz
  - zoneinfo
  - dotenv 
    
7. **youtubetos3.py**
 - function: run periodically to scan for new videos posted on the list of YouTube channels in committees.pk1. Downloads audio only. Uses its access to s3 buckets to see if a video is actually new and uploads both the resulting audio file and metadata as well as WIP information to S3 buckets.
 - implementation in goldendomevt: runs as a cron job on a google debian server instance although can run on locally on Windows, Mac, or Linux.
 - limitations: assumes that there is only one playlist per channel so needs to be extended in environments where mutliple playlists are used. 
 - dependedencies:
   - committees.pk1
   - bototools.py
   - mylogger.py
   - youtubeapi.com
   - yt_dlp
   - ffmpeg
## Web Objects ##
These all must be in the Disply Bucket - the public bucket from which the index page, SmartTranscript pages, amd meeting summaries are served. All of these are customized to GoldenDome to some extent.

1. **about.html** an optional about for both the index page and SmartTranscripts.
2. **dome_closed.png** icon for a closed folder on index page. Should be an svg instead.
3. **dome_open.png** icon for an open folder on index page. Should be an svg instead.
4. **favicon.ico**
5. **footer.html** optional html and javascript to create a footer for both index page and SmartTranscripts.
6. **footer_loader_script.js** optional code to load the footer for both index and SmartTranscripts.
7. **index.html** index page for the GoldenDome application Reads the directory of the bucket it is loaded from to create a visible hierarchy of available SmartTrancripts of meetings, provides a place to display a summary of a chosen meeting, and displays a Google search function. Links to SmartTrancripts.
8. **search_dropdown_styles.css** style sheet for dropdown menus and objects they create dynamically.
9. **searchbox.png** graphic for searchbox.
10. **smart_trancript.css** style sheet for SmartTrancripts
11. **standardVideo.js** implemntation of SmartTrancript functionality. Controls the video player based on selections in transcript.
12. **statehouse.png** drawing of the Vernmont Staehouse used as background for the index page.
13. **youtubePlayer.js** maps standard video player API to YouTube video player API so that standardVideo.js can function with a yt viewer. 
## Samples

1. **committees.pk1**
- pickle of a dictionary where the keys are committee handles and the values are the YouTube IDs of the channels which correspond to the committee. Input to youtubetos3.py. These were scraped from the Vermont legislative directory. Use for other jurisdictions requires building your own dictionary in the same format.
2. **weekly.pk1**
- pickle of an optional dictionary used as context for ChatGPT called from json2html lambda function when assigning names to speakers in a trancript. If ppresent must bin the bucket which json transcripts are retireved from. GoldenDome specific and scraped from Vermont Legislature website but format could be used by other implementations, Major key is committee name. Dictionary under that has key "assistants", whose value is a list of committee assisatnts and their titles, and "speakers" which is list of subdictionaries. Each of these subdictionaries has a key "date", whose value is a date in the form YYYY-MM-DD, and a key "speakers", whose value is a list of speaker names and titles.
3. /<committeename>.txt
  - optional text files for each committee. If present must be in the public display bucket. They are used both as context for ChatGPT called from json2html lambda function when assigning names to speakers and by SmartTranscript web pages to support the "email to committee" option. There is one line for each committee member which contains comma-separeted member name, role on committee, part affiliation, district, and email address.These were scraped from the Vermont legislative directory. Use for other jurisdictions requires building your own files in the same format.


