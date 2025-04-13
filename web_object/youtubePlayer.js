// videoplay.js

function VideoPlay(videoId, containerId) {
    this.videoId = videoId;
    this.containerId = containerId;  // The container where the iframe will be injected
    this.player = null;
    this._currentTime = 0;  // Internal property to store current time
    this.paused = true;
    this.duration = 0;
    this.volume = 1;
    this.eventListeners = {}; // Store event listeners

    // If the YouTube IFrame API is already loaded, initialize the player
    if (typeof YT !== 'undefined' && YT.Player) {
        this.initPlayer();
    } else {
        // Load the YouTube IFrame API if not already loaded
        this.loadYouTubeAPI();
    }
}

VideoPlay.prototype.loadYouTubeAPI = function() {
    var self = this;
    var tag = document.createElement('script');
    tag.src = "https://www.youtube.com/iframe_api";
    var firstScriptTag = document.getElementsByTagName('script')[0];
    firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);

    window.onYouTubeIframeAPIReady = function() {
        self.initPlayer();
    };
};

VideoPlay.prototype.initPlayer = function() {
    var self = this;

    // Create the iframe dynamically inside the specified container
    var container = document.getElementById(this.containerId);
    var iframe = document.createElement('div'); // A <div> placeholder where the iframe will be rendered
    container.appendChild(iframe);

    this.player = new YT.Player(iframe, {
        videoId: this.videoId,
		playerVars: {
            'autoplay': 0,
            'controls': 0,
            'rel': 0,  // Prevents showing related videos at the end
            'modestbranding': 1,  // Reduces YouTube branding
            'enablejsapi': 1,
            'iv_load_policy': 3,  // Hides video annotations
            'playsinline': 1,  // Ensures video plays inline on mobile
            'disablekb': 1,  // Disables keyboard controls
            'cc_load_policy': 0,  // Hides closed captions
            'autohide': 1  // Hides controls when playing
        },
        events: {
            'onReady': function(event) { self.onPlayerReady(event); },
            'onStateChange': function(event) { self.onPlayerStateChange(event); }
        }
    });
	this.addOverlay(); // Add overlay after initializing the player
};


VideoPlay.prototype.addOverlay = function() {
    var container = document.getElementById(this.containerId);
    if (!container) return;

    var overlay = document.createElement('div');
    overlay.id = this.containerId + "-overlay";
    overlay.style.position = "absolute";
    overlay.style.top = "0";
    overlay.style.left = "0";
    overlay.style.width = "100%";
    overlay.style.height = "100%";
    overlay.style.background = "rgba(0, 0, 0, 0.25)";
    overlay.style.zIndex = "10";

    overlay.addEventListener("click", function(event) {
        event.stopPropagation(); // Prevent clicks from reaching the iframe
		if (typeof playClipButton === 'undefined') {
			alert("Please control the video player with the blue tabs above.");
		} else {
			playClipButton.click();
		}
    });

    container.style.position = "relative";
    container.appendChild(overlay);
};

VideoPlay.prototype.removeOverlay = function() {
    var overlay = document.getElementById(this.containerId + "-overlay");
    if (overlay) {
        overlay.remove();
    }
};

VideoPlay.prototype.onPlayerReady = function(event) {
    this.duration = this.player.getDuration();
    this.triggerEvent('ready');
};

VideoPlay.prototype.onPlayerStateChange = function(event) {
    switch (event.data) {
        case YT.PlayerState.PLAYING:
			this.removeOverlay();
            this.paused = false;
            this.triggerEvent('play');
            this.updateTime();
            break;
        case YT.PlayerState.PAUSED:
            this.paused = true;
            this.triggerEvent('pause');
            break;
        case YT.PlayerState.ENDED:
            this.triggerEvent('ended');
            break;
    }
};

VideoPlay.prototype.updateTime = function() {
    var self = this;
    if (!this.paused) {
        this._currentTime = this.player.getCurrentTime();
        setTimeout(function() { self.updateTime(); }, 250);
    }
};

// Getter and Setter for currentTime
Object.defineProperty(VideoPlay.prototype, 'currentTime', {
    get: function() {
        return this.player.getCurrentTime();
    },
    set: function(seconds) {
        // Update the seek time, but don't seek immediately
        this._seekTime = seconds;
    }
});


// Implement addEventListener like in HTML5 video players
VideoPlay.prototype.addEventListener = function(eventName, callback) {
    if (!this.eventListeners[eventName]) {
        this.eventListeners[eventName] = [];
    }
    this.eventListeners[eventName].push(callback);
};

// Trigger events manually
VideoPlay.prototype.triggerEvent = function(eventName) {
    if (this.eventListeners[eventName]) {
        this.eventListeners[eventName].forEach(function(callback) {
            callback();
        });
    }
};

// Implement the play method to perform the seek if needed
VideoPlay.prototype.play = function() {
    if (this.player) {
        // Always seek to the stored _seekTime before playing
        this.player.seekTo(this._seekTime, true);
        this.player.playVideo();
        this.triggerEvent('seeked');  // Trigger seeked event after seeking
    }
};

VideoPlay.prototype.pause = function() {
    if (this.player) {
        this.player.pauseVideo();
    }
};

VideoPlay.prototype.seek = function(seconds) {
    this.currentTime = seconds;
};

VideoPlay.prototype.setVolume = function(volume) {
    this.volume = volume;
    if (this.player) {
        this.player.setVolume(volume * 100);
    }
};

VideoPlay.prototype.getCurrentTime = function() {
    return this.currentTime;
};

VideoPlay.prototype.getDuration = function() {
    return this.player ? this.player.getDuration() : this.duration;
};

VideoPlay.prototype.isPaused = function() {
    return this.paused;
};
VideoPlay.prototype.updateTime = function() {
    var self = this;
    if (!this.paused) {
        this._currentTime = this.player.getCurrentTime();
        this.triggerEvent('timeupdate');  // Custom timeupdate event

        // Continue updating every second
        setTimeout(function() { self.updateTime(); }, 250);
    }
};

