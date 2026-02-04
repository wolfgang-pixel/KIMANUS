import type { CreateExpressContextOptions } from '@trpc/server/adapters/express';

export async function createContext({ req, res }: CreateExpressContextOptions) {
  // Extract user from auth header if present (Manus OAuth)
  const authHeader = req.headers.authorization;
  let user: { id: string; email?: string } | null = null;

  if (authHeader?.startsWith('Bearer ')) {
    // In production, verify the token with Manus OAuth
    // For now, we'll use a simple mock
    const token = authHeader.slice(7);
    if (token) {
      user = { id: 'demo-user', email: 'demo@kimtv.local' };
    }
  }

  return {
    req,
    res,
    user,
  };
}

export type Context = Awaited<ReturnType<typeof createContext>>;
