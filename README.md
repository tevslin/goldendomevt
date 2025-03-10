# GoldenDomeVT

## WIP

will soon contain the code which implements GoldenDomeVT.com and SmartTranscripts.

This repository is particular to the site GoldenDomeVT.com, which is a factory for creating and serving SmartTranscripts of committee and floor meetings of the Vermont Legislature.SmartTrancripts are text transcripts linked to actual videos in such a way that a user can select text and immediately play the corresponding video clip in an imbedded viewer appropriate to the video type. Much of the code is general and can be used to create SmartTrancripts from a variety of online video sources but some of it uses specific S3 Buckets and URLs whose names are hardcoded as defaults. These need to be replaced with folders or your own s3 buckets to run the code for other sites. It ruins off a list of YouTube channels used by the Vermont Legislature so, at least, needs a different channel list for meetings of other entities and uses a number of other files created from the webpages of the Vermont Legislature.
## The Factory
The factory currently runs partly on a Google debian instance and partly on AWS. Storage for the factory is S3 buckets. The part which runs on Google would run on any Linux system. the only real Linux dependency is the cron job. Absent that the code would run whereever Python is supported. Similarly the code which runs on AWS is dependent for triggering on S3 bucket events but, other than the triggering dependency, can be called in any Python environment.

![The Factory](/assets/factory.png)

## BOM
1. **youtubetos3.py**
 - function: run periodically to scan for new videos posted on the list of YouTube channels in committees.pk1. Downloads audio only. Uses its access to s3 buckets to see if a video is actually new and uplaods both the resulting audio file and metadata as well as WIP information to S3 buckets.
 - implementation in goldendomevt: runs as a cron job on a google debian server instance although can run on locally on Windows, Mac, or Linux. 
 - dependedencies:
   - committees.pk1
   - bototools.py
   - mylogger.py
   - youtubeapi.com
   - yt_dlp
   - ffmpeg

2. **bototools3.py**
 - function: tools for working with s3 buckets
 - implementation in goldendomevt: used in youtubetos3.py as well as the lambda routines s3deepgrams3.py and jsontohtml.py for all bucket interaction
 - dependendencies:
   - boto3
   - botocore.exceptions
   - AWS credentials either in environmental variables or ~/.aws/credentials and ~/.aws/config files.




