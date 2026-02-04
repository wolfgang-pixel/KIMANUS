import OpenAI from 'openai';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

export interface LLMMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface LLMResponse {
  content: string;
  usage?: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
}

/**
 * Invoke the LLM with a list of messages
 */
export async function invokeLLM(options: {
  messages: LLMMessage[];
  model?: string;
  temperature?: number;
  maxTokens?: number;
}): Promise<LLMResponse> {
  const {
    messages,
    model = 'gpt-4o-mini',
    temperature = 0.7,
    maxTokens = 1000,
  } = options;

  try {
    const response = await openai.chat.completions.create({
      model,
      messages: messages.map((m) => ({
        role: m.role,
        content: m.content,
      })),
      temperature,
      max_tokens: maxTokens,
    });

    const choice = response.choices[0];

    return {
      content: choice?.message?.content || '',
      usage: response.usage
        ? {
            promptTokens: response.usage.prompt_tokens,
            completionTokens: response.usage.completion_tokens,
            totalTokens: response.usage.total_tokens,
          }
        : undefined,
    };
  } catch (error) {
    console.error('LLM Error:', error);
    throw new Error('LLM-Anfrage fehlgeschlagen');
  }
}

/**
 * Analyze video content and suggest optimal timestamp
 */
export async function analyzeVideoForTimestamp(options: {
  topic: string;
  specificQuestion?: string;
  videoTitle: string;
  videoDescription: string;
  videoDuration: number;
}): Promise<{ timestamp: number; duration: number; reasoning: string }> {
  const { topic, specificQuestion, videoTitle, videoDescription, videoDuration } = options;

  const systemPrompt = `Du bist ein Video-Analyst, der die besten Abschnitte in YouTube-Videos identifiziert.
Deine Aufgabe ist es, basierend auf Titel und Beschreibung eines Videos den optimalen Startpunkt zu bestimmen.

Regeln:
1. Der Timestamp muss zwischen 0 und ${videoDuration - 30} Sekunden liegen
2. Die empfohlene Dauer sollte zwischen 30 und 300 Sekunden sein
3. Wähle einen Abschnitt, der das Thema direkt behandelt
4. Vermeide Intros, Outros und Werbung (meist in den ersten 30 und letzten 60 Sekunden)

Antworte NUR im folgenden JSON-Format:
{
  "timestamp": <Sekunden>,
  "duration": <Sekunden>,
  "reasoning": "<Kurze Begründung auf Deutsch>"
}`;

  const userPrompt = `Thema: "${topic}"
${specificQuestion ? `Spezielle Frage: "${specificQuestion}"` : ''}

Video-Titel: "${videoTitle}"
Video-Beschreibung: "${videoDescription}"
Video-Länge: ${videoDuration} Sekunden

Finde den besten Abschnitt für dieses Thema.`;

  const response = await invokeLLM({
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt },
    ],
    temperature: 0.3,
    maxTokens: 200,
  });

  try {
    // Extract JSON from response
    const jsonMatch = response.content.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      throw new Error('No JSON found in response');
    }

    const result = JSON.parse(jsonMatch[0]);

    return {
      timestamp: Math.max(0, Math.min(result.timestamp || 30, videoDuration - 30)),
      duration: Math.max(30, Math.min(result.duration || 120, 300)),
      reasoning: result.reasoning || 'Automatisch ausgewählt',
    };
  } catch (error) {
    console.error('Failed to parse LLM response:', response.content);
    // Default fallback
    return {
      timestamp: Math.min(30, videoDuration / 4),
      duration: 120,
      reasoning: 'Standard-Auswahl (LLM-Analyse fehlgeschlagen)',
    };
  }
}
