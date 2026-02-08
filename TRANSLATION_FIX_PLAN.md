# Korean Article Translation - Implementation Plan

## Problem
Korean articles from feeds (e.g., Korea KISA) are appearing untranslated in your weekly scans.

## Current State
- **Config has translation settings** (`config.yaml` lines 614-619)
  - `enabled: true`
  - Auto-detect Japanese, Chinese, Korean
  - Uses Gemini API
- **But fetch_news.py has NO translation logic implemented** ❌

## Recommended Solutions

### Option 1: Implement Translation in fetch_news.py ⭐ (Recommended)

Add a `translate_text()` function that:
1. Detects non-English text (Korean, Japanese, Chinese)
2. Uses Gemini API to translate to English
3. Preserves original title in `_original_title` field
4. Translates summary/description

**Where to add:**
- Add function after `summarize_with_gemini()` (around line 600-700)
- Call it in `fetch_articles()` before saving posts
- Use the existing GEMINI_CLIENT

**Benefits:**
- Consistent with your config
- Uses existing Gemini API setup
- Automatic for all feeds

### Option 2: Filter Out Korean Feeds

Simply remove or comment out Korean feeds in config.yaml:

```yaml
# Commented out - Korean language
# - name: Korea KISA
#   url: https://www.kisa.or.kr/rss/eng.xml
#   category: "Cyber Regulatory"
```

**Benefits:**
- Quick fix
- No code changes
- No translation costs

### Option 3: Use English Version of Feeds

Some feeds have English versions:
- Korea KISA: Already using `/eng.xml` ✅
- Check if other APAC feeds have `/en/` versions

## Immediate Action Items

**Quick Win (5 minutes):**
1. Check which feeds are outputting Korean
2. Look for English RSS alternatives
3. Update config.yaml URLs

**Long-term (30-60 minutes):**
1. Implement `translate_text()` function in fetch_news.py
2. Integrate with article processing pipeline
3. Test with Korean articles

## Example Translation Function

```python
def translate_text(text, target_lang="English"):
    """Translate non-English text using Gemini API."""
    if not GEMINI_AVAILABLE or not GEMINI_CLIENT:
        return text
    
    # Detect if text contains Korean/Japanese/Chinese
    if not re.search(r'[가-힣ぁ-んァ-ヶ一-龯]', text):
        return text  # Already English
    
    prompt = f"Translate the following text to {target_lang}. Preserve technical terms and proper nouns:\\n\\n{text}"
    
    try:
        response = GEMINI_CLIENT.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config={"temperature": 0.3, "max_output_tokens": 500}
        )
        return response.text.strip()
    except Exception as e:
        logging.error(f"Translation failed: {e}")
        return text  # Return original on error
```

## Which Option Do You Prefer?

1. **Option 1**: Implement translation (full automation)
2. **Option 2**: Remove Korean feeds (quick fix)
3. **Option 3**: Find English alternatives (manual but clean)

Let me know and I'll help implement!
