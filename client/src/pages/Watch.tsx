import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { trpc } from '@/lib/trpc';
import { cn, formatDuration, formatViewCount, formatRelativeTime } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Slider } from '@/components/ui/slider';
import {
  Play,
  Pause,
  SkipForward,
  SkipBack,
  Repeat,
  Volume2,
  VolumeX,
  Loader2,
  ArrowLeft,
  Search,
  Filter,
  Globe,
  Tv,
  Clock,
  Eye,
  ThumbsUp,
} from 'lucide-react';

// YouTube Player Types
declare global {
  interface Window {
    YT: {
      Player: new (
        element: HTMLElement | string,
        config: {
          videoId: string;
          playerVars?: Record<string, number | string>;
          events?: {
            onReady?: (event: { target: YTPlayer }) => void;
            onStateChange?: (event: { data: number; target: YTPlayer }) => void;
            onError?: (event: { data: number }) => void;
          };
        }
      ) => YTPlayer;
      PlayerState: {
        ENDED: number;
        PLAYING: number;
        PAUSED: number;
        BUFFERING: number;
        CUED: number;
      };
    };
    onYouTubeIframeAPIReady: () => void;
  }
}

interface YTPlayer {
  playVideo: () => void;
  pauseVideo: () => void;
  seekTo: (seconds: number, allowSeekAhead: boolean) => void;
  getCurrentTime: () => number;
  getDuration: () => number;
  getVolume: () => number;
  setVolume: (volume: number) => void;
  mute: () => void;
  unMute: () => void;
  isMuted: () => boolean;
  destroy: () => void;
}

// Video segment from API
interface VideoSegment {
  videoId: string;
  title: string;
  description: string;
  channelId: string;
  channelTitle: string;
  thumbnailUrl: string;
  publishedAt: string;
  duration: number;
  viewCount: number;
  timestamp: number;
  segmentDuration: number;
  timestampReasoning: string;
  qualityScore: number;
  isGerman: boolean;
  channelCountry?: string;
}

// Conversation steps
type ConversationStep = 'topic' | 'question' | 'loading' | 'preview' | 'watching';

export default function Watch() {
  const navigate = useNavigate();

  // Conversation state
  const [step, setStep] = useState<ConversationStep>('topic');
  const [topic, setTopic] = useState('');
  const [specificQuestion, setSpecificQuestion] = useState('');

  // Video state
  const [videos, setVideos] = useState<VideoSegment[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');

  // Filter state
  const [filterGerman, setFilterGerman] = useState<boolean | null>(null);

  // Player state
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [volume, setVolume] = useState(100);
  const [currentTime, setCurrentTime] = useState(0);
  const [autoAdvance, setAutoAdvance] = useState(true);
  const [loopMode, setLoopMode] = useState(false);

  // Refs
  const playerRef = useRef<YTPlayer | null>(null);
  const playerContainerRef = useRef<HTMLDivElement>(null);
  const timeUpdateInterval = useRef<NodeJS.Timeout | null>(null);
  const ytReadyRef = useRef(false);

  // tRPC mutation
  const searchMutation = trpc.kimtv.searchVideos.useMutation({
    onSuccess: (data) => {
      setVideos(data.videos);
      setSearchQuery(data.query);
      setStep('preview');
    },
    onError: (error) => {
      console.error('Search error:', error);
      setStep('topic');
    },
  });

  // Filter videos based on language selection
  const filteredVideos = videos.filter((video) => {
    if (filterGerman === null) return true;
    return filterGerman ? video.isGerman : !video.isGerman;
  });

  // Current video
  const currentVideo = filteredVideos[currentIndex];

  // Load YouTube IFrame API
  useEffect(() => {
    if (window.YT) {
      ytReadyRef.current = true;
      return;
    }

    const tag = document.createElement('script');
    tag.src = 'https://www.youtube.com/iframe_api';
    const firstScriptTag = document.getElementsByTagName('script')[0];
    firstScriptTag.parentNode?.insertBefore(tag, firstScriptTag);

    window.onYouTubeIframeAPIReady = () => {
      ytReadyRef.current = true;
    };
  }, []);

  // Initialize player when watching
  const initPlayer = useCallback(() => {
    if (!ytReadyRef.current || !playerContainerRef.current || !currentVideo) {
      return;
    }

    // Destroy existing player
    if (playerRef.current) {
      playerRef.current.destroy();
      playerRef.current = null;
    }

    // Clear the container
    playerContainerRef.current.innerHTML = '';

    // Create player element
    const playerElement = document.createElement('div');
    playerElement.id = 'yt-player';
    playerContainerRef.current.appendChild(playerElement);

    // Initialize new player
    playerRef.current = new window.YT.Player('yt-player', {
      videoId: currentVideo.videoId,
      playerVars: {
        autoplay: 1,
        controls: 1,
        modestbranding: 1,
        rel: 0,
        start: Math.floor(currentVideo.timestamp),
      },
      events: {
        onReady: (event) => {
          // Seek to timestamp
          event.target.seekTo(Math.floor(currentVideo.timestamp), true);
          event.target.playVideo();
          setIsPlaying(true);

          // Set volume
          event.target.setVolume(volume);
          if (isMuted) {
            event.target.mute();
          }
        },
        onStateChange: (event) => {
          if (event.data === window.YT.PlayerState.ENDED) {
            handleVideoEnd();
          } else if (event.data === window.YT.PlayerState.PLAYING) {
            setIsPlaying(true);
          } else if (event.data === window.YT.PlayerState.PAUSED) {
            setIsPlaying(false);
          }
        },
        onError: (event) => {
          console.error('YouTube Player Error:', event.data);
          // Skip to next video on error
          if (autoAdvance) {
            handleVideoEnd();
          }
        },
      },
    });
  }, [currentVideo, volume, isMuted, autoAdvance]);

  // Initialize player when entering watch mode or changing video
  useEffect(() => {
    if (step === 'watching' && currentVideo) {
      // Wait for YouTube API to be ready
      const checkReady = setInterval(() => {
        if (ytReadyRef.current) {
          clearInterval(checkReady);
          initPlayer();
        }
      }, 100);

      return () => clearInterval(checkReady);
    }
  }, [step, currentVideo, initPlayer]);

  // Update current time periodically
  useEffect(() => {
    if (step === 'watching' && isPlaying && playerRef.current) {
      timeUpdateInterval.current = setInterval(() => {
        if (playerRef.current) {
          const time = playerRef.current.getCurrentTime();
          setCurrentTime(time);

          // Check if segment duration exceeded
          if (currentVideo && time > currentVideo.timestamp + currentVideo.segmentDuration) {
            if (autoAdvance) {
              handleVideoEnd();
            }
          }
        }
      }, 1000);
    }

    return () => {
      if (timeUpdateInterval.current) {
        clearInterval(timeUpdateInterval.current);
      }
    };
  }, [step, isPlaying, currentVideo, autoAdvance]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (playerRef.current) {
        playerRef.current.destroy();
      }
    };
  }, []);

  // Handle video end
  const handleVideoEnd = useCallback(() => {
    if (loopMode) {
      // Restart current video
      if (playerRef.current && currentVideo) {
        playerRef.current.seekTo(currentVideo.timestamp, true);
        playerRef.current.playVideo();
      }
    } else if (autoAdvance && currentIndex < filteredVideos.length - 1) {
      // Move to next video
      setCurrentIndex(currentIndex + 1);
    } else {
      // End of playlist
      setIsPlaying(false);
    }
  }, [loopMode, autoAdvance, currentIndex, filteredVideos.length, currentVideo]);

  // Handle topic submission
  const handleTopicSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (topic.trim()) {
      setStep('question');
    }
  };

  // Handle question submission
  const handleQuestionSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setStep('loading');
    searchMutation.mutate({
      topic: topic.trim(),
      specificQuestion: specificQuestion.trim() || undefined,
      preferGerman: true,
      maxResults: 10,
    });
  };

  // Skip question
  const handleSkipQuestion = () => {
    setStep('loading');
    searchMutation.mutate({
      topic: topic.trim(),
      preferGerman: true,
      maxResults: 10,
    });
  };

  // Start watching
  const handleStartWatching = (index = 0) => {
    setCurrentIndex(index);
    setStep('watching');
  };

  // Player controls
  const togglePlay = () => {
    if (playerRef.current) {
      if (isPlaying) {
        playerRef.current.pauseVideo();
      } else {
        playerRef.current.playVideo();
      }
    }
  };

  const toggleMute = () => {
    if (playerRef.current) {
      if (isMuted) {
        playerRef.current.unMute();
        setIsMuted(false);
      } else {
        playerRef.current.mute();
        setIsMuted(true);
      }
    }
  };

  const handleVolumeChange = (value: number[]) => {
    const newVolume = value[0];
    setVolume(newVolume);
    if (playerRef.current) {
      playerRef.current.setVolume(newVolume);
      if (newVolume === 0) {
        playerRef.current.mute();
        setIsMuted(true);
      } else if (isMuted) {
        playerRef.current.unMute();
        setIsMuted(false);
      }
    }
  };

  const handlePrevious = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    }
  };

  const handleNext = () => {
    if (currentIndex < filteredVideos.length - 1) {
      setCurrentIndex(currentIndex + 1);
    }
  };

  // Back to preview
  const handleBackToPreview = () => {
    if (playerRef.current) {
      playerRef.current.destroy();
      playerRef.current = null;
    }
    setStep('preview');
  };

  // Reset to start
  const handleReset = () => {
    if (playerRef.current) {
      playerRef.current.destroy();
      playerRef.current = null;
    }
    setVideos([]);
    setCurrentIndex(0);
    setTopic('');
    setSpecificQuestion('');
    setFilterGerman(null);
    setStep('topic');
  };

  // Render topic input step
  const renderTopicStep = () => (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <Card className="w-full max-w-lg mx-4 bg-black/40 backdrop-blur-lg border-purple-500/30">
        <CardContent className="pt-8 pb-8">
          <div className="text-center mb-8">
            <div className="flex items-center justify-center gap-3 mb-4">
              <Tv className="w-12 h-12 text-purple-400" />
              <h1 className="text-4xl font-bold text-white">Kim TV</h1>
            </div>
            <p className="text-gray-300">Dein KI-gestützter Video-Kanal</p>
          </div>

          <form onSubmit={handleTopicSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-200 mb-2">
                Welches Thema interessiert dich?
              </label>
              <Input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="z.B. Maschinelles Lernen, Kochen, Gitarre lernen..."
                className="bg-white/10 border-white/20 text-white placeholder:text-gray-400"
                autoFocus
              />
            </div>
            <Button
              type="submit"
              disabled={!topic.trim()}
              className="w-full bg-purple-600 hover:bg-purple-700"
            >
              Weiter
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );

  // Render question step
  const renderQuestionStep = () => (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <Card className="w-full max-w-lg mx-4 bg-black/40 backdrop-blur-lg border-purple-500/30">
        <CardContent className="pt-8 pb-8">
          <div className="text-center mb-6">
            <Tv className="w-10 h-10 text-purple-400 mx-auto mb-3" />
            <p className="text-gray-300">Thema: <span className="text-white font-medium">{topic}</span></p>
          </div>

          <form onSubmit={handleQuestionSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-200 mb-2">
                Hast du spezielle Fragen zu diesem Thema? (Optional)
              </label>
              <Input
                value={specificQuestion}
                onChange={(e) => setSpecificQuestion(e.target.value)}
                placeholder="z.B. Wie funktioniert...? Was ist der Unterschied...?"
                className="bg-white/10 border-white/20 text-white placeholder:text-gray-400"
                autoFocus
              />
              <p className="text-xs text-gray-400 mt-2">
                Eine spezifische Frage hilft uns, die relevantesten Abschnitte zu finden.
              </p>
            </div>
            <div className="flex gap-3">
              <Button
                type="button"
                variant="outline"
                onClick={handleSkipQuestion}
                className="flex-1 border-white/20 text-white hover:bg-white/10"
              >
                Überspringen
              </Button>
              <Button
                type="submit"
                className="flex-1 bg-purple-600 hover:bg-purple-700"
              >
                Videos suchen
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );

  // Render loading step
  const renderLoadingStep = () => (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <div className="text-center">
        <Loader2 className="w-16 h-16 text-purple-400 animate-spin mx-auto mb-4" />
        <h2 className="text-xl font-medium text-white mb-2">Suche Videos...</h2>
        <p className="text-gray-400">
          KI analysiert die besten Abschnitte für "{topic}"
        </p>
      </div>
    </div>
  );

  // Render preview step
  const renderPreviewStep = () => (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-4 md:p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <button
            onClick={handleReset}
            className="flex items-center gap-2 text-gray-300 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            Neues Thema
          </button>
          <div className="flex items-center gap-2">
            <Tv className="w-6 h-6 text-purple-400" />
            <span className="font-semibold text-white">Kim TV</span>
          </div>
        </div>

        {/* Topic info */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white mb-2">
            {searchQuery}
          </h1>
          <p className="text-gray-400">
            {videos.length} Videos gefunden
          </p>
        </div>

        {/* Filter buttons */}
        <div className="flex items-center gap-3 mb-6">
          <span className="text-sm text-gray-300 flex items-center gap-2">
            <Filter className="w-4 h-4" />
            Filter:
          </span>
          <Button
            variant={filterGerman === null ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilterGerman(null)}
            className={filterGerman === null ? 'bg-purple-600' : 'border-white/20 text-white'}
          >
            Alle ({videos.length})
          </Button>
          <Button
            variant={filterGerman === true ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilterGerman(true)}
            className={filterGerman === true ? 'bg-green-600' : 'border-white/20 text-white'}
          >
            Deutsch ({videos.filter(v => v.isGerman).length})
          </Button>
          <Button
            variant={filterGerman === false ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilterGerman(false)}
            className={filterGerman === false ? 'bg-blue-600' : 'border-white/20 text-white'}
          >
            Englisch ({videos.filter(v => !v.isGerman).length})
          </Button>
        </div>

        {/* Start button */}
        <Button
          onClick={() => handleStartWatching(0)}
          disabled={filteredVideos.length === 0}
          className="mb-6 bg-purple-600 hover:bg-purple-700"
          size="lg"
        >
          <Play className="w-5 h-5 mr-2" />
          Abspielen ({filteredVideos.length} Videos)
        </Button>

        {/* Video grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredVideos.map((video, index) => (
            <Card
              key={video.videoId}
              className="bg-black/40 border-white/10 overflow-hidden cursor-pointer hover:border-purple-500/50 transition-colors"
              onClick={() => handleStartWatching(index)}
            >
              <div className="relative">
                <img
                  src={video.thumbnailUrl}
                  alt={video.title}
                  className="w-full aspect-video object-cover"
                />
                <div className="absolute bottom-2 right-2 bg-black/80 px-2 py-1 rounded text-xs text-white">
                  {formatDuration(video.duration)}
                </div>
                <div className="absolute top-2 left-2">
                  <Badge variant={video.isGerman ? 'german' : 'english'}>
                    {video.isGerman ? 'DE' : 'EN'}
                  </Badge>
                </div>
              </div>
              <CardContent className="p-4">
                <h3 className="font-medium text-white line-clamp-2 mb-2">
                  {video.title}
                </h3>
                <p className="text-sm text-gray-400 mb-2">{video.channelTitle}</p>
                <div className="flex items-center gap-3 text-xs text-gray-500">
                  <span className="flex items-center gap-1">
                    <Eye className="w-3 h-3" />
                    {formatViewCount(video.viewCount)}
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {formatRelativeTime(video.publishedAt)}
                  </span>
                </div>
                <div className="mt-2 text-xs text-purple-400">
                  Startet bei {formatDuration(video.timestamp)}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );

  // Render watching step
  const renderWatchingStep = () => (
    <div className="min-h-screen bg-black flex flex-col">
      {/* Top bar */}
      <div className="flex items-center justify-between p-4 bg-black/80">
        <button
          onClick={handleBackToPreview}
          className="flex items-center gap-2 text-gray-300 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
          Zurück
        </button>
        <div className="flex items-center gap-2">
          <Tv className="w-5 h-5 text-purple-400" />
          <span className="text-sm text-white font-medium">Kim TV</span>
        </div>
        <div className="text-sm text-gray-400">
          {currentIndex + 1} / {filteredVideos.length}
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col lg:flex-row">
        {/* Video player */}
        <div className="flex-1 flex flex-col">
          <div
            ref={playerContainerRef}
            className="youtube-player-container bg-black"
          />

          {/* Controls */}
          <div className="p-4 bg-slate-900">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handlePrevious}
                  disabled={currentIndex === 0}
                  className="text-white hover:bg-white/10"
                >
                  <SkipBack className="w-5 h-5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={togglePlay}
                  className="text-white hover:bg-white/10"
                >
                  {isPlaying ? (
                    <Pause className="w-5 h-5" />
                  ) : (
                    <Play className="w-5 h-5" />
                  )}
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleNext}
                  disabled={currentIndex === filteredVideos.length - 1}
                  className="text-white hover:bg-white/10"
                >
                  <SkipForward className="w-5 h-5" />
                </Button>
              </div>

              <div className="flex items-center gap-4">
                {/* Volume */}
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={toggleMute}
                    className="text-white hover:bg-white/10"
                  >
                    {isMuted || volume === 0 ? (
                      <VolumeX className="w-5 h-5" />
                    ) : (
                      <Volume2 className="w-5 h-5" />
                    )}
                  </Button>
                  <Slider
                    value={[volume]}
                    onValueChange={handleVolumeChange}
                    max={100}
                    step={1}
                    className="w-24"
                  />
                </div>

                {/* Loop */}
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setLoopMode(!loopMode)}
                    className={cn(
                      'text-white hover:bg-white/10',
                      loopMode && 'text-purple-400'
                    )}
                  >
                    <Repeat className="w-5 h-5" />
                  </Button>
                </div>

                {/* Auto-advance */}
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-400">Auto</span>
                  <Switch
                    checked={autoAdvance}
                    onCheckedChange={setAutoAdvance}
                  />
                </div>
              </div>
            </div>

            {/* Current video info */}
            {currentVideo && (
              <div>
                <h2 className="text-lg font-medium text-white mb-1">
                  {currentVideo.title}
                </h2>
                <p className="text-sm text-gray-400">
                  {currentVideo.channelTitle}
                </p>
                <p className="text-xs text-purple-400 mt-1">
                  {currentVideo.timestampReasoning}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Playlist sidebar */}
        <div className="w-full lg:w-80 bg-slate-900 border-l border-white/10">
          <div className="p-4 border-b border-white/10">
            <h3 className="font-medium text-white">Playlist</h3>
            <p className="text-sm text-gray-400">
              {filteredVideos.length} Videos
            </p>
          </div>
          <ScrollArea className="h-[400px] lg:h-[calc(100vh-200px)]">
            <div className="p-2">
              {filteredVideos.map((video, index) => (
                <button
                  key={video.videoId}
                  onClick={() => setCurrentIndex(index)}
                  className={cn(
                    'w-full flex items-start gap-3 p-2 rounded-lg text-left transition-colors',
                    index === currentIndex
                      ? 'bg-purple-600/30'
                      : 'hover:bg-white/5'
                  )}
                >
                  <div className="relative flex-shrink-0">
                    <img
                      src={video.thumbnailUrl}
                      alt=""
                      className="w-24 h-14 object-cover rounded"
                    />
                    <div className="absolute bottom-1 right-1 bg-black/80 px-1 text-[10px] text-white rounded">
                      {formatDuration(video.duration)}
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white line-clamp-2">
                      {video.title}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {video.channelTitle}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          </ScrollArea>
        </div>
      </div>
    </div>
  );

  // Render based on step
  switch (step) {
    case 'topic':
      return renderTopicStep();
    case 'question':
      return renderQuestionStep();
    case 'loading':
      return renderLoadingStep();
    case 'preview':
      return renderPreviewStep();
    case 'watching':
      return renderWatchingStep();
    default:
      return renderTopicStep();
  }
}
