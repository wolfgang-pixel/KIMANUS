import { z } from 'zod';
import { router, publicProcedure, protectedProcedure } from './trpc';
import {
  searchYouTube,
  getChannelsDetails,
  isLikelyEnglishTitle,
  hasGermanWords,
  isDACHChannel,
  type YouTubeVideo,
} from './_core/dataApi';
import { analyzeVideoForTimestamp } from './_core/llm';

/**
 * Video segment with timestamp information
 */
export interface VideoSegment {
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

/**
 * Calculate quality score for a video
 */
function calculateQualityScore(options: {
  video: YouTubeVideo;
  isGermanChannel: boolean;
  isGermanTitle: boolean;
  isEnglishTitle: boolean;
}): number {
  const { video, isGermanChannel, isGermanTitle, isEnglishTitle } = options;

  let score = 0;

  // Language scoring (German priority)
  if (isGermanChannel) {
    score += 50; // Strong bonus for DACH channels
  }
  if (isGermanTitle) {
    score += 30; // Bonus for German words in title
  }
  if (isEnglishTitle && !isGermanChannel) {
    score -= 40; // Penalty for likely English content
  }

  // View count scoring (logarithmic)
  if (video.viewCount && video.viewCount > 0) {
    const viewScore = Math.log10(video.viewCount) * 5;
    score += Math.min(viewScore, 30); // Cap at 30 points
  }

  // Recency scoring
  const publishedDate = new Date(video.publishedAt);
  const ageInDays = (Date.now() - publishedDate.getTime()) / (1000 * 60 * 60 * 24);

  if (ageInDays < 30) {
    score += 15; // Very recent
  } else if (ageInDays < 180) {
    score += 10; // Recent
  } else if (ageInDays < 365) {
    score += 5; // Within a year
  }
  // Older videos get no bonus

  // Duration scoring (prefer medium-length videos)
  if (video.duration) {
    if (video.duration >= 300 && video.duration <= 1200) {
      score += 10; // 5-20 minutes is ideal
    } else if (video.duration >= 180 && video.duration <= 1800) {
      score += 5; // 3-30 minutes is okay
    }
  }

  return score;
}

/**
 * Kim TV Router - Main video search and curation logic
 */
const kimtvRouter = router({
  /**
   * Search for videos based on topic
   */
  searchVideos: publicProcedure
    .input(
      z.object({
        topic: z.string().min(1, 'Bitte gib ein Thema ein'),
        specificQuestion: z.string().optional(),
        preferGerman: z.boolean().default(true),
        maxResults: z.number().min(1).max(20).default(5),
      })
    )
    .mutation(async ({ input }) => {
      const { topic, specificQuestion, preferGerman, maxResults } = input;

      // Build search query
      const searchQuery = specificQuestion
        ? `${topic} ${specificQuestion}`
        : topic;

      console.log(`[Kim TV] Searching for: "${searchQuery}"`);

      // STEP 1: Search for German videos
      const germanVideos = await searchYouTube({
        query: `${searchQuery} deutsch`,
        maxResults: maxResults * 2,
        regionCode: 'DE',
        relevanceLanguage: 'de',
      });

      console.log(`[Kim TV] Found ${germanVideos.length} German search results`);

      // STEP 2: Search for international videos (as fallback)
      let internationalVideos: YouTubeVideo[] = [];
      if (!preferGerman || germanVideos.length < maxResults) {
        internationalVideos = await searchYouTube({
          query: searchQuery,
          maxResults: maxResults,
          regionCode: 'US',
          relevanceLanguage: 'en',
        });
        console.log(`[Kim TV] Found ${internationalVideos.length} international results`);
      }

      // Combine and deduplicate
      const allVideos = [...germanVideos];
      for (const video of internationalVideos) {
        if (!allVideos.find((v) => v.videoId === video.videoId)) {
          allVideos.push(video);
        }
      }

      if (allVideos.length === 0) {
        throw new Error('Keine Videos gefunden. Bitte versuche ein anderes Thema.');
      }

      // STEP 3: Get channel details for language detection
      const channelIds = [...new Set(allVideos.map((v) => v.channelId))];
      const channelsMap = await getChannelsDetails(channelIds);

      console.log(`[Kim TV] Fetched details for ${channelsMap.size} channels`);

      // STEP 4: Score and filter videos
      const scoredVideos: Array<{
        video: YouTubeVideo;
        score: number;
        isGerman: boolean;
        channelCountry?: string;
      }> = [];

      for (const video of allVideos) {
        const channel = channelsMap.get(video.channelId);
        const isGermanChannel = isDACHChannel(channel?.country);
        const isGermanTitle = hasGermanWords(video.title);
        const isEnglishTitle = isLikelyEnglishTitle(video.title);

        const score = calculateQualityScore({
          video,
          isGermanChannel,
          isGermanTitle,
          isEnglishTitle,
        });

        // Determine if content is German
        const isGerman = isGermanChannel || (isGermanTitle && !isEnglishTitle);

        scoredVideos.push({
          video,
          score,
          isGerman,
          channelCountry: channel?.country,
        });
      }

      // Sort by score (highest first)
      scoredVideos.sort((a, b) => b.score - a.score);

      // STEP 5: Select top videos
      const selectedVideos = scoredVideos.slice(0, maxResults);

      console.log(`[Kim TV] Selected ${selectedVideos.length} videos after scoring`);

      // STEP 6: Analyze timestamps with LLM
      const videoSegments: VideoSegment[] = [];

      for (const { video, score, isGerman, channelCountry } of selectedVideos) {
        let timestampResult;

        try {
          timestampResult = await analyzeVideoForTimestamp({
            topic,
            specificQuestion,
            videoTitle: video.title,
            videoDescription: video.description.slice(0, 500),
            videoDuration: video.duration || 300,
          });
        } catch (error) {
          console.error(`[Kim TV] Timestamp analysis failed for ${video.videoId}:`, error);
          timestampResult = {
            timestamp: 30,
            duration: 120,
            reasoning: 'Standard-Auswahl',
          };
        }

        videoSegments.push({
          videoId: video.videoId,
          title: video.title,
          description: video.description,
          channelId: video.channelId,
          channelTitle: video.channelTitle,
          thumbnailUrl: video.thumbnailUrl,
          publishedAt: video.publishedAt,
          duration: video.duration || 0,
          viewCount: video.viewCount || 0,
          timestamp: timestampResult.timestamp,
          segmentDuration: timestampResult.duration,
          timestampReasoning: timestampResult.reasoning,
          qualityScore: score,
          isGerman,
          channelCountry,
        });
      }

      console.log(`[Kim TV] Returning ${videoSegments.length} video segments`);

      return {
        videos: videoSegments,
        query: searchQuery,
        totalFound: allVideos.length,
      };
    }),

  /**
   * Get video details by ID
   */
  getVideoDetails: publicProcedure
    .input(z.object({ videoId: z.string() }))
    .query(async ({ input }) => {
      const videos = await searchYouTube({
        query: input.videoId,
        maxResults: 1,
      });

      if (videos.length === 0) {
        throw new Error('Video nicht gefunden');
      }

      return videos[0];
    }),
});

/**
 * Health check router
 */
const healthRouter = router({
  check: publicProcedure.query(() => {
    return {
      status: 'ok',
      timestamp: new Date().toISOString(),
      version: '1.6.0',
    };
  }),
});

/**
 * Main app router
 */
export const appRouter = router({
  health: healthRouter,
  kimtv: kimtvRouter,
});

export type AppRouter = typeof appRouter;
