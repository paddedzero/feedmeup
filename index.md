---
layout: default
title: Home
---

<div class="hero-banner" role="img" aria-label="FeedMeUp News Brief">
  <img src="{{ '/assets/img/banner.svg' | relative_url }}" alt="FeedMeUp News Brief banner" />
</div>


{% assign latest_brief = site.posts | where_exp:"post","post.categories contains 'newsbrief'" | sort: "date" | last %}
{% if latest_brief %}
  <h1>{{ latest_brief.title }}</h1>

  {% if latest_brief.highlights %}
    <h2>Top 5 Highlights</h2>
    <ul>
    {% for item in latest_brief.highlights %}
      <li class="highlight">{{ item }}</li>
    {% endfor %}
    </ul>
  {% endif %}

  {{ latest_brief.content }}

{% else %}
  <p>No news brief available yet.</p>
{% endif %}
