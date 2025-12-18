/**
 * BYOK (Bring Your Own Key) Utilities
 * Manages Anthropic API keys for Thoth AI
 *
 * Keys are stored locally in the browser and never sent to our servers.
 * Users pay Anthropic directly for AI usage.
 */

const STORAGE_KEY = "dynasty_edge_anthropic_key";

/**
 * Store the Anthropic API key in localStorage
 * In a production app, you might want to encrypt this with a user-specific key
 */
export function setAnthropicKey(key: string): void {
  if (typeof window === "undefined") return;

  // Basic validation
  if (!key.startsWith("sk-ant-")) {
    throw new Error("Invalid API key format. Anthropic keys start with 'sk-ant-'");
  }

  // Store the key (in production, consider encrypting)
  localStorage.setItem(STORAGE_KEY, key);
}

/**
 * Retrieve the stored Anthropic API key
 */
export function getAnthropicKey(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(STORAGE_KEY);
}

// Alias for api.ts compatibility
export const getStoredKey = getAnthropicKey;

/**
 * Check if an API key is stored
 */
export function hasAnthropicKey(): boolean {
  return getAnthropicKey() !== null;
}

/**
 * Remove the stored API key
 */
export function removeAnthropicKey(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEY);
}

/**
 * Mask an API key for display (show only last 8 characters)
 */
export function maskApiKey(key: string): string {
  if (key.length <= 12) return "****";
  return `sk-ant-...${key.slice(-8)}`;
}

/**
 * Validate an Anthropic API key format
 */
export function isValidKeyFormat(key: string): boolean {
  return key.startsWith("sk-ant-") && key.length > 20;
}

/**
 * Chat with Claude using the stored API key
 * This function handles the streaming response from Claude
 */
export async function chatWithClaude(
  messages: Array<{ role: "user" | "assistant"; content: string }>,
  onChunk?: (text: string) => void
): Promise<string> {
  const apiKey = getAnthropicKey();

  if (!apiKey) {
    throw new Error("No API key found. Please add your Anthropic API key in settings.");
  }

  const systemPrompt = `You are Thoth, a dynasty fantasy football analyst AI assistant for Dynasty Edge.
You help users with:
- Trade analysis and advice
- Player valuations and projections
- Roster construction strategies
- Dynasty draft strategy
- Buy/sell recommendations

Be concise, data-driven, and helpful. Reference KTC values and our ML projections when relevant.
If you don't have specific data, say so and provide general guidance.`;

  try {
    const response = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
        "anthropic-dangerous-direct-browser-access": "true",
      },
      body: JSON.stringify({
        model: "claude-sonnet-4-20250514",
        max_tokens: 1024,
        system: systemPrompt,
        messages: messages,
        stream: !!onChunk,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error?.message || `API Error: ${response.status}`);
    }

    if (onChunk && response.body) {
      // Handle streaming response
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === "content_block_delta" && data.delta?.text) {
                fullText += data.delta.text;
                onChunk(data.delta.text);
              }
            } catch {
              // Skip invalid JSON lines
            }
          }
        }
      }

      return fullText;
    } else {
      // Handle non-streaming response
      const data = await response.json();
      return data.content[0]?.text || "";
    }
  } catch (error) {
    if (error instanceof Error && error.message.includes("401")) {
      throw new Error("Invalid API key. Please check your Anthropic API key in settings.");
    }
    throw error;
  }
}
