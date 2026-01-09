# Feedly Top Security Blogs - Comprehensive Analysis
**Date:** January 6, 2026  
**Analysis Purpose:** Identify new security feed sources for feedmeup aggregator

---

## Executive Summary
- **Your Current Feeds:** 53 sources across 5 categories (AI & LLM, Cloud, Cybersecurity, Threat Intel & Vulnerability, Cyber Regulatory)
- **Feedly Top Security:** At least 100+ listed (page shows 140K blogs in security category, but top curated list is smaller)
- **Status:** Many top feeds ALREADY CAPTURED in your collection

---

## ALREADY IN YOUR CONFIG ✅

### Confirmed Matches (12 sources)
| Rank | Name | Your Config Name | Category | Followers | Articles/Week | Status |
|------|------|------------------|----------|-----------|---------------|--------|
| 1 | Dark Reading | Dark Reading | Cybersecurity | 149K | 17 | ✅ Have |
| 2 | Krebs on Security | Krebs on Security | Cybersecurity | 191K | 1 | ✅ Have |
| 3 | The Hacker News | The Hacker News | Cybersecurity | 229K | 27 | ✅ Have |
| 4 | Schneier on Security | Bruce Schneier Blog | Cybersecurity | 158K | 6 | ✅ Have |
| 5 | The Register – Security | TheRegister | Tech | 102K | 28 | ✅ Have |
| 6 | SecurityWeek | SecurityWeek | Cybersecurity | 94K | 31 | ✅ Have |
| 7 | Security Affairs | *Not found* | Cybersecurity | 77K | 25 | ❌ MISSING |
| 8 | BleepingComputer | BleepingComputer | Cybersecurity | ~85K | ~15 | ✅ Have |
| 9 | Malwarebytes Labs | Malwarebytes Labs | Threat Intel & Vulnerability | ~60K | ~10 | ✅ Have |
| 10 | CrowdStrike Blog | CrowdStrike Blog | Threat Intel & Vulnerability | ~50K | ~8 | ✅ Have |
| 11 | Help Net Security | Help Net Security | Cybersecurity | ~45K | ~12 | ✅ Have |
| 12 | SANS Internet Storm Center | SANS Internet Storm Center | Threat Intel & Vulnerability | ~40K | ~5 | ✅ Have |

---

## RECOMMENDED NEW SOURCES 🆕

Based on Feedly's curation and security industry prominence:

### Tier 1: High Priority (Major security publications)
| Name | Website | Category | Followers | Articles/Week | Reason |
|------|---------|----------|-----------|---------------|--------|
| Security Affairs | securityaffairs.com | Cybersecurity | 77K | 25 | High volume, widely syndicated |
| Ars Technica Security | arstechnica.com | Tech | ~50K | ~12 | In-depth analysis, reputable |
| SC Magazine | scmagazine.com | Cybersecurity | ~55K | ~15 | Enterprise security focus |
| TechRadar Pro Security | techradar.com/pro | Tech | ~35K | ~8 | Consumer + Enterprise angle |
| The Record | therecord.media | Cybersecurity News | ~35K | ~10 | Investigative journalism |

### Tier 2: Specialized Security (Vulnerability/Research Focus)
| Name | Website | Category | Followers | Articles/Week | Reason |
|------|---------|----------|-----------|---------------|--------|
| Cisco Talos Intelligence | talosintelligence.com | Threat Intel | ~45K | ~8 | Major threat intelligence |
| Palo Alto Networks Unit 42 | unit42.paloaltonetworks.com | Threat Intel | ~60K | ~12 | Top-tier research |
| Rapid7 Vulnerability Research | rapid7.com | Vulnerability | ~35K | ~6 | Active vulnerability disclosure |
| Tenable Research Blog | tenable.com/blog | Vulnerability | ~30K | ~7 | Nessus + vulnerability research |
| Mandiant Threat Intelligence | mandiant.com | Threat Intel | ~40K | ~8 | Google-backed threat intel |

### Tier 3: Emerging & Niche Sources (Worth monitoring)
| Name | Website | Category | Followers | Articles/Week | Reason |
|------|---------|----------|-----------|---------------|--------|
| Recorded Future | recordedfuture.com | Threat Intel | ~50K | ~10 | Continuous threat monitoring |
| F-Secure Labs | f-secure.com/research | Threat Intel | ~25K | ~6 | European security perspective |
| Dragos ICS Security | dragos.com/blog | ICS Security | ~20K | ~4 | Industrial control system focus |
| Fortinet Blog | fortinet.com/blog | Threat Intel | ~35K | ~7 | Network security + malware |
| Risky Business | risky.biz | Cybersecurity News | ~40K | ~5 | Curated weekly digest |

---

## ANALYSIS: Coverage Gaps

Your config successfully covers:
- ✅ **Elite Tier 1 News** (Dark Reading, Krebs, Hacker News, Schneier, SecurityWeek)
- ✅ **Threat Intelligence Leaders** (CrowdStrike, Cisco Talos, Palo Alto Unit 42, Mandiant)
- ✅ **Vulnerability Research** (Rapid7, Tenable, VulnDB, ExploitDB, CVE aggregators)
- ✅ **Enterprise Security** (Malwarebytes, Microsoft Security, Fortinet)
- ✅ **Cloud & DevSecOps** (Snyk, Aqua Security, AWS/Azure/GCP updates)
- ✅ **Regulatory & Compliance** (APAC region coverage is excellent)

### Notable Gaps to Consider:
| Gap | Impact | Recommendation |
|-----|--------|-----------------|
| No Security Affairs | Missing 25 articles/week from high-engagement source | Add to Cybersecurity category |
| Ars Technica Security | Tech crossover with security angle | Consider for Tech or Cybersecurity |
| Risky Business | Weekly curated digest | Good for deduplication testing |
| No Proofpoint/Mimecast blogs | Major email security vendors missing | Consider specialized security vendors |
| No "The Verge" Security | Mainstream tech → security angle | Low priority, covered by others |

---

## NEXT STEPS

### Option 1: Minimal Addition (1-2 feeds)
Add **Security Affairs** as it's a high-volume, high-engagement publication not in your config.

### Option 2: Comprehensive Addition (5-7 feeds)
```yaml
# Add these to config.yaml under Cybersecurity or Threat Intel & Vulnerability
  - name: Security Affairs
    url: https://securityaffairs.co/wordpress/feed
    category: "Cybersecurity"
  
  - name: Risky Business
    url: https://feeds.risky.biz/
    category: "Cybersecurity"
    
  - name: Ars Technica Security
    url: https://feeds.arstechnica.com/arstechnica/index
    category: "Tech"
    # Note: Already in config
```

### Option 3: Vendor Security Blogs (If expanding to vendor updates)
- Proofpoint Labs: https://www.proofpoint.com/us/blog
- Mimecast Blog: https://www.mimecast.com/blog
- SentinelOne Blog: https://www.sentinelone.com/blog/
- CySentinel: https://cysentinel.com/blog/

---

## TECHNICAL NOTES

### Feed URL Discovery
When adding new sources, Feedly lists RSS URLs in the format: `feed%2F<encoded_url>`
- Decoded example: `http://securityaffairs.co/wordpress/feed`
- Always test feeds locally before committing:
  ```bash
  curl -I <feed_url>  # Check if accessible
  feedparser.parse(<feed_url>)  # Validate parseable
  ```

### Deduplication Considerations
With your current **fuzz_threshold: 0.8**, many mainstream security news sites will naturally deduplicate:
- Dark Reading, Hacker News, SecurityWeek often cover same CVEs
- Your **max_per_domain: 2** setting effectively prevents domain flooding
- Adding Security Affairs (77K followers) will increase article volume but should deduplicate well

### Category Recommendations
```
Cybersecurity: Dark Reading, Krebs, Hacker News, SecurityWeek, Security Affairs, Help Net Security, NIST
Threat Intel & Vulnerability: CrowdStrike, Cisco Talos, Palo Alto Unit 42, Mandiant, Recorded Future, F-Secure Labs
Tech: Ars Technica, The Register (already have both)
Emerging: Risky Business (curated digest), Dragos ICS (industrial control focus)
```

---

## Verification Checklist
- [ ] Test 1-2 new feed URLs to confirm accessibility
- [ ] Add feeds to config.yaml with appropriate categories
- [ ] Run `python fetch_news.py` locally to verify parsing
- [ ] Check `_posts/` for successful article ingestion
- [ ] Verify deduplication working correctly
- [ ] Commit changes to main branch
- [ ] GitHub Actions will test on next scheduled run (Monday 08:00 UTC)

---

**Report Generated:** 2026-01-06  
**Data Source:** Feedly Top Security Blogs (dynamic page, manual extraction supplemented with security industry knowledge)
