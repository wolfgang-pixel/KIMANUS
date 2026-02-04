import {
  mysqlTable,
  varchar,
  int,
  text,
  boolean,
  timestamp,
  json,
  primaryKey,
} from 'drizzle-orm/mysql-core';

/**
 * Users table - for Manus OAuth integration
 */
export const users = mysqlTable('users', {
  id: varchar('id', { length: 36 }).primaryKey(),
  email: varchar('email', { length: 255 }).notNull().unique(),
  name: varchar('name', { length: 255 }),
  avatarUrl: varchar('avatar_url', { length: 500 }),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().onUpdateNow().notNull(),
});

/**
 * Search history - tracks user searches
 */
export const searchHistory = mysqlTable('search_history', {
  id: int('id').primaryKey().autoincrement(),
  userId: varchar('user_id', { length: 36 }).references(() => users.id),
  topic: varchar('topic', { length: 500 }).notNull(),
  specificQuestion: text('specific_question'),
  videoCount: int('video_count').notNull().default(0),
  createdAt: timestamp('created_at').defaultNow().notNull(),
});

/**
 * Saved playlists - user-created playlists
 */
export const playlists = mysqlTable('playlists', {
  id: int('id').primaryKey().autoincrement(),
  userId: varchar('user_id', { length: 36 }).references(() => users.id).notNull(),
  name: varchar('name', { length: 255 }).notNull(),
  description: text('description'),
  isPublic: boolean('is_public').notNull().default(false),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().onUpdateNow().notNull(),
});

/**
 * Playlist items - videos in a playlist
 */
export const playlistItems = mysqlTable('playlist_items', {
  id: int('id').primaryKey().autoincrement(),
  playlistId: int('playlist_id').references(() => playlists.id).notNull(),
  videoId: varchar('video_id', { length: 20 }).notNull(),
  title: varchar('title', { length: 500 }).notNull(),
  channelTitle: varchar('channel_title', { length: 255 }).notNull(),
  thumbnailUrl: varchar('thumbnail_url', { length: 500 }),
  duration: int('duration').notNull().default(0),
  timestamp: int('timestamp').notNull().default(0),
  segmentDuration: int('segment_duration').notNull().default(120),
  position: int('position').notNull().default(0),
  createdAt: timestamp('created_at').defaultNow().notNull(),
});

/**
 * Favorite topics - saved topic presets
 */
export const favoriteTopics = mysqlTable('favorite_topics', {
  id: int('id').primaryKey().autoincrement(),
  userId: varchar('user_id', { length: 36 }).references(() => users.id).notNull(),
  topic: varchar('topic', { length: 500 }).notNull(),
  specificQuestion: text('specific_question'),
  createdAt: timestamp('created_at').defaultNow().notNull(),
});

/**
 * Video ratings - user ratings for videos
 */
export const videoRatings = mysqlTable(
  'video_ratings',
  {
    userId: varchar('user_id', { length: 36 }).references(() => users.id).notNull(),
    videoId: varchar('video_id', { length: 20 }).notNull(),
    rating: int('rating').notNull(), // 1-5 stars or -1/1 for thumbs
    createdAt: timestamp('created_at').defaultNow().notNull(),
    updatedAt: timestamp('updated_at').defaultNow().onUpdateNow().notNull(),
  },
  (table) => ({
    pk: primaryKey({ columns: [table.userId, table.videoId] }),
  })
);

/**
 * Watch history - tracks video watch progress
 */
export const watchHistory = mysqlTable('watch_history', {
  id: int('id').primaryKey().autoincrement(),
  userId: varchar('user_id', { length: 36 }).references(() => users.id).notNull(),
  videoId: varchar('video_id', { length: 20 }).notNull(),
  watchedAt: timestamp('watched_at').defaultNow().notNull(),
  watchDuration: int('watch_duration').notNull().default(0),
  completed: boolean('completed').notNull().default(false),
});

/**
 * Channel preferences - user preferences for channels
 */
export const channelPreferences = mysqlTable(
  'channel_preferences',
  {
    userId: varchar('user_id', { length: 36 }).references(() => users.id).notNull(),
    channelId: varchar('channel_id', { length: 30 }).notNull(),
    channelTitle: varchar('channel_title', { length: 255 }).notNull(),
    preference: int('preference').notNull(), // -1 = block, 0 = neutral, 1 = prefer
    createdAt: timestamp('created_at').defaultNow().notNull(),
    updatedAt: timestamp('updated_at').defaultNow().onUpdateNow().notNull(),
  },
  (table) => ({
    pk: primaryKey({ columns: [table.userId, table.channelId] }),
  })
);

// Type exports
export type User = typeof users.$inferSelect;
export type NewUser = typeof users.$inferInsert;

export type SearchHistory = typeof searchHistory.$inferSelect;
export type NewSearchHistory = typeof searchHistory.$inferInsert;

export type Playlist = typeof playlists.$inferSelect;
export type NewPlaylist = typeof playlists.$inferInsert;

export type PlaylistItem = typeof playlistItems.$inferSelect;
export type NewPlaylistItem = typeof playlistItems.$inferInsert;

export type FavoriteTopic = typeof favoriteTopics.$inferSelect;
export type NewFavoriteTopic = typeof favoriteTopics.$inferInsert;

export type VideoRating = typeof videoRatings.$inferSelect;
export type NewVideoRating = typeof videoRatings.$inferInsert;

export type WatchHistory = typeof watchHistory.$inferSelect;
export type NewWatchHistory = typeof watchHistory.$inferInsert;

export type ChannelPreference = typeof channelPreferences.$inferSelect;
export type NewChannelPreference = typeof channelPreferences.$inferInsert;
