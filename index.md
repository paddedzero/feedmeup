---
layout: default
title: Home
---

Welcome to the Weekly News Brief!  

Here I attempt to distill news on Cybersecurity, Cloud, AI and Regulatory News.

<ul class="brief-list">
  {% for post in site.posts %}
    <li>
      <a href="{{ post.url | relative_url }}">
        {{ post.title }}
      </a>
      - <span>{{ post.date | date: "%B %d, %Y" }}</span>
    </li>
  {% endfor %}
</ul>