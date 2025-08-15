---
layout: default
title: Home
---

Welcome to the Weekly News Brief!  

Here I attempt to distill news on Cybersecurity, Cloud, AI and Regulatory News.

{% assign latest_brief = site.posts | where_exp:"post","post.categories contains 'newsbrief'" | sort: "date" | last %}

{% if latest_brief %}
  {{ latest_brief.content }}
{% else %}
  <p>No news brief available yet.</p>
{% endif %}