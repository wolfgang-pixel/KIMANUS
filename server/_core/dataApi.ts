/**
 * YouTube Data API Wrapper
 * Uses YouTube Data API v3 for search and channel details
 */

const YOUTUBE_API_KEY = process.env.YOUTUBE_API_KEY;
const YOUTUBE_API_BASE = 'https://www.googleapis.com/youtube/v3';

export interface YouTubeVideo {
  videoId: string;
  title: string;
  description: string;
  channelId: string;
  channelTitle: string;
  publishedAt: string;
  thumbnailUrl: string;
  duration?: number;
  viewCount?: number;
}

export interface YouTubeChannel {
  id: string;
  title: string;
  description: string;
  country?: string;
  subscriberCount?: number;
  videoCount?: number;
  thumbnailUrl?: string;
}

export interface SearchOptions {
  query: string;
  maxResults?: number;
  regionCode?: string;
  relevanceLanguage?: string;
  order?: 'relevance' | 'date' | 'viewCount' | 'rating';
  videoDuration?: 'short' | 'medium' | 'long';
}

/**
 * Search YouTube videos
 */
export async function searchYouTube(options: SearchOptions): Promise<YouTubeVideo[]> {
  const {
    query,
    maxResults = 10,
    regionCode = 'DE',
    relevanceLanguage = 'de',
    order = 'relevance',
    videoDuration = 'medium',
  } = options;

  if (!YOUTUBE_API_KEY) {
    throw new Error('YOUTUBE_API_KEY nicht konfiguriert');
  }

  const params = new URLSearchParams({
    part: 'snippet',
    q: query,
    type: 'video',
    maxResults: String(maxResults),
    regionCode,
    relevanceLanguage,
    order,
    videoDuration,
    key: YOUTUBE_API_KEY,
    videoEmbeddable: 'true',
  });

  const searchUrl = `${YOUTUBE_API_BASE}/search?${params}`;

  try {
    const response = await fetch(searchUrl);

    if (!response.ok) {
      const error = await response.json();
      throw new Error(`YouTube API Error: ${error.error?.message || response.statusText}`);
    }

    const data = await response.json();
    const videoIds = data.items?.map((item: any) => item.id.videoId).join(',') || '';

    // Get video details (duration, view count)
    const videos: YouTubeVideo[] = [];

    if (videoIds) {
      const detailsParams = new URLSearchParams({
        part: 'snippet,contentDetails,statistics',
        id: videoIds,
        key: YOUTUBE_API_KEY,
      });

      const detailsUrl = `${YOUTUBE_API_BASE}/videos?${detailsParams}`;
      const detailsResponse = await fetch(detailsUrl);

      if (detailsResponse.ok) {
        const detailsData = await detailsResponse.json();

        for (const item of detailsData.items || []) {
          videos.push({
            videoId: item.id,
            title: item.snippet.title,
            description: item.snippet.description,
            channelId: item.snippet.channelId,
            channelTitle: item.snippet.channelTitle,
            publishedAt: item.snippet.publishedAt,
            thumbnailUrl: item.snippet.thumbnails?.high?.url || item.snippet.thumbnails?.default?.url,
            duration: parseDuration(item.contentDetails?.duration),
            viewCount: parseInt(item.statistics?.viewCount || '0', 10),
          });
        }
      }
    }

    return videos;
  } catch (error) {
    console.error('YouTube Search Error:', error);
    throw error;
  }
}

/**
 * Get channel details
 */
export async function getChannelDetails(channelId: string): Promise<YouTubeChannel | null> {
  if (!YOUTUBE_API_KEY) {
    throw new Error('YOUTUBE_API_KEY nicht konfiguriert');
  }

  const params = new URLSearchParams({
    part: 'snippet,statistics,brandingSettings',
    id: channelId,
    key: YOUTUBE_API_KEY,
  });

  const url = `${YOUTUBE_API_BASE}/channels?${params}`;

  try {
    const response = await fetch(url);

    if (!response.ok) {
      return null;
    }

    const data = await response.json();
    const channel = data.items?.[0];

    if (!channel) {
      return null;
    }

    return {
      id: channel.id,
      title: channel.snippet.title,
      description: channel.snippet.description,
      country: channel.snippet.country || channel.brandingSettings?.channel?.country,
      subscriberCount: parseInt(channel.statistics?.subscriberCount || '0', 10),
      videoCount: parseInt(channel.statistics?.videoCount || '0', 10),
      thumbnailUrl: channel.snippet.thumbnails?.default?.url,
    };
  } catch (error) {
    console.error('Channel Details Error:', error);
    return null;
  }
}

/**
 * Get multiple channel details at once
 */
export async function getChannelsDetails(channelIds: string[]): Promise<Map<string, YouTubeChannel>> {
  if (!YOUTUBE_API_KEY || channelIds.length === 0) {
    return new Map();
  }

  const params = new URLSearchParams({
    part: 'snippet,statistics,brandingSettings',
    id: channelIds.join(','),
    key: YOUTUBE_API_KEY,
  });

  const url = `${YOUTUBE_API_BASE}/channels?${params}`;

  try {
    const response = await fetch(url);

    if (!response.ok) {
      return new Map();
    }

    const data = await response.json();
    const channels = new Map<string, YouTubeChannel>();

    for (const channel of data.items || []) {
      channels.set(channel.id, {
        id: channel.id,
        title: channel.snippet.title,
        description: channel.snippet.description,
        country: channel.snippet.country || channel.brandingSettings?.channel?.country,
        subscriberCount: parseInt(channel.statistics?.subscriberCount || '0', 10),
        videoCount: parseInt(channel.statistics?.videoCount || '0', 10),
        thumbnailUrl: channel.snippet.thumbnails?.default?.url,
      });
    }

    return channels;
  } catch (error) {
    console.error('Channels Details Error:', error);
    return new Map();
  }
}

/**
 * Parse ISO 8601 duration to seconds
 * e.g., "PT1H2M30S" -> 3750
 */
function parseDuration(duration: string | undefined): number {
  if (!duration) return 0;

  const match = duration.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/);
  if (!match) return 0;

  const hours = parseInt(match[1] || '0', 10);
  const minutes = parseInt(match[2] || '0', 10);
  const seconds = parseInt(match[3] || '0', 10);

  return hours * 3600 + minutes * 60 + seconds;
}

/**
 * Check if a video title is likely in English
 */
export function isLikelyEnglishTitle(title: string): boolean {
  const englishPatterns = [
    /\b(how to|what is|why|build|create|tutorial|guide|tips|tricks|best|top|review|explained|introduction|basics|advanced|complete|full|ultimate)\b/i,
    /\b(the|and|or|for|with|from|this|that|these|those|here|there|where|when|which|who|whom|whose)\b/i,
  ];

  // Check if multiple English patterns match
  let englishMatches = 0;
  for (const pattern of englishPatterns) {
    if (pattern.test(title)) {
      englishMatches++;
    }
  }

  return englishMatches >= 2;
}

/**
 * Check if a video title has German words
 */
export function hasGermanWords(title: string): boolean {
  const germanPatterns = /\b(und|oder|mit|für|wie|was|wer|wann|wo|warum|Tutorial|Anleitung|Erklärung|Tipps|lernen|einfach|schnell|beste|komplett|deutsch|german)\b/i;
  return germanPatterns.test(title);
}

/**
 * Check if channel is from DACH region (Germany, Austria, Switzerland)
 */
export function isDACHChannel(country: string | undefined): boolean {
  if (!country) return false;
  return ['DE', 'AT', 'CH'].includes(country.toUpperCase());
}
