
            
            let textContainer = document.getElementById('text-container');
            let timeRangeDisplay = document.getElementById('time-range');
            let fullVideoStartTime = 0;
            let fullVideoEndTime = videoPlayer.duration || Number.MAX_SAFE_INTEGER;
            let isPlayingSelection = false;
            let playClipButton = document.getElementById('play-clip-button');
            let playFullVideoButton = document.getElementById('play-full-video-button');
            let pauseResumeButton = document.getElementById('pause-resume-button');
			let resumeTime=0;
            let startTime = 0;  // Global variable to track the start time of the selected clip
            let endTime = 0;    // Global variable to track the end time of the selected clip
            let isClipPlaying = false;
            //let isPaused = false;
            let hasSelection = false;
            let videoPlaying=false;
			let savedSelection= null;

            
            // Function to update the button states based on the video player status
            function updateButtonStates() {
                if (hasSelection && videoPlayer.paused && !isClipPlaying) {
                    playClipButton.innerText = 'Play Clip';
                    playClipButton.disabled = false;
                } else if (isClipPlaying && videoPlayer.paused) {
                    playClipButton.innerText = 'Replay Clip';
                    playClipButton.disabled = false;
                } else {
                    playClipButton.disabled = true;
                }
    
                playFullVideoButton.disabled = !videoPlayer.paused;
                pauseResumeButton.disabled = !videoPlaying;
                pauseResumeButton.innerText = videoPlayer.paused ? 'Resume' : 'Pause';
				//if (videoPlayer.paused) {				
					//textContainer.classList.remove('no-select'); // Allow text selection
				//} else {
					//textContainer.classList.add('no-select'); // Prevent new selections
					//console.log('no-select added');
				//}
				
            }
                    
            // Reset video to play the whole transcript
            function resetVideoPlayer() {
                videoPlayer.currentTime = fullVideoStartTime;

                timeRangeDisplay.innerText = 'Playing full transcript. Select a portion to play a clip.';
                isPlayingSelection = false;
            }

            //resetVideoPlayer();
            updateButtonStates()
			
			function preventTextSelection(event) {
			  // Prevent any text selection interactions when video is playing
			  if (!videoPlayer.paused) {
				event.preventDefault();
				if (savedSelection) {
					const selection = window.getSelection();
					selection.removeAllRanges(); // Clear existing selection
					selection.addRange(savedSelection); // Restore the saved selection
				}
			  }		
			}
			
			function blockSelection(){
				document.addEventListener('mousedown', preventTextSelection);
				document.addEventListener('mouseup', preventTextSelection);
				document.addEventListener('selectionchange', preventTextSelection);
			}
			
			function allowSelection(){
				document.removeEventListener('mousedown', preventTextSelection);
				document.removeEventListener('mouseup', preventTextSelection);
				document.removeEventListener('selectionchange', preventTextSelection);
			}
        
        // Play Clip Button Click Event
        playClipButton.addEventListener('click', function () {
            if (hasSelection) {
                // Reset to the start of the selected clip
                videoPlayer.currentTime = startTime / 1000;  // Convert milliseconds to seconds if necessary
				blockSelection();
                videoPlayer.play();  // Start playing the clip
                isClipPlaying = true;
                videoPlaying=true;
                playClipButton.disabled = true;
            }
        });

        // Play Full Video Button Click Event
        playFullVideoButton.addEventListener('click', function () {
            isClipPlaying = false;
            videoPlaying=true;
            hasSelection = false;  // Reset selection state
            videoPlayer.currentTime = 0;  // Start from the beginning
            videoPlayer.play();  // Play the full video
            updateButtonStates();
        });

        // Pause/Resume Button Click Event
        pauseResumeButton.addEventListener('click', function () {
            if (videoPlayer.paused) {
				videoPlayer.startTime=resumeTime;
				blockSelection();
                videoPlayer.play();
                //isPaused = false;
            } else {
                videoPlayer.pause();
				allowSelection();
                //isPaused = true;
            }
            updateButtonStates();
        });
		
		videoPlayer.addEventListener('timeupdate', function() {
		// check for time expired
			let curTime=videoPlayer.currentTime;
		    if (videoPlayer.currentTime >= fullVideoEndTime) {
                        videoPlayer.pause();
                        videoPlaying=false;
						isClipPlaying=false;
            }
         });

        // Update buttons on video play
        videoPlayer.addEventListener('play', function () {
            updateButtonStates();
        });

        // Update buttons on video pause
        videoPlayer.addEventListener('pause', function () {
			resumeTime=videoPlayer.currentTime;
            updateButtonStates();
        });

        // Update buttons on video end
        videoPlayer.addEventListener('ended', function () {
            isClipPlaying = false;
            updateButtonStates();
        });
                                   
        document.getElementById('text-container').addEventListener('mouseup', function() {
			//if (textContainer.classList.contains('disabled')) { //don't process when not supposed to selectable
			if (!videoPlayer.paused) {
				event.preventDefault(); // Prevent further processing of the event
				return;
			}
            let selection = window.getSelection();
            let firstWord = null;
            let lastWord = null;

            if ( selection.rangeCount > 0 )  {
                       
                let range = selection.getRangeAt(0);
                let rangeStart = range.startOffset;
                let rangeEnd = range.endOffset;
                if ( rangeEnd > rangeStart ) {
                    let rows = document.querySelectorAll(`#word-timings tr`);
                    for (let i = 0; i < rows.length; i++) {
                        let cells = rows[i].getElementsByTagName('td');
                        let wordStart = parseInt(cells[0].textContent);
                        let wordEnd = rows[i + 1] ? parseInt(rows[i + 1].getElementsByTagName('td')[0].textContent) : Infinity;
                        if ( rangeStart>= wordStart && rangeStart < wordEnd) {
                            startTime = parseInt(cells[1].textContent);
                            range.setStart(range.startContainer, wordStart);
                            firstWord=i;
                        }
                        if ( rangeEnd> wordStart && rangeEnd <= wordEnd) {            
                            endTime = parseInt(cells[2].textContent);
                            range.setEnd(range.endContainer, wordEnd);
                            lastWord=i;
                            break;
                        }
                    }
                    // Clear and re-apply the extended selection
                    selection.removeAllRanges();
                    selection.addRange(range);
					savedSelection=range
                }
                   
            }
            if (firstWord==null | lastWord==null){
                timeRangeDisplay.innerText = 'Selected time range: None';
                //resetVideoPlayer();                
				hasSelection=false;
                updateButtonStates();
            } else {
                 videoPlayer.currentTime = startTime/1000;
                 fullVideoEndTime = endTime/1000;
                 hasSelection=true;
                 isClipPlaying=false;
                 updateButtonStates();
                 
                 //timeRangeDisplay.innerText = 'Play selection or unselect to play the whole video.';
                 //isPlayingSelection = true
                 timeRangeDisplay.innerText = 'Selected time range: ' + startTime/1000 + ' to ' + endTime/1000+', sentence: '+firstWord+' to '+ lastWord;
                 
            }                                                
        })

   
        
    