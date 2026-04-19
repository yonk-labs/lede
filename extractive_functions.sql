-- ============================================================================
-- Extractive Summarization & Text Cleaning Functions
-- Pure PL/pgSQL — no tsvector, no extensions required
-- ============================================================================

-- ============================================================================
-- 1. clean_text(input_text)
--    Removes markdown formatting, filler words, extra whitespace, boilerplate.
--    Returns cleaned, lowercase text.
-- ============================================================================
CREATE OR REPLACE FUNCTION clean_text(input_text TEXT)
RETURNS TEXT
LANGUAGE plpgsql IMMUTABLE STRICT AS $$
DECLARE
    result TEXT;
BEGIN
    result := input_text;

    -- Remove markdown formatting: **bold**, __underline__, # headers, --- separators
    result := regexp_replace(result, '\*{1,3}', '', 'g');
    result := regexp_replace(result, '_{1,3}', '', 'g');
    result := regexp_replace(result, '^#{1,6}\s*', '', 'gm');
    result := regexp_replace(result, '^-{3,}$', '', 'gm');
    result := regexp_replace(result, '^\s*[-*+]\s+', '', 'gm');

    -- Remove numbered list prefixes (1. 2. etc) but keep the content
    result := regexp_replace(result, '^\s*\d+\.\s+', '', 'gm');

    -- Remove common filler phrases
    result := regexp_replace(result, '\b(just wanted to|I just wanted to|wanted to follow up|as discussed|per our conversation|as mentioned|going forward|at the end of the day|in terms of|with respect to|in regards to|please find attached|hope this helps|let me know if you have any questions|looking forward to hearing from you)\b', '', 'gi');

    -- Remove common filler words (surrounded by word boundaries)
    result := regexp_replace(result, '\b(basically|essentially|actually|literally|honestly|frankly|obviously|clearly|simply|really|very|quite|rather|pretty much|kind of|sort of|in order to|due to the fact that|at this point in time|for all intents and purposes)\b', '', 'gi');

    -- Remove boilerplate CRM patterns
    result := regexp_replace(result, '\bNo update[s]?\b\.?', '', 'gi');
    result := regexp_replace(result, '\bCalendar invite sent[.]?\b', '', 'gi');
    result := regexp_replace(result, '\bSent (proposal|case study|documentation|overview|pricing) (documentation |via email|as requested)?\.?\b', '', 'gi');
    result := regexp_replace(result, '\bWaiting (on|for) callback\.?\b', '', 'gi');
    result := regexp_replace(result, '\bUpdated CRM with latest info\.?\b', '', 'gi');
    result := regexp_replace(result, '\bMeeting confirmed for next week\.?\b', '', 'gi');
    result := regexp_replace(result, '\bFollowing standard sales process\.?\b', '', 'gi');
    result := regexp_replace(result, '\bMeeting went as expected\.?\b', '', 'gi');

    -- Lowercase
    result := LOWER(result);

    -- Collapse multiple spaces/tabs to single space
    result := regexp_replace(result, '[ \t]+', ' ', 'g');

    -- Collapse multiple newlines to single newline
    result := regexp_replace(result, '\n\s*\n+', E'\n', 'g');

    -- Remove leading/trailing whitespace per line
    result := regexp_replace(result, '^\s+', '', 'gm');
    result := regexp_replace(result, '\s+$', '', 'gm');

    -- Remove empty lines
    result := regexp_replace(result, '^\s*$\n?', '', 'gm');

    -- Final trim
    result := TRIM(result);

    RETURN result;
END;
$$;

COMMENT ON FUNCTION clean_text(TEXT) IS
'Removes markdown, filler words, CRM boilerplate, and extra whitespace from text. Returns cleaned lowercase text.';


-- ============================================================================
-- 2. extract_sentences(input_text, keywords, num_sentences)
--    Extracts the most relevant sentences from a single text block.
--    Scores sentences by keyword overlap with the provided prompt/keywords.
--    Returns top N sentences ordered by relevance score.
--
--    Parameters:
--      input_text    — the text to extract from (can be any length)
--      keywords      — prompt or keywords to match against (space-separated)
--      num_sentences — how many sentences to return
-- ============================================================================
CREATE OR REPLACE FUNCTION extract_sentences(
    input_text TEXT,
    keywords TEXT,
    num_sentences INTEGER DEFAULT 10
)
RETURNS TEXT
LANGUAGE plpgsql IMMUTABLE STRICT AS $$
DECLARE
    keyword_arr TEXT[];
    sentences TEXT[];
BEGIN
    IF input_text IS NULL OR input_text = '' THEN
        RETURN '';
    END IF;

    -- Parse keywords: lowercase, split on spaces, remove short words
    keyword_arr := ARRAY(
        SELECT DISTINCT LOWER(TRIM(word))
        FROM unnest(string_to_array(LOWER(keywords), ' ')) AS word
        WHERE LENGTH(TRIM(word)) > 2
    );

    IF array_length(keyword_arr, 1) IS NULL THEN
        RETURN LEFT(input_text, 2000);
    END IF;

    -- Split text into sentences on . ? ! and newlines
    -- Keep sentences that are meaningful (> 20 chars)
    sentences := ARRAY(
        SELECT TRIM(s)
        FROM unnest(
            regexp_split_to_array(
                regexp_replace(input_text, E'\n+', '. ', 'g'),
                E'(?<=[.!?])\\s+'
            )
        ) AS s
        WHERE LENGTH(TRIM(s)) > 20
    );

    IF array_length(sentences, 1) IS NULL THEN
        RETURN input_text;
    END IF;

    -- Score each sentence and collect top N
    RETURN (
        SELECT STRING_AGG(scored_sentence, E'\n' ORDER BY rank_score DESC)
        FROM (
            SELECT
                s AS scored_sentence,
                (
                    SELECT COUNT(*)::NUMERIC
                    FROM unnest(keyword_arr) AS keyword
                    WHERE LOWER(s) LIKE '%' || keyword || '%'
                )
                -- Bonus for longer, more substantive sentences
                + CASE WHEN LENGTH(s) > 200 THEN 0.5 ELSE 0 END
                -- Bonus for sentences with numbers (data-rich)
                + CASE WHEN s ~ '\d+' THEN 0.3 ELSE 0 END
                -- Bonus for causal/analytical language
                + CASE WHEN LOWER(s) ~ '(because|reason|due to|caused|result|impact|issue|problem|concern|risk|challenge|blocker|gap|lack|missing|competitor|pricing|budget|cost|expensive|cheaper|alternative|decided|chose|prefer|switched|rejected|declined)' THEN 1.0 ELSE 0 END
                AS rank_score
            FROM unnest(sentences) AS s
            ORDER BY rank_score DESC
            LIMIT num_sentences
        ) ranked
    );
END;
$$;

COMMENT ON FUNCTION extract_sentences(TEXT, TEXT, INTEGER) IS
'Extracts the N most relevant sentences from a text block based on keyword matching. Uses keyword overlap scoring with bonuses for substantive, data-rich, and causal/analytical language.';


-- ============================================================================
-- 3. extract_relevant(input_text, prompt, num_sentences)
--    Wrapper that cleans text first, then extracts relevant sentences.
--    Designed for use directly on text columns in queries.
--
--    Parameters:
--      input_text    — raw text (with markdown, filler, etc)
--      prompt        — the analysis prompt or keywords to match against
--      num_sentences — how many sentences to return (default 10)
-- ============================================================================
CREATE OR REPLACE FUNCTION extract_relevant(
    input_text TEXT,
    prompt TEXT,
    num_sentences INTEGER DEFAULT 10
)
RETURNS TEXT
LANGUAGE plpgsql IMMUTABLE STRICT AS $$
BEGIN
    RETURN extract_sentences(clean_text(input_text), prompt, num_sentences);
END;
$$;

COMMENT ON FUNCTION extract_relevant(TEXT, TEXT, INTEGER) IS
'Cleans text (removes markdown, filler, boilerplate) then extracts the N most relevant sentences based on keyword matching against the prompt.';


-- ============================================================================
-- 4. strip_think(input_text)
--    Removes <think>...</think> reasoning blocks from LLM output.
--    Reasoning models (Qwen3, DeepSeek-R1, QwQ) emit chain-of-thought
--    inside <think> tags in the content field. This function strips them.
--
--    Parameters:
--      input_text — LLM output that may contain <think>...</think> blocks
-- ============================================================================
CREATE OR REPLACE FUNCTION strip_think(input_text TEXT)
RETURNS TEXT
LANGUAGE plpgsql IMMUTABLE STRICT AS $$
BEGIN
    RETURN TRIM(regexp_replace(input_text, '<think>.*?</think>\s*', '', 'gs'));
END;
$$;

COMMENT ON FUNCTION strip_think(TEXT) IS
'Removes <think>...</think> reasoning/chain-of-thought blocks from LLM output. Use as a wrapper around summarize results from reasoning models (Qwen3, DeepSeek-R1, etc).';
