---
layout: default
title: Home
---

Welcome to the Weekly News Brief!  

Here I attempt to distill news on Cybersecurity, Cloud, AI and Regulatory News.


{% assign latest_brief = site.posts | where_exp:"post","post.categories contains 'news brief'" | sort: "date" | last %}
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
